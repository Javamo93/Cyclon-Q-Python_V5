import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import datetime
import logger

def log_to_sheets(username, inputs, results, client_name):
    """
    Guarda los datos de la cotización en Google Sheets.
    Requiere que st.secrets["gcp_service_account"] esté configurado.
    """
    # Verificación de seguridad para no romper la app si no hay credenciales
    if "gcp_service_account" not in st.secrets:
        print("Advertencia: No hay credenciales de Google Sheets configuradas en secrets.")
        return

    try:
        # 1. Configuración de credenciales
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)

        # 2. Abrir la hoja de cálculo
        # Define el nombre de tu hoja en secrets o usa "Cyclone_Logs" por defecto
        sheet_name = st.secrets.get("SHEET_NAME", "Cyclone_Logs")
        sheet = client.open(sheet_name).sheet1

        # 3. Preparar los datos
        stats = results.get('stats', {})
        
        # Convertimos objetos complejos a texto JSON para que quepan en una celda
        locs_str = json.dumps(inputs.get('ubicaciones', []), ensure_ascii=False)
        pagos_str = json.dumps(inputs.get('tabla_pagos', []), ensure_ascii=False)

        # Estructura de la fila
        row = [
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            username,
            client_name,  # <--- NUEVO: Agregamos el cliente en la columna 3
            stats.get('Prima_Agresiva', 0),
            stats.get('RoL_Agresivo_Pct', '0%'),
            inputs.get('limite_evento', 0),
            inputs.get('limite_agregado', 0),
            inputs.get('factor_asimetrico', 0.5),
            locs_str,
            pagos_str
        ]

        # 4. Enviar a Google
        sheet.append_row(row)
        
    except Exception as e:
        # Imprimimos el error en consola para no interrumpir al usuario en la interfaz
        print(f"Error registrando en Google Sheets: {e}")