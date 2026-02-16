import pandas as pd
import numpy as np
import streamlit as st
import os

@st.cache_resource
def load_hurricane_data(txt_filepath="hurdat2-1851-2024-040425.txt", xlsx_filepath="best_tracks_atl_hu_2025.xlsx"):
    """
    Carga y combina datos históricos (TXT) con datos recientes (Excel).
    """
    data = []
    
    # ---------------------------------------------------------
    # 1. CARGA DEL ARCHIVO DE TEXTO (HURDAT2)
    # ---------------------------------------------------------
    if os.path.exists(txt_filepath):
        with open(txt_filepath, 'r') as f:
            lines = f.readlines()

        current_hid = None
        current_name = None
        current_year = None
        
        for line in lines:
            parts = line.split(',')
            if len(parts) == 4:  # Header row
                current_hid = parts[0].strip()
                current_name = parts[1].strip()
                try: current_year = int(current_hid[4:8])
                except: current_year = 0
            else:  # Data row
                # Parseo básico
                lat_str = parts[4].strip()
                lon_str = parts[5].strip()
                wind_str = parts[6].strip()
                
                lat = float(lat_str[:-1]) * (-1 if lat_str[-1] == 'S' else 1)
                lon = float(lon_str[:-1]) * (-1 if lon_str[-1] == 'W' else 1)
                
                try: wind = float(wind_str)
                except: wind = 0.0

                data.append({
                    'HID': current_hid,
                    'Name': current_name,
                    'Year': current_year,
                    'Date': parts[0].strip(),
                    'Time': parts[1].strip(),
                    'Status': parts[3].strip(),
                    'Lat': lat,
                    'Lon': lon,
                    'Wind_kt': wind
                })
    
    df_txt = pd.DataFrame(data)

    # ---------------------------------------------------------
    # 2. CARGA DEL ARCHIVO EXCEL (Datos Recientes/Proyectados)
    # ---------------------------------------------------------
    df_excel = pd.DataFrame()
    if os.path.exists(xlsx_filepath):
        try:
            # Asumimos que el Excel tiene columnas similares a las usadas en R
            # Mapeo de nombres típicos de NOAA a nuestro formato interno
            raw_xl = pd.read_excel(xlsx_filepath)
            
            # Normalización de columnas (ajusta según tu Excel real si fallara)
            # Buscamos columnas clave ignorando mayúsculas
            raw_xl.columns = [c.upper() for c in raw_xl.columns]
            
            processed_xl = []
            for _, row in raw_xl.iterrows():
                # Extracción segura de datos
                hid = row.get('HID', row.get('HURACANID', 'UNKNOWN'))
                name = row.get('HNAME', row.get('NAME', 'UNKNOWN'))
                
                # Manejo de Lat/Lon (pueden venir como números negativos o strings con N/W)
                lat_val = row.get('LATITUDE', row.get('LAT', 0))
                lon_val = row.get('LONGITUDE', row.get('LON', 0))
                
                # Limpieza Latitud
                if isinstance(lat_val, str):
                    factor = -1 if 'S' in lat_val else 1
                    lat = float(lat_val.replace('N','').replace('S','')) * factor
                else:
                    lat = float(lat_val)
                    
                # Limpieza Longitud
                if isinstance(lon_val, str):
                    factor = -1 if 'W' in lon_val else 1
                    lon = float(lon_val.replace('E','').replace('W','')) * factor
                else:
                    lon = float(lon_val)

                # Fecha y Hora
                date_val = str(row.get('DATE', ''))
                time_val = str(row.get('TIME_UTC', row.get('TIME', '0000'))).zfill(4)
                
                # Año
                try: year = int(str(hid)[4:8])
                except: year = row.get('YEAR', 2025)

                processed_xl.append({
                    'HID': hid,
                    'Name': name,
                    'Year': year,
                    'Date': date_val,
                    'Time': time_val,
                    'Status': row.get('STATUS', 'HU'),
                    'Lat': lat,
                    'Lon': lon,
                    'Wind_kt': float(row.get('WINDSPEED_KT', row.get('WIND', 0)))
                })
            
            df_excel = pd.DataFrame(processed_xl)
            
        except Exception as e:
            st.error(f"Error cargando Excel {xlsx_filepath}: {e}")

    # ---------------------------------------------------------
    # 3. FUSIÓN Y LIMPIEZA FINAL
    # ---------------------------------------------------------
    # Unir ambos DataFrames
    if not df_excel.empty:
        df_final = pd.concat([df_txt, df_excel], ignore_index=True)
    else:
        df_final = df_txt
        
    # Filtrar datos sin viento
    df_final = df_final[df_final['Wind_kt'] > 0].copy()
    
    # Asignar Categorías
    conditions = [
        (df_final['Wind_kt'] <= 33),
        (df_final['Wind_kt'] <= 63),
        (df_final['Wind_kt'] <= 82),
        (df_final['Wind_kt'] <= 95),
        (df_final['Wind_kt'] <= 113),
        (df_final['Wind_kt'] <= 135),
        (df_final['Wind_kt'] > 135)
    ]
    choices = ['TD', 'TS', 'H1', 'H2', 'H3', 'H4', 'H5']
    df_final['Category'] = np.select(conditions, choices, default='Unknown')
    
    return df_final