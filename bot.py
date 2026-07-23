import os
import math
import sqlite3
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CREDENCIALES DE GREEN API ---
ID_INSTANCE = "710722691516"
API_TOKEN_INSTANCE = "a807a932d0c64f24a4fd2469a72a0214c225a4fe2d9c41bcb2"
GREEN_API_URL = f"https://api.green-api.com/waInstance{ID_INSTANCE}"

DB_NAME = "inventario_led_fijo.db"

# --- CREACIÓN AUTOMÁTICA DE BASE DE DATOS ---
def inicializar_bd():
    if not os.path.exists(DB_NAME):
        print("⚠️ Base de datos no encontrada. Creándola de forma automática...")
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
        
        pantallas_defecto = [
            ('PIKA', 'P4.8 Outdoor (Pika)', 500, 1000, 104, 208, 100, 0, 0, 0),
            ('ROMBO', 'P3.9 Indoor (Rombo)', 500, 500, 128, 128, 80, 0, 0, 0),
            ('UNI 500', 'P2.9 Indoor (Uni 500)', 500, 500, 168, 168, 60, 0, 0, 0),
            ('UNI 1000', 'P2.9 Indoor (Uni 1000)', 500, 1000, 168, 336, 40, 0, 0, 0),
            ('BLACKFACE', 'P3.9 Outdoor BlackFace', 500, 1000, 128, 256, 50, 0, 0, 0),
            ('NUEVA NUEVA', 'P2.6 High Refresh', 500, 500, 192, 192, 50, 0, 0, 0)
        ]
        
        cursor.executemany("""
            INSERT OR IGNORE INTO inventario 
            (partida, nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, gabs_comprados_total, gabs_rotos, ladrillos_en_reparacion, ladrillos_esperando)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, pantallas_defecto)
        
        conn.commit()
        conn.close()
        print("✅ Base de datos inicializada correctamente.")

inicializar_bd()

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_datos_partida(partida):
    inicializar_bd()
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, 
                   gabs_comprados_total, gabs_rotos, ladrillos_en_reparacion, ladrillos_esperando 
            FROM inventario WHERE partida=?
        """, (partida,))
        res = cursor.fetchone()
        if not res:
            conn.close()
            return None
            
        cursor.execute("SELECT SUM(gabs_usados) FROM salones WHERE partida=?", (partida,))
        gabs_en_uso = cursor.fetchone()[0] or 0
        conn.close()
        
        nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, total_gabs, gabs_rotos, lad_rep, lad_esp = res
        ancho_m = ancho_mm / 1000.0
        alto_m = alto_mm / 1000.0
        m2_por_gab = ancho_m * alto_m
        gabs_funcionando_ok = total_gabs - gabs_rotos
        gabs_disponibles = gabs_funcionando_ok - gabs_en_uso
        
        return {
            "nombre": nombre_largo, "ancho_m": ancho_m, "alto_m": alto_m,
            "px_ancho": px_ancho, "px_alto": px_alto, "m2_por_gab": m2_por_gab,
            "total_gabs": total_gabs, "rotos_gabs": gabs_rotos,
            "en_uso_gabs": gabs_en_uso, "disponibles_gabs": gabs_disponibles,
            "ladrillos_en_reparacion": lad_rep, "ladrillos_esperando": lad_esp
        }
    except Exception as e:
        print(f"Error DB: {e}")
        return None

def ver_reporte_stock():
    inicializar_bd()
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT partida FROM inventario")
        partidas = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        reporte = "📦 *REPORTE DE DEPÓSITO Y STOCK*\n----------------------------------\n"
        for p_id in partidas:
            p = obtener_datos_partida(p_id)
            if p:
                reporte += f"🔹 *{p['nombre']}*\n"
                reporte += f"  • Libres en cajón: {p['disponibles_gabs']} gabs ({p['disponibles_gabs']*p['m2_por_gab']:.2f} m²)\n"
                reporte += f"  • En uso salones: {p['en_uso_gabs']} gabs\n"
                reporte += f"  • En Taller: {p['rotos_gabs']} gabs\n"
                reporte += f"----------------------------------\n"
        return reporte
    except Exception as e:
        return f"Error leyendo stock: {e}"

def ver_reporte_taller():
    inicializar_bd()
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT partida FROM inventario")
        partidas = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        reporte = "🛠️ *REPORTE DE COMPONENTES EN TALLER*\n----------------------------------\n"
        for p_id in partidas:
            p = obtener_datos_partida(p_id)
            if p and (p['rotos_gabs'] > 0 or p['ladrillos_en_reparacion'] > 0 or p['ladrillos_esperando'] > 0):
                reporte += f"🔸 *{p['nombre']}*\n"
                reporte += f"  • Módulos rotos: {p['rotos_gabs']} gabs\n"
                reporte += f"  • Ladrillos en reparación: {p['ladrillos_en_reparacion']}\n"
                reporte += f"  • Ladrillos esperando rep: {p['ladrillos_esperando']}\n"
                reporte += f"----------------------------------\n"
        return reporte
    except Exception as e:
        return f"Error leyendo taller: {e}"

# --- ENVIAR MENSAJE VÍA GREEN API REST ---
def enviar_mensaje_whatsapp(chat_id, texto):
    url = f"{GREEN_API_URL}/sendMessage/{API_TOKEN_INSTANCE}"
    payload = {
        "chatId": chat_id,
        "message": texto
    }
    headers = {'Content-Type': 'application/json'}
    try:
        r = requests.post(url, json=payload, headers=headers)
        print(f"📤 Envió mensaje a {chat_id} (Status {r.status_code})")
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

# --- RUTAS FLASK / WEBHOOK ---
@app.route("/", methods=["GET"])
def health_check():
    return "OK - Bot de WhatsApp escuchando vía Webhook", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    
    # Extraer chatId sin importar la variante del evento
    sender_data = data.get("senderData", {})
    chat_id = sender_data.get("chatId") or data.get("chatId")
    
    # Intentar obtener el texto del mensaje
    message_data = data.get("messageData", {})
    type_msg = message_data.get("typeMessage", "")
    
    texto = ""
    if type_msg == "textMessage":
        texto = message_data.get("textMessageData", {}).get("textMessage", "")
    elif type_msg == "extendedTextMessage":
        texto = message_data.get("extendedTextMessageData", {}).get("text", "")
    
    texto = texto.strip()
    
    if texto and chat_id:
        print(f"📥 MENSAJE DETECTADO: '{texto}' en ChatID: {chat_id}")
        
        if texto.startswith("!"):
            cmd = texto.lower()
            
            if cmd == "!stock":
                enviar_mensaje_whatsapp(chat_id, ver_reporte_stock())
            elif cmd == "!taller":
                enviar_mensaje_whatsapp(chat_id, ver_reporte_taller())
            else:
                match = re.match(r"^!(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s*(.+)$", cmd)
                if match:
                    ancho = float(match.group(1))
                    alto = float(match.group(2))
                    modelo_buscado = match.group(3).strip().upper()
                    
                    mapa_modelos = {
                        "PIKA": "PIKA", "ROMBO": "ROMBO", "UNI500": "UNI 500",
                        "UNI 500": "UNI 500", "UNI1000": "UNI 1000", "UNI 1000": "UNI 1000",
                        "BLACKFACE": "BLACKFACE", "NUEVA": "NUEVA NUEVA", "NUEVA NUEVA": "NUEVA NUEVA"
                    }
                    partida = mapa_modelos.get(modelo_buscado, modelo_buscado)
                    mod = obtener_datos_partida(partida)
                    
                    if not mod:
                        enviar_mensaje_whatsapp(chat_id, f"⚠️ Modelo '{modelo_buscado}' no encontrado en inventario.")
                    else:
                        gabs_ancho = math.ceil(ancho / mod["ancho_m"])
                        gabs_alto = math.ceil(alto / mod["alto_m"])
                        total_necesarios = gabs_ancho * gabs_alto
                        m2_reales = total_necesarios * mod["m2_por_gab"]
                        px_totales = total_necesarios * (mod["px_ancho"] * mod["px_alto"])
                        cables_main = math.ceil(px_totales / 650000)
                        
                        resp = f"📺 *CÁLCULO DE PANTALLA ({mod['nombre']})*\n"
                        resp += f"----------------------------------\n"
                        resp += f"📐 Solicitado: {ancho}m x {alto}m\n"
                        resp += f"🧱 Estructura Real: {gabs_ancho}x{gabs_alto} ({total_necesarios} gabs | {m2_reales:.2f} m²)\n"
                        resp += f"🔌 Líneas Cat6 (NovaStar): {cables_main} puerto(s) Main\n"
                        resp += f"----------------------------------\n"
                        
                        if total_necesarios <= mod["disponibles_gabs"]:
                            libres = mod["disponibles_gabs"] - total_necesarios
                            resp += f"✅ *DISPONIBLE EN STOCK*\nQuedarán libres en cajón: {libres} gabs"
                        else:
                            faltan = total_necesarios - mod["disponibles_gabs"]
                            resp += f"🚨 *FALTA STOCK EN DEPÓSITO*\nFaltan fabricar/conseguir: {faltan} gabs"
                            
                        enviar_mensaje_whatsapp(chat_id, resp)
                else:
                    ayuda = "🤖 *COMANDOS DEL BOT TÉCNICO*\n"
                    ayuda += "• `!stock` : Ver módulos libres y en uso\n"
                    ayuda += "• `!taller` : Ver componentes rotos\n"
                    ayuda += "• `!4x3 pika` : Calcular pantalla (ancho x alto modelo)\n"
                    enviar_mensaje_whatsapp(chat_id, ayuda)

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
