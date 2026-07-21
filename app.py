import streamlit as st
import math
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA PARA CELULAR ---
st.set_page_config(
    page_title="TÉCNICO AUTOMÁTICO DE VIDEO",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="collapsed"
)

DB_NAME = "inventario_led_fijo.db"

# --- BASE DE DATOS LOCAL ---
def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS inventario")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            partida TEXT PRIMARY KEY,
            nombre_largo TEXT,
            ancho_mm REAL,
            alto_mm REAL,
            px_ancho INTEGER,
            px_alto INTEGER,
            gabs_comprados_total INTEGER,
            gabs_rotos INTEGER,
            ladrillos_en_reparacion INTEGER DEFAULT 0,
            ladrillos_esperando INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS salones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_salon TEXT,
            partida TEXT,
            gabs_usados INTEGER,
            m2_usados REAL,
            fecha_registro TEXT
        )
    ''')
    datos_iniciales = [
        ("ROMBO", "ROMBO (0.5x0.5m)", 500, 500, 128, 128, 192, 5, 0, 0),
        ("PIKA", "PIKA (0.5x0.5m)", 500, 500, 128, 128, 392, 10, 0, 0),
        ("UNI 500", "UNI 500 ÁNGULO (0.5x0.5m)", 500, 500, 128, 128, 240, 0, 0, 0),
        ("UNI 1000", "UNI 1000 (0.5x1m)", 500, 1000, 128, 256, 480, 0, 0, 0),
        ("BLACKFACE", "BLACKFACE (1x1m)", 1000, 1000, 240, 240, 98, 0, 0, 0),
        ("NUEVA NUEVA", "NUEVA NUEVA (1x1m)", 1000, 1000, 240, 240, 56, 0, 0, 0)
    ]
    cursor.executemany("INSERT INTO inventario VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", datos_iniciales)
    conn.commit()
    conn.close()

if "bd_lista" not in st.session_state:
    inicializar_bd()
    st.session_state["bd_lista"] = True

def obtener_datos_partida(partida):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, 
               gabs_comprados_total, gabs_rotos, ladrillos_en_reparacion, ladrillos_esperando 
        FROM inventario WHERE partida=?
    """, (partida,))
    res = cursor.fetchone()
    cursor.execute("SELECT SUM(gabs_usados) FROM salones WHERE partida=?", (partida,))
    gabs_en_uso = cursor.fetchone()[0] or 0
    conn.close()
    
    nombre_largo, ancho_mm, alto_mm, px_ancho, px_alto, total_gabs, gabs_rotos, lad_rep, lad_esp = res
    ancho_m = ancho_mm / 1000.0
    alto_m = alto_mm / 1000.0
    m2_por_gab = ancho_m * alto_m
    gabs_funcionando_ok = total_gabs - gabs_rotos
    gabs_disponibles_en_cajon = gabs_funcionando_ok - gabs_en_uso
    
    return {
        "nombre": nombre_largo, "ancho_m": ancho_m, "alto_m": alto_m,
        "px_ancho": px_ancho, "px_alto": px_alto, "m2_por_gab": m2_por_gab,
        "total_gabs": total_gabs, "rotos_gabs": gabs_rotos,
        "en_uso_gabs": gabs_en_uso, "disponibles_gabs": gabs_disponibles_en_cajon,
        "ladrillos_en_reparacion": lad_rep, "ladrillos_esperando": lad_esp
    }

def cambiar_contador(partida, campo, delta):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if campo == "gabs_rotos":
        cursor.execute("UPDATE inventario SET gabs_rotos = MAX(0, gabs_rotos + ?) WHERE partida=?", (delta, partida))
    elif campo == "ladrillos_en_reparacion":
        cursor.execute("UPDATE inventario SET ladrillos_en_reparacion = MAX(0, ladrillos_en_reparacion + ?) WHERE partida=?", (delta, partida))
    elif campo == "ladrillos_esperando":
        cursor.execute("UPDATE inventario SET ladrillos_esperando = MAX(0, ladrillos_esperando + ?) WHERE partida=?", (delta, partida))
    conn.commit()
    conn.close()

def calcular_mapa_senal(gabs_ancho, gabs_alto, px_por_gab, total_gabs):
    limite_puerto = 650000
    px_totales = total_gabs * px_por_gab
    cables_necesarios = math.ceil(px_totales / limite_puerto)
    gabs_por_cable = math.floor(total_gabs / cables_necesarios) if cables_necesarios > 0 else total_gabs
    
    txt_cableado = f"[DIAGRAMA DE SEÑAL NOVASTAR]\n"
    txt_cableado += f"➔ CAPACIDAD REQUERIDA: {px_totales:,} px totales\n"
    txt_cableado += f"➔ CABLES MAIN NECESARIOS: {cables_necesarios} lineas Cat6 independientes\n"
    
    restante = total_gabs
    for i in range(cables_necesarios):
        linea_gabs = gabs_por_cable if i < cables_necesarios - 1 else restante
        restante -= linea_gabs
        txt_cableado += f"  • Puerto {i+1} (Main {i+1}): Carga {linea_gabs} modulos ({linea_gabs * px_por_gab:,} px)\n"
    
    txt_cableado += f"--------------------------------------------------\n"
    txt_cableado += f"[MAPA VISUAL DE RUTEO SERRAT]\n\n"
    
    esquema = ""
    for fila in range(gabs_alto - 1, -1, -1):
        fila_txt = f"Fila {fila+1:02d}:  "
        modulos_fila = []
        for col in range(gabs_ancho):
            if fila % 2 == 0:
                icon = " [▲ IN/IN] " if fila == 0 else " [▲ UP] " if col == 0 else " ➔ [MOD] "
            else:
                icon = " [▲ UP] " if col == gabs_ancho - 1 else " [MOD] 🠔 "
            modulos_fila.append(icon)
        if fila % 2 != 0:
            modulos_fila.reverse()
        esquema += fila_txt + "".join(modulos_fila) + "\n"
        
    txt_cableado += esquema
    return txt_cableado

def ver_reporte_deposito():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT partida FROM inventario")
    partidas = [row[0] for row in cursor.fetchall()]
    conn.close()
    reporte = ""
    for p_id in partidas:
        p = obtener_datos_partida(p_id)
        reporte += f"[PARTIDA: {p['nombre']}]\n"
        reporte += f"  • DISPONIBLES EN CAJÓN : {p['disponibles_gabs']} gabs ({p['disponibles_gabs']*p['m2_por_gab']:.2f} m²)\n"
        reporte += f"  • ASIGNADOS EN SALÓN   : {p['en_uso_gabs']} gabs ({p['en_uso_gabs']*p['m2_por_gab']:.2f} m²)\n"
        reporte += f"  • MÓDULOS EN TALLER    : {p['rotos_gabs']} gabs ({p['rotos_gabs']*p['m2_por_gab']:.2f} m²)\n"
        reporte += f"  • HARDWARE TOTAL NETO  : {p['total_gabs']} gabs ({p['total_gabs']*p['m2_por_gab']:.2f} m²)\n"
        if p['ladrillos_en_reparacion'] > 0 or p['ladrillos_esperando'] > 0:
            reporte += f"  • DETALLE: {p['ladrillos_en_reparacion']} lad. en reparac. / {p['ladrillos_esperando']} esperando\n"
        reporte += f"--------------------------------------------------\n"
    return reporte

def ver_salones():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_salon, partida, gabs_usados, m2_usados, fecha_registro FROM salones")
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return "REGISTRO: No existen puestas activas."
    txt = ""
    for row in rows:
        txt += f"• [{row[4]}] SECTOR: {row[0]} ➔ {row[1]}: {row[2]} gabs ({row[3]:.2f} m²)\n"
    return txt

# --- ENCABEZADO ---
st.markdown("<h1 style='text-align: center; color: white;'>TÉCNICO AUTOMÁTICO DE VIDEO</h1>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🧮 CALCULADOR", "📦 STOCK EN TIEMPO REAL", "🛠️ TALLER"])

# --- TAB 1: CALCULADOR ---
with tab1:
    st.subheader("Parámetros de la Solicitud")
    col1, col2 = st.columns(2)
    with col1:
        txt_salon = st.selectbox("Ubicación / Salón de Destino", ["SUR", "SUR LUXURY", "CENTRAL", "NORTE", "NORTE LUXURY", "GRAN SALÓN"])
        tipo = st.selectbox("Modelo de Partida LED", ["ROMBO", "PIKA", "UNI 500", "UNI 1000", "BLACKFACE", "NUEVA NUEVA"], index=1)
    with col2:
        modo = st.radio("Unidad de Medida de Entrada", ["Metros (m)", "Píxeles (px)"])
        ancho = st.number_input("Dimensión Ancho", value=4.0, step=0.5)
        alto = st.number_input("Dimensión Alto", value=3.0, step=0.5)
    
    col_btn1, col_btn2 = st.columns(2)
    comprobar = col_btn1.button("🔍 Comprobar Stock", use_container_width=True)
    confirmar = col_btn2.button("🚀 Confirmar y Registrar", type="primary", use_container_width=True)
    
    mod = obtener_datos_partida(tipo)
    if modo == "Metros (m)":
        gabs_ancho = math.ceil(ancho / mod["ancho_m"])
        gabs_alto = math.ceil(alto / mod["alto_m"])
    else:
        gabs_ancho = math.ceil(ancho / mod["px_ancho"])
        gabs_alto = math.ceil(alto / mod["px_alto"])
        
    total_gabs_necesarios = gabs_ancho * gabs_alto
    ancho_real = gabs_ancho * mod["ancho_m"]
    alto_real = gabs_alto * mod["alto_m"]
    m2_reales = total_gabs_necesarios * mod["m2_por_gab"]
    res_ancho = gabs_ancho * mod["px_ancho"]
    res_alto = gabs_alto * mod["px_alto"]
    px_por_gab = mod["px_ancho"] * mod["px_alto"]
    
    st.markdown("---")
    if total_gabs_necesarios <= mod["disponibles_gabs"]:
        gabs_libres_restantes = mod["disponibles_gabs"] - total_gabs_necesarios
        m2_libres_restantes = gabs_libres_restantes * mod["m2_por_gab"]
        st.success(f"✅ DISPONIBLE\nQuedan libres en depósito: {gabs_libres_restantes} gabs ({m2_libres_restantes:.2f} m²)")
    else:
        gabs_faltantes = total_gabs_necesarios - mod["disponibles_gabs"]
        m2_faltantes = gabs_faltantes * mod["m2_por_gab"]
        st.error(f"🚨 ERROR: FALTA STOCK\nFaltan fabricar para este armado: {gabs_faltantes} gabs ({m2_faltantes:.2f} m²)")

    reporte = f"➔ ESTRUCTURA ARMADA: {gabs_ancho} x {gabs_alto} módulos\n"
    reporte += f"➔ MEDIDA REAL DE ARMADO: {ancho_real}m ancho x {alto_real}m alto ({m2_reales:.2f} m²)\n"
    reporte += f"➔ HARDWARE REQUERIDO: {total_gabs_necesarios} gabinetes\n"
    reporte += f"➔ RESOLUCIÓN CALCULADA: {res_ancho} x {res_alto} px\n"
    reporte += f"--------------------------------------------------\n"
    reporte += f"➔ DISPONIBLE NETO EN DEPÓSITO ANTES DEL SHOW: {mod['disponibles_gabs']} gabs ({mod['disponibles_gabs'] * mod['m2_por_gab']:.2f} m²)"

    st.text_area("Dimensiones de Estructura Calculada", reporte, height=180)
    st.text_area("Distribución de Cables de Datos Main", calcular_mapa_senal(gabs_ancho, gabs_alto, px_por_gab, total_gabs_necesarios), height=250)

    if confirmar:
        if total_gabs_necesarios <= mod["disponibles_gabs"]:
            fecha_hoy = datetime.now().strftime("%d/%m %H:%M")
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO salones (nombre_salon, partida, gabs_usados, m2_usados, fecha_registro) VALUES (?, ?, ?, ?, ?)",
                           (txt_salon, tipo, total_gabs_necesarios, m2_reales, fecha_hoy))
            conn.commit()
            conn.close()
            st.toast(f"🎉 Registrado en {txt_salon}!")
            st.rerun()
        else:
            st.error("Sin stock suficiente.")

# --- TAB 2: STOCK ---
with tab2:
    st.subheader("Monitoreo de Depósito")
    st.text_area("Módulos Libres / Uso / Taller", ver_reporte_deposito(), height=300)
    st.subheader("Registro Semanal de Eventos")
    st.text_area("Hojas de Ruta Operativas", ver_salones(), height=200)
    
    if st.button("🗑️ Reiniciar Ciclo Semanal (Resetear Salones)", type="secondary"):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM salones")
        conn.commit()
        conn.close()
        st.toast("Semana reseteada!")
        st.rerun()

# --- TAB 3: TALLER ---
with tab3:
    st.subheader("Registro General de Componentes Damnificados")
    partidas_lista = ["ROMBO", "PIKA", "UNI 500", "UNI 1000", "BLACKFACE", "NUEVA NUEVA"]
    
    for p_name in partidas_lista:
        p_init = obtener_datos_partida(p_name)
        st.write(f"### {p_init['nombre']}")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.caption("Módulos Taller")
            st.write(f"**{p_init['rotos_gabs']}**")
            b1, b2 = st.columns(2)
            if b1.button("-", key=f"{p_name}_g_sub"):
                cambiar_contador(p_name, "gabs_rotos", -1)
                st.rerun()
            if b2.button("+", key=f"{p_name}_g_add"):
                cambiar_contador(p_name, "gabs_rotos", 1)
                st.rerun()

        with c2:
            st.caption("Ladrillos Reparación")
            st.write(f"**{p_init['ladrillos_en_reparacion']}**")
            b3, b4 = st.columns(2)
            if b3.button("-", key=f"{p_name}_lrep_sub"):
                cambiar_contador(p_name, "ladrillos_en_reparacion", -1)
                st.rerun()
            if b4.button("+", key=f"{p_name}_lrep_add"):
                cambiar_contador(p_name, "ladrillos_en_reparacion", 1)
                st.rerun()

        with c3:
            st.caption("Ladrillos Esperando")
            st.write(f"**{p_init['ladrillos_esperando']}**")
            b5, b6 = st.columns(2)
            if b5.button("-", key=f"{p_name}_lesp_sub"):
                cambiar_contador(p_name, "ladrillos_esperando", -1)
                st.rerun()
            if b6.button("+", key=f"{p_name}_lesp_add"):
                cambiar_contador(p_name, "ladrillos_esperando", 1)
                st.rerun()
        st.markdown("---")
