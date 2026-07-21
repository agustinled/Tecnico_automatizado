import streamlit as st
import math
import sqlite3
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="TECNICO AUTOMATIZADO",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "inventario_led_fijo.db"

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
    /* Fondo General Verde #006414 */
    .stApp {
        background-color: #006414 !important;
        color: #ffffff !important;
        font-family: 'Segoe UI', -apple-system, Roboto, sans-serif;
    }
    
    /* Animación de entrada menú lateral */
    @keyframes slideInLeft {
        from {
            transform: translateX(-100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    /* Fondo de la Barra Lateral desplegable */
    section[data-testid="stSidebar"] {
        background-color: #004d0f !important;
        border-right: 2px solid #00330a !important;
        animation: slideInLeft 0.4s cubic-bezier(0.25, 1, 0.5, 1);
    }

    /* Estilo del menú radio en la barra lateral (Más grande y separado) */
    div[data-testid="stSidebar"] label {
        color: #ffffff !important;
    }
    
    /* Agrandar y separar las opciones del menú desplegable */
    div[data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 12px 10px !important;
        margin-bottom: 8px !important;
        border-radius: 8px !important;
        background-color: rgba(255, 255, 255, 0.08) !important;
        font-size: 1.15rem !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
    }

    /* Header Principal */
    .header-box {
        background: #00420d;
        border-bottom: 3px solid #00ff33;
        border-radius: 10px;
        padding: 18px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }
    .header-title {
        font-family: 'Arial Black', sans-serif;
        color: #ffffff;
        font-size: 1.8rem;
        letter-spacing: 2px;
        margin: 0;
        text-transform: uppercase;
    }

    /* Tarjetas KPI de Métricas */
    .kpi-card {
        background: #00420d;
        border-left: 4px solid #00ff33;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 10px;
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #b3ffc2;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .kpi-value {
        font-size: 1.25rem;
        color: #ffffff;
        font-weight: 800;
        font-family: 'Courier New', monospace;
    }

    /* Alertas de Stock */
    .alert-ok {
        background-color: rgba(0, 255, 51, 0.15);
        border: 2px solid #00ff33;
        border-radius: 8px;
        color: #ffffff;
        padding: 15px;
        text-align: center;
        font-size: 1.1rem;
        font-weight: 800;
    }
    .alert-error {
        background-color: rgba(255, 0, 0, 0.2);
        border: 2px solid #ff4d4d;
        border-radius: 8px;
        color: #ffffff;
        padding: 15px;
        text-align: center;
        font-size: 1.1rem;
        font-weight: 800;
    }

    /* Bloques Taller */
    .taller-card {
        background: #00420d;
        border: 1px solid #00801a;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 15px;
    }
    .taller-title {
        color: #66ff85;
        font-weight: 800;
        font-size: 1.1rem;
        margin-bottom: 10px;
    }
    
    /* Contenedores de inputs */
    div[data-testid="stVerticalBlock"] > div {
        background-color: #004d0f;
        border: 1px solid #00801a;
        border-radius: 8px;
        padding: 12px;
    }
</style>
""", unsafe_allow_html=True)

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
    
    txt_cableado = f"➔ CAPACIDAD REQUERIDA: {px_totales:,} px totales\n"
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

# --- BARRA LATERAL DESPLEGABLE (SIDEBAR) ---
with st.sidebar:
    st.markdown("## MENU")
    st.markdown("---")
    opcion_menu = st.radio(
        "Navegación:",
        ["CALCULADORA DE PANTALLA", "STOCK", "GESTION TALLER LED"],
        index=0,
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.caption("SISTEMA CONTROL DE VIDEO v3.0")

# --- ENCABEZADO PRINCIPAL ---
st.markdown("""
<div class="header-box">
    <h1 class="header-title">TECNICO AUTOMATIZADO</h1>
</div>
""", unsafe_allow_html=True)

# --- VISTA 1: CALCULADORA DE PANTALLA ---
if opcion_menu == "CALCULADORA DE PANTALLA":
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("##### Configuración de Pantalla")
        txt_salon = st.selectbox("Selecciona el salón", ["SUR", "SUR LUXURY", "CENTRAL", "NORTE", "NORTE LUXURY", "GRAN SALÓN"])
        tipo = st.selectbox("Selecciona partida de pantalla", ["ROMBO", "PIKA", "UNI 500", "UNI 1000", "BLACKFACE", "NUEVA NUEVA"], index=1)
        modo = st.radio("Unidad de Medida de Entrada", ["Metros (m)", "Píxeles (px)"], horizontal=True)
        
        c_ancho, c_alto = st.columns(2)
        ancho = c_ancho.number_input("Ancho", value=4.0, step=0.5)
        alto = c_alto.number_input("Alto", value=3.0, step=0.5)
        
        confirmar = st.button("🚀 Confirmar y Registrar Salón", type="primary", use_container_width=True)

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

    with col2:
        st.markdown("##### Estado de Disponibilidad")
        if total_gabs_necesarios <= mod["disponibles_gabs"]:
            gabs_libres_restantes = mod["disponibles_gabs"] - total_gabs_necesarios
            m2_libres_restantes = gabs_libres_restantes * mod["m2_por_gab"]
            st.markdown(f"""
            <div class="alert-ok">
                ✅ DISPONIBLE<br>
                <span style="font-size: 0.9rem; font-weight: 500;">Quedan libres: {gabs_libres_restantes} gabs ({m2_libres_restantes:.2f} m²)</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            gabs_faltantes = total_gabs_necesarios - mod["disponibles_gabs"]
            m2_faltantes = gabs_faltantes * mod["m2_por_gab"]
            st.markdown(f"""
            <div class="alert-error">
                🚨 ERROR: FALTA STOCK<br>
                <span style="font-size: 0.9rem; font-weight: 500;">Faltan: {gabs_faltantes} gabs ({m2_faltantes:.2f} m²)</span>
            </div>
            """, unsafe_allow_html=True)

        kpi1, kpi2 = st.columns(2)
        with kpi1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Medida Real</div>
                <div class="kpi-value">{ancho_real:.2f}m x {alto_real:.2f}m</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Estructura</div>
                <div class="kpi-value">{gabs_ancho} x {gabs_alto} gabs</div>
            </div>
            """, unsafe_allow_html=True)

        with kpi2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Superficie</div>
                <div class="kpi-value">{m2_reales:.2f} m²</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Resolución</div>
                <div class="kpi-value">{res_ancho}x{res_alto} px</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("##### Diagrama de Datos y Señal NovaStar")
    st.text_area("Ruteado de Señal", calcular_mapa_senal(gabs_ancho, gabs_alto, px_por_gab, total_gabs_necesarios), height=200)

    if confirmar:
        if total_gabs_necesarios <= mod["disponibles_gabs"]:
            fecha_hoy = datetime.now().strftime("%d/%m %H:%M")
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO salones (nombre_salon, partida, gabs_usados, m2_usados, fecha_registro) VALUES (?, ?, ?, ?, ?)",
                           (txt_salon, tipo, total_gabs_necesarios, m2_reales, fecha_hoy))
            conn.commit()
            conn.close()
            st.toast(f"🚀 Registrado en {txt_salon}!")
            st.rerun()
        else:
            st.error("No se puede registrar: Stock insuficiente.")

# --- VISTA 2: STOCK ---
elif opcion_menu == "STOCK":
    col_stock1, col_stock2 = st.columns(2)
    with col_stock1:
        st.markdown("##### Monitoreo de Depósito")
        st.text_area("Módulos Libres / Uso / Taller", ver_reporte_deposito(), height=350)
    
    with col_stock2:
        st.markdown("##### Hojas de Ruta en Salones")
        st.text_area("Eventos Activos", ver_salones(), height=250)
        
        if st.button("🗑️ Reiniciar Ciclo Semanal", type="secondary", use_container_width=True):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM salones")
            conn.commit()
            conn.close()
            st.toast("Base de datos reseteada para la nueva semana!")
            st.rerun()

# --- VISTA 3: GESTION TALLER LED ---
elif opcion_menu == "GESTION TALLER LED":
    st.markdown("##### Control de Componentes Damnificados")
    partidas_lista = ["ROMBO", "PIKA", "UNI 500", "UNI 1000", "BLACKFACE", "NUEVA NUEVA"]
    
    for p_name in partidas_lista:
        p_init = obtener_datos_partida(p_name)
        
        st.markdown(f"""
        <div class="taller-card">
            <div class="taller-title">{p_init['nombre']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.caption("Módulos Taller")
            st.markdown(f"**{p_init['rotos_gabs']} gabs**")
            b1, b2 = st.columns(2)
            if b1.button("-", key=f"{p_name}_g_sub", use_container_width=True):
                cambiar_contador(p_name, "gabs_rotos", -1)
                st.rerun()
            if b2.button("+", key=f"{p_name}_g_add", use_container_width=True):
                cambiar_contador(p_name, "gabs_rotos", 1)
                st.rerun()

        with c2:
            st.caption("Ladrillos Reparación")
            st.markdown(f"**{p_init['ladrillos_en_reparacion']} uds**")
            b3, b4 = st.columns(2)
            if b3.button("-", key=f"{p_name}_lrep_sub", use_container_width=True):
                cambiar_contador(p_name, "ladrillos_en_reparacion", -1)
                st.rerun()
            if b4.button("+", key=f"{p_name}_lrep_add", use_container_width=True):
                cambiar_contador(p_name, "ladrillos_en_reparacion", 1)
                st.rerun()

        with c3:
            st.caption("Ladrillos Esperando")
            st.markdown(f"**{p_init['ladrillos_esperando']} uds**")
            b5, b6 = st.columns(2)
            if b5.button("-", key=f"{p_name}_lesp_sub", use_container_width=True):
                cambiar_contador(p_name, "ladrillos_esperando", -1)
                st.rerun()
            if b6.button("+", key=f"{p_name}_lesp_add", use_container_width=True):
                cambiar_contador(p_name, "ladrillos_esperando", 1)
                st.rerun()
                
        st.markdown("<br>", unsafe_allow_html=True)
