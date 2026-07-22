import math
import sqlite3
import re
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from whatsapp_chatbot_python import GreenAPIBot, Notification

# --- 1. SERVIDOR HTTP SIMPLE PARA CUMPLIR EL REQUISITO DE RENDER ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK - Bot de WhatsApp Activo")
    def log_message(self, format, *args):
        return # Silenciar logs HTTP en consola

def iniciar_servidor_health():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    server.serve_forever()

# Iniciar servidor en hilo secundario
threading.Thread(target=iniciar_servidor_health, daemon=True).start()

# --- 2. VERIFICACIÓN Y CONEXIÓN DE BASE DE DATOS ---
DB_NAME = "inventario_led_fijo.db"

def obtener_datos_partida(partida):
    if not os.path.exists(DB_NAME):
        return None
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
        print(f"Error Base de Datos: {e}")
        return None

def ver_reporte_stock():
    if not os.path.exists(DB_NAME):
        return "⚠️ Base de datos no encontrada en el servidor."
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
    if not os.path.exists(DB_NAME):
        return "⚠️ Base de datos no encontrada en el servidor."
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

# --- 3. INICIALIZACIÓN DEL BOT DE GREEN API ---
bot = GreenAPIBot(
    "710722690480", "096fbb2829b946db96ca3fb1b2edba66b5c7632d6d904ce79c"
)

# --- 4. MANEJADOR DE COMANDOS ---
@bot.router.message()
def procesar_mensaje(notification: Notification) -> None:
    try:
        texto = notification.message_text.strip().lower()
    except Exception:
        return
        
    if not texto.startswith("!"):
        return

    if texto == "!stock":
        notification.answer(ver_reporte_stock())
        return

    if texto == "!taller":
        notification.answer(ver_reporte_taller())
        return

    # Acepta espacio opcional: !4x3 pika o !4x3pika
    match = re.match(r"^!(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s*(.+)$", texto)
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
            notification.answer(f"⚠️ Modelo '{modelo_buscado}' no encontrado en el inventario.")
            return
            
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
            resp += f"✅ *DISPONIBLE EN STOCK*\n"
            resp += f"Quedarán libres en cajón: {libres} gabs"
        else:
            faltan = total_necesarios - mod["disponibles_gabs"]
            resp += f"🚨 *FALTA STOCK EN DEPÓSITO*\n"
            resp += f"Faltan fabricar/conseguir: {faltan} gabs"
            
        notification.answer(resp)
        return

    ayuda = "🤖 *COMANDOS DEL BOT TÉCNICO*\n"
    ayuda += "• `!stock` : Ver módulos libres y en uso\n"
    ayuda += "• `!taller` : Ver componentes rotos\n"
    ayuda += "• `!4x3 pika` : Calcular pantalla (ancho x alto modelo)\n"
    notification.answer(ayuda)

# --- 5. BUCLE DE EJECUCIÓN CON CAPTURA DE ERRORES Y REINTENTO ---
while True:
    try:
        print("🤖 Iniciando escuchador del Bot de WhatsApp...")
        bot.run_for_ever()
    except Exception as e:
        print(f"⚠️ Error en la conexión del bot: {e}. Reintentando en 10 segundos...")
        time.sleep(10)
