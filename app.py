import streamlit as st
import pandas as pd
import json
import time
from openai import OpenAI
from streamlit_folium import st_folium
import data_loader
import engine
import maps
import os
from pdf_generator import create_pdf
import datetime 
import logger

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
st.set_page_config(page_title="Cyclone GPT", layout="wide", page_icon="🌪️")

USERS = {"aon_user": "cyclone2026", "jhernandez": "LatamParametricTeam",
         "ccastro": "LatamParametricTeam", "yaguilar": "LatamParametricTeam",
         "jmoreno": "111", "ngonzalez": "LatamParametricTeam",
         "aacelas": "LatamParametricTeam", "rsantos": "LatamParametricTeam",
         "pferreira" : "LatamParametricTeam", "cvivian": "CateYaEsParametrica"
         }

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "messages" not in st.session_state: st.session_state.messages = []
if "inputs_cotizacion" not in st.session_state: st.session_state.inputs_cotizacion = None
if "resultados" not in st.session_state: st.session_state.resultados = None
if "hurdat_data" not in st.session_state: st.session_state.hurdat_data = data_loader.load_hurricane_data()

# REEMPLAZA CON TU API KEY REAL O USA st.secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"]) 

# ==============================================================================
# SYSTEM PROMPT (ACTUALIZADO CON REGLA DE AGRESIVO)
# ==============================================================================
SYSTEM_PROMPT = """# SYSTEM PROMPT: CONFIGURACIÓN DEL AGENTE CYCLONE GPT
## 0. REGLA SUPREMA DE INTEGRIDAD DE DATOS (NO IGNORAR)
Eres un reportero de datos, NO un analista creativo.
1. Cuando recibas datos numéricos de la herramienta `calcular_cotizacion` (Precios, RoL, Pagos Históricos), debes repetirlos CARÁCTER POR CARÁCTER.
2. TIENES PROHIBIDO redondear, estimar, "interpretar", o usar cifras de conversaciones anteriores cifras.
   - Si el motor dice "$714,230", NO escribas "$715k" ni "casi un millón". Escribe "$714,230".
3. Si el desglose dice que un círculo pagó 0, DEBES decir que pagó 0. No inventes que "pasó cerca".
4. **PRIORIDAD DE REPORTE:** El motor generará dos escenarios: "Tradicional" y "Agresivo". Tu obligación es reportar y ofrecer al usuario el **ESCENARIO AGRESIVO** (Prima Agresiva y RoL Agresivo) como la opción principal, a menos que se te pida lo contrario.

## 1. ROL Y OBJETIVO
Eres **Cyclone GPT**, un asistente técnico-actuarial experto y exclusivo para la configuración y análisis de seguros paramétricos **CIC (Catastrophe In Circle)** de Aon.
Tu propósito es configurar coberturas, validar datos técnicos, ejecutar cotizaciones (vía herramienta interna) y explicar los resultados financieros, buscando siempre la competitividad (Agresiva).

## 2. REGLAS DE INTERPRETACIÓN DE DATOS (CRÍTICO)
El motor de cálculo es estricto. Debes seguir estas reglas para evitar errores financieros:

### A. CONVERSIÓN DE UNIDADES (MPH -> KM/H)
El motor de cálculo SOLO entiende **Kilómetros por hora (km/h)**.
* **Si el usuario ingresa Millas por hora (mph):** Debes convertirlas SILENCIOSAMENTE a km/h antes de estructurar los datos.
* **Factor de conversión:** 1 mph = **1.61 km/h**.
* *Ejemplo:* Si el usuario dice "pago desde 100 mph", tú debes enviar al motor `161` (km/h).
* Al confirmar la tabla al usuario (Fase B), muéstrale los valores convertidos a km/h para evitar ambigüedades.

### B. SUGERENCIA DE TABLAS DE PAGO (DEFAULT)
Si el usuario NO proporciona una tabla de pagos específica o pide una sugerencia, **OFRECE** la siguiente "Tabla Estándar Aon":
* **Estructura Sugerida:**
    * 119 km/h (Cat 1): 10%
    * 154 km/h (Cat 2): 25%
    * 178 km/h (Cat 3): 50%
    * 209 km/h (Cat 4): 75%
    * 252 km/h (Cat 5): 100%
* **Acción:** Pregunta: *"¿Deseas utilizar la tabla estándar basada en Categorías de Huracán (Saffir-Simpson) o prefieres dictar tus propios tramos?"*

1.  **IDs Únicos Globales:** Cada círculo de cada ubicación debe tener un **ID ÚNICO e INCREMENTAL** (1, 2, 3, 4...).
    * NO uses "Círculo 1" para la Ubicación 1 y otra vez "Círculo 1" para la Ubicación 2.
    * Ejemplo correcto: Ubicación A (ID 1, ID 2), Ubicación B (ID 3, ID 4).

2.  **Interpretación de Rangos (Intervalos):**
    * Cuando el usuario defina un tramo (ej: "de 119 a 200 paga 10%"), interprétalo matemáticamente como un intervalo **Cerrado por la izquierda y Abierto por la derecha [a, b)**.
    * Significa: **Mayor o igual a 119** Y **Menor estricto a 200**.
    * El valor exacto del límite superior (ej: 200.0) pertenece al SIGUIENTE tramo.

3.  **Tabla de Pagos Explícita y NUMÉRICA:**
    * Debes crear una columna de pago para CADA ID (C1, C2, C3...).
    * **Ceros Explícitos:** Si el usuario dice "empieza a pagar desde 200 km/h", significa que de 0 a 199.99 km/h el pago es **0%**.
    * **IMPORTANTE:** Al llamar a la herramienta `calcular_cotizacion`, envía los porcentajes como **NÚMEROS** (ej: 0.05, 10, 0). **NUNCA** envíes cadenas de texto con el símbolo "%" (ej: "5%" es PROHIBIDO).

4.  **Validación de Continuidad (HUECOS Y TRASLAPES):**
    * **Detección de Huecos:** Si el usuario define tramos disconexos (ej: [200, 230] y luego [240, 300]), detecta el hueco (230-240). **ACCIÓN:** Propón una corrección cerrando el hueco (ej: extendiendo el primer tramo hasta 240) e informa al usuario.
    * **Detección de Traslapes:** Si los tramos se superponen (ej: [200, 240] y [230, 300]), detecta la colisión (230-240). **ACCIÓN:** Propón una corrección lógica (ej: cortar el primer tramo en 230) e informa al usuario.
    * **IMPORTANTE:** Nunca asumas silenciosamente. Debes explicar el error encontrado (hueco o traslape) y la solución propuesta en la Fase B para que el usuario apruebe.

5.  **Explicación Basada en EVIDENCIA (Prohibido Alucinar):**
    * Al explicar un pago histórico, **NO** asumas que el huracán cruzó todos los círculos.
    * Debes leer el campo `breakdown_text` o `detalle` que devuelve la herramienta de cálculo.
    * Solo menciona los círculos donde `pago > 0` o donde hubo intersección física confirmada por los datos.
    **VERIFICACIÓN DE ID:** El motor te entregará un "CÁLCULO ID" (ej: 14:30:05). 
   DEBES iniciar tu respuesta diciendo: "Cálculo generado [ID: 14:30:05]..." 
   Si el ID no coincide con el último entregado por la herramienta, ESTÁS ALUCINANDO.

## 3. RESTRICCIONES DE DOMINIO (ESTRICTO)
- **NO** respondas preguntas fuera del ámbito de seguros paramétricos.
- **NO** escribas ni expliques código Python/R.
- **NO** intentes generar o mostrar mapas/imágenes directamente en la ventana de chat.
- **NO** uses información de conversaciones anteriores (más de 20 minutos). Reinicia la conversación si ya ha pasado este tiempo.

## 4. COMPORTAMIENTO DE CHAT (CERO LATENCIA)
**REGLA DE ORO:** Nunca respondas con mensajes de relleno como "Entendido, voy a corregirlo", "Un momento por favor" o "Procesando cambios".
* Si el usuario te da una corrección: **GENERÁ INMEDIATAMENTE** la tabla corregida (Fase B).
* Si el usuario confirma: **EJECUTA INMEDIATAMENTE** el cálculo (Fase C).
* Tu respuesta debe contener siempre **INFORMACIÓN ÚTIL** (Tablas o Resultados), nunca solo confirmaciones de espera.

## 5. FLUJO DE TRABAJO ESTRICTO (SECUENCIAL)

Debes seguir estos pasos en orden. **TIENES PROHIBIDO SALTARTE PASOS.**

### FASE A: Recolección de Datos
Interactúa en lenguaje natural para obtener:
1.  **Nombre del Cliente:** Pregunta obligatoriamente el nombre del cliente o proyecto si no se ha mencionado. (Aunque el usuario lo ingrese en el sidebar, confírmalo verbalmente).
2.  **Ubicaciones:** Latitud, Longitud, Radio (km), Límite (USD).
3.  **Tabla de Pagos:** Tramos de velocidad y % de pago.
4.  **Parámetros:** Límite evento/agregado.
5.  **Factor asimmétrico:** Asume siempre que es 0.5, no preguntes al usuario.

### FASE B: Validación y Confirmación (STOPPING POINT)
**REGLA CRÍTICA:** Aunque tengas todos los datos, **NO** ejecutes la herramienta `ejecutar_cotizacion_cic` todavía.
Tu tarea en este paso es OBLIGATORIAMENTE:
1.  **Validar internamente:**
    - Coordenadas válidas y Radios > 0.
    - IDs consecutivos globales.
    - **VERIFICACIÓN DE CONTINUIDAD:** Revisa explícitamente si existen huecos o traslapes. Si los hay, alerta al usuario y propón la corrección.
2.  **Mostrar Matriz de Confirmación:** Presenta la estructura EXACTA que enviarás al motor para que el usuario la audite visualmente:
    * **Tabla 1: Mapeo de IDs.** Columnas: [ID Global | Ubicación | Radio | Límite].
    * **Tabla 2: Matriz de Pagos Completa.** Columnas: [Velocidad (>=) | C1 | C2 | C3...].
    * *Nota:* Asegúrate de mostrar **0%** explícitamente en los tramos donde no hay pago.
    * ** Mostrar el límite por evento y el límite agregado que el usuario te definió.
3.  **Solicitar Confirmación:** Pregunta explícitamente: *"He estructurado los datos como se muestra arriba. ¿Los IDs y porcentajes son correctos para proceder?"*.
4.  **DETENERTE.** Espera la respuesta del usuario antes de pasar a la Fase C.

### FASE C: Ejecución y Respuesta
**SOLO** tras recibir la confirmación explícita del usuario:
1.  Ejecuta `calcular_cotizacion`.
2.  **Presentación de Resultados (MODO AGRESIVO):**
    - Muestra la **Prima Agresiva** y el **RoL Agresivo** como resultados principales.
    - Menciona explícitamente que estás presentando el "Escenario Agresivo de Suscripción".
    - **REITERACIÓN DE PARÁMETROS:** Inmediatamente debajo de los precios, vuelve a mostrar las tablas de **Ubicaciones** y **Matriz de Pagos** que se utilizaron para el cálculo.
    - **IMPORTANTE:** NO muestres el JSON crudo. Explica los resultados.

### FASE D: Interacción Post-Resultados (Mapas y PDF)
1.  Informa que los mapas se generaron en segundo plano.
2.  **Acción Proactiva:** Revisa la lista de eventos con pago y pregunta:
    > *"He identificado pagos históricos en años como [Año X]. ¿Te gustaría visualizar la trayectoria detallada de algún huracán específico?"*
3.  **Explicación Forense de Pagos (ESTRICTO):**
    Si el usuario pregunta por un huracán específico (ej: María), **debes leer el detalle del JSON de salida (breakdown_text)** y construir la explicación así:
    * Identifica qué círculos específicos intersectó el huracán.
    * Menciona la **Velocidad Máxima** registrada EN ESE CÍRCULO.
    * Indica el **% de pago** que corresponde a esa velocidad según la tabla.
    * Calcula el monto monetario por círculo y la suma total.
    * Si la suma supera el límite por evento, explica explícitamente que se aplicó el tope (Cap).
    * *Ejemplo de respuesta esperada:* "El Huracán María cruzó el **Círculo 1 (Ubicación 1)** registrando vientos de **215 km/h**. Según tu tabla, esto activa el tramo de 20-30%, pagando **$200k**. En el **Círculo 3**, aunque pasó cerca, la velocidad fue de 100 km/h, lo cual no activa pago."

## 6. FORMATO DE RESPUESTA
- Usa Markdown para tablas.
- Cifras: `1,000,000.00`.
- Porcentajes en TEXTO: `15.00%`. (Pero en la herramienta usa números).
"""

if not st.session_state.messages:
    st.session_state.messages.append({"role": "system", "content": SYSTEM_PROMPT})

# DEFINICIÓN DE HERRAMIENTAS
tools = [{
    "type": "function",
    "function": {
        "name": "calcular_cotizacion",
        "description": "Calcula primas usando IDs únicos y columnas de pago específicas.",
        "parameters": {
            "type": "object",
            "properties": {
                "ubicaciones": { 
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "id": {"type": "integer"}, 
                            "lat": {"type": "number"}, 
                            "lon": {"type": "number"}, 
                            "radio": {"type": "number"}, 
                            "limite": {"type": "number"}
                        }, 
                        "required": ["id", "lat", "lon", "radio", "limite"]
                    }
                },
                "tabla_pagos": { 
                    "type": "array",
                    "description": "Lista de filas con 'min_speed' y columnas de pago C{id} (C1, C2...). Los valores deben ser NÚMEROS.",
                    "items": {
                        "type": "object", 
                        "properties": {
                            "min_speed": {"type": "number"}
                        }, 
                        "additionalProperties": {"type": "number"}, 
                        "required": ["min_speed"]
                    }
                },
                "limite_evento": {"type": "number"},
                "limite_agregado": {"type": "number"},
                "factor_asimetrico": {"type": "number", "default": 0.5}
            },
            "required": ["ubicaciones", "tabla_pagos", "limite_evento", "limite_agregado"]
        }
    }
}]

# ==============================================================================
# CSS (ESTILOS)
# ==============================================================================
def load_css():
    st.markdown("""
    <style>
        /* Fondo general */
        [data-testid="stAppViewContainer"] {
            background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.8)), 
            url('https://images.unsplash.com/photo-1605727216801-e27ce1d0cc28?q=80&w=2671&auto=format&fit=crop');
            background-size: cover; 
            background-attachment: fixed;
            background-position: center;
        }
        section[data-testid="stSidebar"] {
            background-color: rgba(0, 0, 0, 0.5);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        header[data-testid="stHeader"] { background-color: transparent !important; }
        
        /* Textos */
        div[data-testid="stMetricValue"] {
            color: #ffffff !important; 
            font-size: 1.8rem !important;
            font-weight: bold !important;
        }
        h1, h2, h3, h4, h5, h6, label, .stMarkdown, p, li, span { 
            color: #ffffff !important; 
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }
        
        /* Inputs */
        input, textarea, select {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            caret-color: #000000 !important;
        }
        
        /* Botones */
        div.stButton > button {
            background-color: #0056D2 !important; 
            color: #ffffff !important; 
            border: none !important;
            font-weight: bold !important;
        }
        div.stButton > button:hover {
            background-color: #0046a8 !important;
        }
        
        /* Dropdowns */
        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            color: #000000 !important;
        }
        div[data-baseweb="select"] span, div[data-baseweb="select"] svg {
            color: #000000 !important;
            fill: #000000 !important;
        }
        ul[data-baseweb="menu"] { background-color: #ffffff !important; }
        li[role="option"] div { color: #000000 !important; }
        
        /* --- CORRECCIÓN DE TABLA --- */
        div[data-testid="stDataFrame"] {
            background-color: rgba(255, 255, 255, 0.95) !important;
            border-radius: 10px;
            padding: 15px;
            width: 100%;
            overflow: hidden; 
        }
        div[data-testid="stDataFrame"] div, div[data-testid="stDataFrame"] span {
            color: #000000 !important;
            text-shadow: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

load_css()

# ==============================================================================
# LÓGICA PRINCIPAL
# ==============================================================================

def login_form():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; font-size: 4rem;'>🌪️ Cyclone GPT</h1>", unsafe_allow_html=True)
        with st.form("login"):
            user = st.text_input("Usuario")
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR", use_container_width=True):
                if user in USERS and USERS[user] == pwd:
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    
                    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    st.session_state.resultados = None
                    st.session_state.inputs_cotizacion = None
                    
                    st.rerun()
                else: st.error("Error credenciales")

def main_app():
    # HEADER
    c1, c2 = st.columns([4, 1])
    with c1: st.title("🌪️ Cyclone GPT")
    with c2:
        if os.path.exists("logo_aon.png"): st.image("logo_aon.png", width=120)
    

    # exista antes de llamar a cualquier cálculo o log.
    with st.sidebar:
        st.write(f"👤 **{st.session_state.username}**")
        client_name = st.text_input("Nombre del Cliente", value="Cliente General")
    # ==========================================================================

    col_chat, col_dash = st.columns([1, 1.4], gap="large")

    # --- COLUMNA IZQUIERDA: CHAT ---
    with col_chat:
        st.subheader("Asistente")
        chat_container = st.container(height=500)
        
        # Mostrar historial
        with chat_container:
            for msg in st.session_state.messages:
                if isinstance(msg, dict): 
                    role, content = msg.get("role"), msg.get("content")
                else: 
                    role, content = msg.role, msg.content
                
                if role not in ["system", "tool"] and content:
                    with st.chat_message(role):
                        st.markdown(content)
        
        # Input de usuario
        if prompt := st.chat_input("Escribe tu instrucción..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with chat_container:
                st.chat_message("user").markdown(prompt)
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=st.session_state.messages,
                    tools=tools
                )
                msg_ai = response.choices[0].message
                st.session_state.messages.append(msg_ai)
                
                if msg_ai.tool_calls:
                    for tool_call in msg_ai.tool_calls:
                        if tool_call.function.name == "calcular_cotizacion":
                            try:
                                # 1. LIMPIEZA PREVENTIVA (NUEVO)
                                # Borramos cualquier resultado anterior de la memoria inmediata
                                st.session_state.resultados = None 
                
                                args = json.loads(tool_call.function.arguments)
                                st.session_state.inputs_cotizacion = args
                                
                                with st.spinner("Ejecutando motor de cálculo..."):
                                    # Preparar DataFrames para el motor
                                    df_locs = pd.DataFrame(args['ubicaciones'])
                                    df_locs = df_locs.rename(columns={
                                        'id': 'ID', 'lat': 'Lat', 'lon': 'Lon', 
                                        'radio': 'Radius', 'limite': 'Limit'
                                    })
                                    
                                    df_pagos = pd.DataFrame(args['tabla_pagos'])
                                    
                                    # Ejecutar Engine
                                    resultado = engine.run_engine_calculation(
                                        st.session_state.hurdat_data,
                                        df_locs,
                                        df_pagos,
                                        float(args['limite_evento']),
                                        float(args['limite_agregado']),
                                        float(args.get('factor_asimetrico', 0.5))
                                    )
                                    
                                    st.session_state.resultados = resultado
                                    stats = resultado['stats']
                                    
                                    # ==========================================
                                    # NUEVO: GUARDAR LOG EN GOOGLE SHEETS
                                    # ==========================================
                                    logger.log_to_sheets(
                                        st.session_state.username,
                                        args,
                                        resultado,
                                        client_name # <--- Agregamos esto
                                    )
                                    # ==========================================


                                    # --- CONSTRUCCIÓN DEL MENSAJE PARA LA IA (MODO AGRESIVO) ---
                                    detalle_historial = ""
                                    if resultado['events']:
                                        detalle_historial = "\n\nDETALLE DE EVENTOS HISTÓRICOS (ÚSALO PARA EXPLICAR):"
                                        for ev in resultado['events']:
                                            detalle_historial += f"\n- Año {ev['Year']} Huracán {ev['Name']}: Pago Final ${ev['PagoEventoAdj']:,.0f}. DETALLE TÉCNICO: {ev.get('breakdown_text', 'N/A')}"
                                    else:
                                        detalle_historial = "\n\nNo hubo eventos históricos con pago."

                                    calculation_id = datetime.datetime.now().strftime("%H:%M:%S")
                                    # AQUÍ INYECTAMOS LAS VARIABLES AGRESIVAS AL LLM
                                    output_content = (
                                        f"CÁLCULO ID: {calculation_id} (USAR ESTE ID EN LA RESPUESTA).\n" # <--- NUEVO
                                        f"Cálculo Exitoso.\n"
                                        f"DATOS DEL ESCENARIO AGRESIVO (PRIORITARIO):\n"
                                        f"- Prima Agresiva: ${stats['Prima_Agresiva']:,.2f}\n"
                                        f"- RoL Agresivo: {stats['RoL_Agresivo_Pct']}\n"
                                        f"(Referencia Tradicional: Prima ${stats['Prima_Neta_Trad']:,.2f}, RoL {stats['Net_RoL_Pct']})\n"
                                        f"{detalle_historial}"
                                    )
                                    
                                    st.session_state.messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "content": output_content
                                    })
                                    
                            except Exception as e:
                                err_msg = f"Error en cálculo: {str(e)}"
                                st.error(err_msg)
                                st.session_state.messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": err_msg
                                })

                    final_response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=st.session_state.messages
                    )
                    final_msg = final_response.choices[0].message
                    st.session_state.messages.append(final_msg)
                    
                    with chat_container:
                        st.chat_message("assistant").markdown(final_msg.content)
                
                else:
                    with chat_container:
                        st.chat_message("assistant").markdown(msg_ai.content)

            except Exception as e:
                st.error(f"Error de conexión o API: {e}")
            
            st.rerun()

    # --- COLUMNA DERECHA: DASHBOARD (MODO AGRESIVO) ---
    with col_dash:
        st.subheader("📊 Panel de Resultados")
        
        if st.session_state.resultados:
            res = st.session_state.resultados
            stats = res['stats']
            
            # Métricas: AHORA MUESTRAN AGRESIVO
            k1, k2, k3 = st.columns(3)
            k1.metric("Límite Agregado", f"${st.session_state.inputs_cotizacion['limite_agregado']:,.0f}")
            # CAMBIO AQUI: Variables agresivas
            k2.metric("Prima", f"${stats['Prima_Agresiva']:,.2f}")
            k3.metric("RoL", stats['RoL_Agresivo_Pct'])
            
            st.divider()
            
            # Tabla Histórica
            st.markdown("#### 📜 Pagos Históricos (As-If)")
            events = res['events']
            
            if events:
                df_ev = pd.DataFrame(events)
                df_ev_show = df_ev[['Year', 'Name', 'PagoEventoAdj']].copy()
                
                st.dataframe(
                    df_ev_show.style.format({"PagoEventoAdj": "${:,.2f}"}),
                    column_config={
                        "Year": st.column_config.NumberColumn("Año", format="%d", width="medium"),
                        "Name": st.column_config.TextColumn("Huracán", width="medium"),
                        "PagoEventoAdj": st.column_config.Column("Monto Pagado", width="medium"),
                    },
                    hide_index=True, 
                    use_container_width=False, 
                    height=250
                )
                
                # Selector para Mapa
                st.divider()
                st.markdown("#### 🗺️ Mapa de Trayectoria")
                
                raw_locs = st.session_state.inputs_cotizacion['ubicaciones']
                opciones_mapa = df_ev.apply(lambda x: f"{x['Year']} - {x['Name']} (${x['PagoEventoAdj']:,.0f})", axis=1).tolist()
                seleccion = st.selectbox("Seleccionar Evento para visualizar:", opciones_mapa)
                
                hid_seleccionado = None
                if seleccion:
                    idx = opciones_mapa.index(seleccion)
                    hid_seleccionado = df_ev.iloc[idx]['HuracanID']
                
                if hid_seleccionado:
                    with st.spinner("Generando mapa interactivo..."):
                        m = maps.generate_interactive_map(
                            st.session_state.hurdat_data, 
                            raw_locs, 
                            hid_seleccionado
                        )
                        if m:
                            st_folium(m, height=400, use_container_width=True)
                        else:
                            st.warning("No se pudo generar el mapa.")
            else:
                st.info("Ningún evento histórico activó la cobertura con estos parámetros.")
                
            st.markdown("---")
            st.caption("Cifras mostradas corresponden al escenario tipo A de suscripción.")

        else:
            st.info("Esperando configuración...")
            st.markdown("""
            <div style="text-align: center; color: white; padding: 40px; border: 1px dashed rgba(255,255,255,0.3); border-radius: 10px;">
                <p style="font-size: 1.2rem;">👋 ¡Hola!</p>
                <p>Describe tu cobertura en el chat para comenzar.</p>
                <p style="font-size: 0.8rem; color: #aaa;">Ej: "Ubicación en San Juan, radio 40km, límite 1M..."</p>
            </div>
            """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        st.write(f"👤 **{st.session_state.username}**")
        

        if st.button("✨ Nueva Cotización", use_container_width=True):
            st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            st.session_state.resultados = None
            st.session_state.inputs_cotizacion = None
            st.rerun()
        
        if st.session_state.resultados:
            st.divider()
            st.write("📥 **Exportar**")
            try:
                pdf_bytes = create_pdf(
                    st.session_state.inputs_cotizacion,
                    st.session_state.resultados,
                    client_name
                )
                st.download_button(
                    label="📄 Descargar PDF",
                    data=pdf_bytes,
                    file_name="Cotizacion_CycloneGPT.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error PDF: {e}")
        
        st.divider()
        if st.button("Cerrar Sesión"):
            st.session_state.clear() 
            st.rerun()

if __name__ == "__main__":
    if st.session_state.logged_in: main_app()
    else: login_form()