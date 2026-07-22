import math
import sqlite3
import re
from whatsapp_chatbot_python import GreenAPIBot, Notification

# --- CONEXIÓN A LA BASE DE DATOS COMPARTIDA ---
DB_NAME = "inventario_led_fijo.db"

def obtener_datos_partida(partida):
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

def ver_reporte_stock():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT partida FROM inventario")
    partidas = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    reporte = "📦 *REPORTE DE DEPÓSITO Y STOCK*\n----------------------------------\n"
    for p_id in partidas:
        p = obtener_datos_partida(p_id)
        reporte += f"🔹 *{p['nombre']}*\n"
        reporte += f"  • Libres en cajón: {p['disponibles_gabs']} gabs ({p['disponibles_gabs']*p['m2_por_gab']:.2f} m²)\n"
        reporte += f"  • En uso salones: {p['en_uso_gabs']} gabs\n"
        reporte += f"  • En Taller: {p['rotos_gabs']} gabs\n"
        reporte += f"----------------------------------\n"
    return reporte

def ver_reporte_taller():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT partida FROM inventario")
    partidas = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    reporte = "🛠️ *REPORTE DE COMPONENTES EN TALLER*\n----------------------------------\n"
    for p_id in partidas:
        p = obtener_datos_partida(p_id)
        if p['rotos_gabs'] > 0 or p['ladrillos_en_reparacion'] > 0 or p['ladrillos_esperando'] > 0:
            reporte += f"🔸 *{p['nombre']}*\n"
            reporte += f"  • Módulos rotos: {p['rotos_gabs']} gabs\n"
            reporte += f"  • Ladrillos en reparación: {p['ladrillos_en_reparacion']}\n"
            reporte += f"  • Ladrillos esperando rep: {p['ladrillos_esperando']}\n"
            reporte += f"----------------------------------\n"
    return reporte

# --- INICIALIZACIÓN DEL BOT ---
# Usamos credenciales de instancia (se configuran gratis)
bot = GreenAPIBot(
    "ID_INSTANCIA_AQUI", "TOKEN_AQUI"
)

# --- MANEJADOR DE MENSAJES DEL GRUPO ---
@bot.router.message()
def procesar_mensaje(notification: Notification) -> None:
    texto = notification.message_text.strip().lower()
    
    # Solo responder si el mensaje empieza con '!'
    if not texto.startswith("!"):
        return

    # COMANDO: !stock
    if texto == "!stock":
        notification.answer(ver_reporte_stock())
        return

    # COMANDO: !taller
    if texto == "!taller":
        notification.answer(ver_reporte_taller())
        return

    # COMANDO: !pantalla o !4x3 pika (Ejemplo: !4x3 pika)
    # Patrón para detectar medidas tipo "!4x3 pika" o "!5x2.5 rombo"
    match = re.match(r"^!(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s+(.+)$", texto)
    if match:
        ancho = float(match.group(1))
        alto = float(match.group(2))
        modelo_buscado = match.group(3).strip().upper()
        
        # Mapear nombre rápido a partida de la BD
        mapa_modelos = {
            "PIKA": "PIKA", "ROMBO": "ROMBO", "UNI500": "UNI 500",
            "UNI 500": "UNI 500", "UNI1000": "UNI 1000", "UNI 1000": "UNI 1000",
            "BLACKFACE": "BLACKFACE", "NUEVA": "NUEVA NUEVA"
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
        
        # Cálculo de líneas Cat6
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

    # MENSAJE DE AYUDA SI EL COMANDO NO SE RECONOCE
    ayuda = "🤖 *COMANDOS DEL BOT TÉCNICO*\n"
    ayuda += "• `!stock` : Ver módulos libres y en uso\n"
    ayuda += "• `!taller` : Ver componentes rotos\n"
    ayuda += "• `!4x3 pika` : Calcular pantalla (ancho x alto modelo)\n"
    notification.answer(ayuda)

bot.run_for_ever()
