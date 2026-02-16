import pandas as pd
import numpy as np
from math import radians, cos, sin, atan2, sqrt, pi

# ==============================================================================
# 1. FUNCIONES GEOMÉTRICAS
# ==============================================================================

def haversine_km(lon1, lat1, lon2, lat2):
    """Calcula distancia Haversine en KM (Aproximación suficiente para consistencia)."""
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def solve_intersection_wind(p1, p2, c_lat, c_lon, radius_km):
    winds = []
    lon1, lat1, w1 = p1['Lon'], p1['Lat'], p1['Wind_kt']
    lon2, lat2, w2 = p2['Lon'], p2['Lat'], p2['Wind_kt']
    
    mid_lat = radians((lat1 + lat2) / 2)
    km_per_deg_lat = 111.32
    km_per_deg_lon = 111.32 * cos(mid_lat)
    
    dx = (lon2 - lon1) * km_per_deg_lon
    dy = (lat2 - lat1) * km_per_deg_lat
    cx = (c_lon - lon1) * km_per_deg_lon
    cy = (c_lat - lat1) * km_per_deg_lat
    
    A = dx**2 + dy**2
    if A < 1e-9: return []

    B = -2 * (cx * dx + cy * dy)
    C_eq = (cx**2 + cy**2) - radius_km**2
    
    delta = B**2 - 4*A*C_eq
    
    if delta >= 0:
        sqrt_delta = sqrt(delta)
        t1 = (-B - sqrt_delta) / (2*A)
        t2 = (-B + sqrt_delta) / (2*A)
        for t in [t1, t2]:
            if -1e-5 <= t <= 1.00001:
                t_clamp = max(0.0, min(1.0, t))
                w_interp = w1 + t_clamp * (w2 - w1)
                winds.append(w_interp)
    return winds

def get_max_wind_exact(group, c_lat, c_lon, radius_km):
    max_w = 0.0
    # 1. Puntos dentro
    for idx, row in group.iterrows():
        d = haversine_km(row['Lon'], row['Lat'], c_lon, c_lat)
        if d <= radius_km:
            if row['Wind_kt'] > max_w: max_w = row['Wind_kt']
    
    # 2. Intersecciones
    for i in range(len(group) - 1):
        p1 = group.iloc[i]
        p2 = group.iloc[i+1]
        
        # Optimización espacial simple
        rad_deg = (radius_km / 111.0) + 1.0
        if (min(p1['Lat'], p2['Lat']) > c_lat + rad_deg) or \
           (max(p1['Lat'], p2['Lat']) < c_lat - rad_deg) or \
           (min(p1['Lon'], p2['Lon']) > c_lon + rad_deg) or \
           (max(p1['Lon'], p2['Lon']) < c_lon - rad_deg):
            continue

        crossing_winds = solve_intersection_wind(p1, p2, c_lat, c_lon, radius_km)
        for w in crossing_winds:
            if w > max_w: max_w = w     
    return max_w

def determine_side_exact_r_logic(group, c_lat, c_lon):
    dists = []
    for idx, row in group.iterrows():
        d = haversine_km(row['Lon'], row['Lat'], c_lon, c_lat)
        dists.append({'idx': idx, 'dist': d, 'lat': row['Lat'], 'lon': row['Lon']})
    
    dists.sort(key=lambda x: x['dist'])
    if len(dists) < 2: return "DER"
    
    p_close_A = dists[0]
    p_close_B = dists[1]
    
    if p_close_A['idx'] < p_close_B['idx']:
        p_first, p_second = p_close_A, p_close_B
    else:
        p_first, p_second = p_close_B, p_close_A
        
    vec1_x = p_first['lon'] - c_lon
    vec1_y = p_first['lat'] - c_lat
    vec2_x = p_second['lon'] - c_lon
    vec2_y = p_second['lat'] - c_lat
    
    cross_prod = (vec1_x * vec2_y) - (vec1_y * vec2_x)
    return "IZQ" if cross_prod > 0 else "DER"

# ==============================================================================
# 2. LÓGICA FINANCIERA (REPLICADA EXACTAMENTE DE R)
# ==============================================================================

def calculate_complex_rol_exact(df_annual_stats, limit_agg):
    """
    Replica EXACTAMENTE la lógica de 'engine_cycloneQ.R' (líneas ~980-1127).
    Calcula escenarios Base y Agresivo basándose en ratios históricos.
    """
    if df_annual_stats.empty: 
        return 0.0, 0.0, 0.0, 0.0, 0.0 # Base_RoL, Base_Prima, AAL, Agg_RoL, Agg_Prima
    
    last_year_analized = 2025
    
    # 1. Métricas Históricas
    # Todos los años
    expected_loss_all_years = df_annual_stats['PagoAnual'].mean()
    
    # 1949 en adelante
    df_1949 = df_annual_stats[df_annual_stats['Year'] >= 1949]
    expected_loss_1949_onwards = df_1949['PagoAnual'].mean()
    if expected_loss_1949_onwards == 0: expected_loss_1949_onwards = 0.001
    
    # Últimos 25 años
    df_25 = df_annual_stats[df_annual_stats['Year'] >= (last_year_analized - 25 + 1)]
    expected_loss_last25y = df_25['PagoAnual'].mean()
    
    # Ratios de comparación
    ratio_aal_all_years = (expected_loss_all_years / expected_loss_1949_onwards) - 1
    ratio_aal_last25y = (expected_loss_last25y / expected_loss_1949_onwards) - 1
    
    # 2. Lógica de Escenarios (9 Casos Mutuamente Excluyentes)
    # Inicialización
    divisor_base = 0.4
    divisor_agg = 0.525
    target_aal = expected_loss_1949_onwards
    
    # Caso 1
    if ratio_aal_all_years < -0.1 and ratio_aal_last25y > 0.1:
        divisor_base = 0.475
        divisor_agg = 0.575
        target_aal = expected_loss_last25y
        
    # Caso 2
    elif ratio_aal_all_years < -0.1 and abs(ratio_aal_last25y) <= 0.1:
        divisor_base = 0.4
        divisor_agg = 0.575
        target_aal = expected_loss_1949_onwards
        
    # Caso 3
    elif ratio_aal_all_years < -0.1 and ratio_aal_last25y < -0.1:
        divisor_base = 0.5
        divisor_agg = 0.6
        target_aal = expected_loss_1949_onwards
        
    # Caso 4
    elif abs(ratio_aal_all_years) <= 0.1 and ratio_aal_last25y > 0.1:
        divisor_base = 0.45
        divisor_agg = 0.575
        target_aal = expected_loss_last25y
        
    # Caso 5
    elif abs(ratio_aal_all_years) <= 0.1 and abs(ratio_aal_last25y) <= 0.1:
        divisor_base = 0.4
        divisor_agg = 0.55
        target_aal = expected_loss_1949_onwards
        
    # Caso 6
    elif abs(ratio_aal_all_years) <= 0.1 and ratio_aal_last25y < -0.1:
        divisor_base = 0.45
        divisor_agg = 0.6
        target_aal = expected_loss_1949_onwards
        
    # Caso 7
    elif ratio_aal_all_years > 0.1 and ratio_aal_last25y > 0.1:
        divisor_base = 0.425
        divisor_agg = 0.55
        target_aal = expected_loss_last25y
        
    # Caso 8
    elif ratio_aal_all_years > 0.1 and abs(ratio_aal_last25y) <= 0.1:
        divisor_base = 0.4
        divisor_agg = 0.525
        target_aal = expected_loss_1949_onwards
        
    # Caso 9
    elif ratio_aal_all_years > 0.1 and ratio_aal_last25y < -0.1:
        divisor_base = 0.425
        divisor_agg = 0.575
        target_aal = expected_loss_1949_onwards

    # 3. Ajuste de RoL Mínimo (Umbral 3.5% y Mínimo 2%)
    min_rol = 0.02
    umbra_ajuste_rol = 0.035
    factor_adj_rol = (umbra_ajuste_rol - min_rol) / umbra_ajuste_rol
    
    # Cálculo crudo
    if limit_agg > 0:
        net_rol_base = (1/divisor_base) * (target_aal / limit_agg)
        net_rol_agg = (1/divisor_agg) * (target_aal / limit_agg)
    else:
        net_rol_base = 0.0
        net_rol_agg = 0.0
    
    # Ajuste Suavizado Base
    if net_rol_base < umbra_ajuste_rol:
        delta_rol = umbra_ajuste_rol - net_rol_base
        delta_rol = factor_adj_rol * delta_rol
        net_rol_base = umbra_ajuste_rol - delta_rol
        
    # Ajuste Suavizado Agresivo
    if net_rol_agg < umbra_ajuste_rol:
        delta_rol = umbra_ajuste_rol - net_rol_agg
        delta_rol = factor_adj_rol * delta_rol
        net_rol_agg = umbra_ajuste_rol - delta_rol
        
    prima_base = net_rol_base * limit_agg
    prima_agg = net_rol_agg * limit_agg
    
    return net_rol_base, prima_base, target_aal, net_rol_agg, prima_agg

# ==============================================================================
# 3. MOTOR PRINCIPAL
# ==============================================================================

def run_engine_calculation(df_hurdat, df_locations, df_payouts, limit_event, limit_agg, asym_factor):
    
    # 1. Filtro Espacial Preliminar
    min_lat = df_locations['Lat'].min() - 5
    max_lat = df_locations['Lat'].max() + 5
    min_lon = df_locations['Lon'].min() - 5
    max_lon = df_locations['Lon'].max() + 5
    
    relevant_hids = df_hurdat[
        (df_hurdat['Lat'].between(min_lat, max_lat)) & 
        (df_hurdat['Lon'].between(min_lon, max_lon))
    ]['HID'].unique()
    
    df_subset = df_hurdat[df_hurdat['HID'].isin(relevant_hids)].copy()
    grouped = df_subset.groupby('HID')
    
    results_events = []
    
    # 2. Procesamiento Evento por Evento
    for hid, group in grouped:
        group = group.sort_values(['Date', 'Time']).reset_index(drop=True)
        if len(group) < 2: continue
        
        circle_payouts = []
        
        for idx, loc in df_locations.iterrows():
            c_lat, c_lon = loc['Lat'], loc['Lon']
            radius_km = loc['Radius']
            loc_limit = loc['Limit']
            loc_id = int(loc['ID'])
            
            # A) Viento exacto
            max_wind_kt = get_max_wind_exact(group, c_lat, c_lon, radius_km)
            if max_wind_kt == 0: continue
            
            # B) Asimetría
            side = determine_side_exact_r_logic(group, c_lat, c_lon)
            
            # C) Payout %
            max_wind_kmh = max_wind_kt * 1.852
            
            # Buscar porcentaje en tabla
            col_name = f"C{loc_id}"
            payout_pct = 0.0
            
            # La tabla de pagos debe interpretarse como tramos [min_speed, next_min_speed)
            # Filtramos todas las filas donde min_speed <= viento registrado
            matching_rows = df_payouts[df_payouts['min_speed'] <= max_wind_kmh]
            if not matching_rows.empty:
                # Tomamos la última fila que cumple la condición (el tramo más alto alcanzado)
                if col_name in df_payouts.columns:
                    raw_val = matching_rows.iloc[-1][col_name]
                elif 'payout' in df_payouts.columns:
                    raw_val = matching_rows.iloc[-1]['payout']
                else: 
                    raw_val = 0.0
                
                # Normalizar % si viene como 10 en lugar de 0.10
                payout_pct = raw_val / 100.0 if raw_val > 1.0 else raw_val
            
            pay_t = payout_pct * loc_limit
            # Aplicamos factor asimétrico solo si está a la Izquierda
            pay_a = pay_t * (asym_factor if side == "IZQ" else 1.0)
            
            if max_wind_kmh > 30: 
                circle_payouts.append({
                    'Lat': c_lat, 'Lon': c_lon,
                    'ID': loc_id,
                    'Radius': radius_km,
                    'Wind': max_wind_kmh,
                    'Pct': payout_pct,
                    'PayTrad': pay_t, 
                    'PayAsym': pay_a # Aquí guardamos el valor asimétrico monetario, aunque el RoL luego se calcula sobre la estructura anual
                })
        
        if not circle_payouts: continue
        
        df_circles = pd.DataFrame(circle_payouts)
        
        # 3. Agregación: Un pago por ubicación (el círculo que más paga)
        df_circles = df_circles.sort_values('PayTrad', ascending=False)
        df_loc_winners = df_circles.drop_duplicates(subset=['Lat', 'Lon'], keep='first')
        
        event_payout_trad = df_loc_winners['PayTrad'].sum()
        # Nota: La lógica R usa el 'lado' del círculo ganador para la asimetría global del evento
        # Aquí sumamos la asimetría calculada individualmente por ubicación ganadora
        event_payout_asym = df_loc_winners['PayAsym'].sum()
        
        # Evidencia textual para la IA
        breakdown_parts = []
        for _, row in df_loc_winners.iterrows():
            if row['PayTrad'] > 0:
                part = (f"[Ubicación Lat:{row['Lat']:.2f}/Lon:{row['Lon']:.2f}] "
                        f"Ganó Círculo {int(row['ID'])} ({row['Radius']}km) "
                        f"Viento {row['Wind']:.1f} km/h -> "
                        f"Tramo {row['Pct']*100:.0f}% = ${row['PayTrad']:,.0f}")
                breakdown_parts.append(part)
            else:
                part = (f"[Ubicación Lat:{row['Lat']:.2f}] Círculo {int(row['ID'])} "
                        f"Viento {row['Wind']:.1f} km/h (Bajo Trigger)")
                breakdown_parts.append(part)

        breakdown_text = " || ".join(breakdown_parts)
        
        # Tope por Evento
        raw_total = event_payout_trad
        event_payout_trad = min(event_payout_trad, limit_event)
        event_payout_asym = min(event_payout_asym, limit_event) # El límite por evento también aplica al asimétrico
        
        if raw_total > limit_event:
            breakdown_text += f" || [ALERTA] Tope Evento Aplicado (${raw_total:,.0f} -> ${limit_event:,.0f})."

        if event_payout_trad > 0:
            results_events.append({
                'HuracanID': hid,
                'Name': group['Name'].iloc[0],
                'Year': group['Year'].iloc[0],
                'PagoEventoRaw': event_payout_trad,
                'PagoAsymRaw': event_payout_asym, # Guardamos el asimétrico crudo
                'breakdown_text': breakdown_text
            })

    # 4. Agregación Anual y Límites Agregados (Ciclo Histórico)
    last_year_analized = 2025
    all_years = pd.DataFrame({'Year': range(1851, last_year_analized + 1)})
    
    if not results_events:
        df_annual = all_years.copy()
        df_annual['PagoAnual'] = 0.0
        df_res_final = pd.DataFrame()
    else:
        df_res = pd.DataFrame(results_events).sort_values('HuracanID')
        df_res['PagoEventoAdj'] = 0.0
        
        # Aplicación del Límite Agregado Anual
        for y in df_res['Year'].unique():
            mask = df_res['Year'] == y
            sub = df_res[mask]
            cum_t = 0.0
            
            for idx in sub.index:
                raw_t = df_res.at[idx, 'PagoEventoRaw']
                left_t = max(0, limit_agg - cum_t)
                pay_t = min(raw_t, left_t)
                
                if pay_t < raw_t:
                    current_text = df_res.at[idx, 'breakdown_text']
                    df_res.at[idx, 'breakdown_text'] = current_text + f" || [AGREGADO] Recorte anual a ${pay_t:,.0f}"
                
                df_res.at[idx, 'PagoEventoAdj'] = pay_t
                cum_t += pay_t

        # Crear Dataframe Anual para Estadísticas
        annual_sums = df_res.groupby('Year')[['PagoEventoAdj']].sum().reset_index()
        annual_sums.columns = ['Year', 'PagoAnual']
        df_annual = pd.merge(all_years, annual_sums, on='Year', how='left').fillna(0)
        df_res_final = df_res[df_res['PagoEventoAdj'] > 0].copy()

    # 5. Cálculo de Estadísticas (Base y Agresivo)
    rol_base, prima_base, aal_target, rol_agg, prima_agg = calculate_complex_rol_exact(df_annual, limit_agg)
    
    stats = {
        # Tradicional
        'Prima_Neta_Trad': prima_base,
        'Net_RoL_Pct': f"{rol_base*100:.2f}%",
        
        # AGRESIVO (LO QUE QUIERES VER)
        'Prima_Agresiva': prima_agg,
        'RoL_Agresivo_Pct': f"{rol_agg*100:.2f}%",
        
        'AAL_Target': aal_target
    }
    
    events_list = df_res_final.to_dict('records') if not df_res_final.empty else []

    return {'events': events_list, 'stats': stats}