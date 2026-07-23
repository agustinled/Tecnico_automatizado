import os
import sqlite3
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CREDENCIALES NUEVAS DE GREEN API ---
ID_INSTANCE = "710722691516"
API_TOKEN_INSTANCE = "a807a932d0c64f24a4fd2469a72a0214c225a4fe2d9c41bcb2"
GREEN_API_URL = f"https://api.green-api.com/waInstance{ID_INSTANCE}"

DB_NAME = "inventario_led_fijo.db"

# --- CREACIÓN Y CARGA DE BD CON STOCK REAL CORREGIDO ---
def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            partida TEXT PRIMARY KEY,
            nombre_largo TEXT,
            ancho_mm REAL,
            alto_mm REAL,
            px_ancho INTEGER,
            px_alto INTEGER,
            gabs_comprados_total INTEGER,
            gabs_rotos INTEGER DEFAULT 0,
            ladrillos_en_reparacion INTEGER DEFAULT 0,
            ladrillos_esperando INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS salones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partida TEXT,
            salon TEXT,
            gabs_usados INTEGER
        )
    """)
    
    # INVENTARIO REAL CORREGIDO (PIKA 500x500 mm -> 84 m² = 336 gabs)
    pantallas_reales = [
        ('ROMBO', 'P3.9 Indoor (Rombo)', 500, 500, 128, 128, 192, 0, 0, 0),
        ('PIKA', 'P4.8 Outdoor (Pika)', 500, 500, 104, 104, 336, 0, 0, 0),
        ('UNI 500', 'P2.9 Indoor (Uni 500)', 500, 500, 168, 168, 240, 0, 0, 0),
        ('UNI 1000', 'P2.9 Indoor (Uni 1000)', 500, 1000, 168, 336, 480, 0, 0, 0)
    ]
    
    cursor.executemany("""
        INSERT OR REPLACE INTO inventario 
        (partida, nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, gabs_comprados_total, gabs_rotos, ladrillos_en_reparacion, ladrillos_esperando)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, pantallas_reales)
    
    conn.commit()
    conn.close()

# Inicializar Base de Datos al arrancar
inicializar_bd()

# --- REPORTE DE STOCK EN METROS CUADRADOS Y GABINETES ---
def ver_reporte_stock():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT partida, nombre_largo, ancho_mm, alto_mm, gabs_comprados_total, gabs_rotos FROM inventario")
    modelos = cursor.fetchall()
    
    resp = "📦 *REPORTE DE STOCK DE PANTALLAS*\n"
    resp += "----------------------------------\n"
    
    for mod in modelos:
        partida, nombre_largo, ancho_mm, alto_mm, total_gabs, rotos_gabs = mod
        
        # Cálculo de m² por gabinete
        m2_por_gab = (ancho_mm / 1000.0) * (alto_mm / 1000.0)
        
        # Calcular gabinetes ocupados en salones
        cursor.execute("SELECT SUM(gabs_usados) FROM salones WHERE partida = ?", (partida,))
        usados_res = cursor.fetchone()[0]
        usados_gabs = usados_res if usados_res else 0
        
        libres_gabs = total_gabs - usados_gabs - rotos_gabs
        
        # Conversión a Metros Cuadrados (m²)
        m2_totales = total_gabs * m2_por_gab
        m2_libres = libres_gabs * m2_por_gab
        m2_usados = usados_gabs * m2_por_gab
        
        resp += f"🔹 *{nombre_largo}*\n"
        resp += f"   • Total Depósito: {m2_totales:.1f} m² ({total_gabs} gabs)\n"
        resp += f"   • Disponible Libre: *{m2_libres:.1f} m²* ({libres_gabs} gabs)\n"
        if usados_gabs > 0:
            resp += f"   • Armado en Salones: {m2_usados:.1f} m² ({usados_gabs} gabs)\n"
        if rotos_gabs > 0:
            resp += f"   • En Taller/Rotos: {rotos_gabs * m2_por_gab:.1f} m² ({rotos_gabs} gabs)\n"
        resp += "----------------------------------\n"
        
    conn.close()
    return resp

# --- FUNCIÓN PARA ENVIAR MENSAJES VÍA GREEN API ---
def enviar_mensaje_whatsapp(chat_id, texto):
    url = f"{GREEN_API_URL}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {
        "chatId": chat_id,
        "message": texto
    }
    headers = {'Content-Type': 'application/json'}
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"📤 Respuesta de Green API -> Status: {r.status_code} | Body: {r.text}")
    except Exception as e:
        print(f"❌ Error enviando mensaje a WhatsApp: {e}")

# --- RUTAS DE FLASK ---
@app.route('/', methods=['GET'])
def home():
    return "Bot de Stock LED Fijo activo y funcionando.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "No JSON data"}), 400

    type_webhook = data.get('typeWebhook')
    
    if type_webhook == 'incomingMessageReceived':
        message_data = data.get('messageData', {})
        sender_data = data.get('senderData', {})
        chat_id = sender_data.get('chatId')
        
        # Extracción blindada del texto para chats individuales y grupales
        text_message = ""
        type_msg = message_data.get('typeMessage')
        
        if type_msg == 'textMessage':
            text_message = message_data.get('textMessageData', {}).get('textMessage', '')
        elif type_msg == 'extendedTextMessage':
            text_message = message_data.get('extendedTextMessageData', {}).get('text', '')
        
        # Búsqueda de respaldo si la variable sigue vacía
        if not text_message:
            text_message = (
                message_data.get('textMessageData', {}).get('textMessage') or
                message_data.get('extendedTextMessageData', {}).get('text') or
                ""
            )
            
        text_message = text_message.strip()
        print(f"📥 MENSAJE DETECTADO: '{text_message}' en ChatID: {chat_id}")
        
        # Evaluamos el comando !stock
        if '!stock' in text_message.lower():
            print("🚀 Ejecutando respuesta de !stock...")
            respuesta = ver_reporte_stock()
            enviar_mensaje_whatsapp(chat_id, respuesta)
            
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
