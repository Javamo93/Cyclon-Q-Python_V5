import folium
import pandas as pd

# Definición de categorías y colores
def get_category_color(wind_kt):
    wind_mph = wind_kt * 1.15078
    if wind_mph < 39: return 'TD', 'blue'
    elif 39 <= wind_mph <= 73: return 'TS', 'cyan'
    elif 74 <= wind_mph <= 95: return 'H1', 'yellow'
    elif 96 <= wind_mph <= 110: return 'H2', 'orange'
    elif 111 <= wind_mph <= 129: return 'H3', 'red'
    elif 130 <= wind_mph <= 156: return 'H4', 'darkred'
    else: return 'H5', 'purple'

def generate_interactive_map(df_hurdat, df_locations, huracan_id):
    """
    Genera el mapa interactivo filtrando el huracán específico.
    Retorna el objeto mapa (folium.Map) sin renderizarlo para evitar duplicados.
    """
    # 1. Filtrar los datos para el huracán seleccionado
    df_trayectoria = df_hurdat[df_hurdat['HID'] == huracan_id].sort_values(['Date', 'Time'])
    
    if df_trayectoria.empty:
        return None

    # Centro del mapa basado en el primer punto
    start_lat = df_trayectoria.iloc[0]['Lat']
    start_lon = df_trayectoria.iloc[0]['Lon']
    m = folium.Map(location=[start_lat, start_lon], zoom_start=6, tiles='CartoDB positron')

    # 2. Dibujar Ubicaciones y Círculos
    if isinstance(df_locations, pd.DataFrame):
        iterator = df_locations.to_dict('records')
    else:
        iterator = df_locations

    for u in iterator:
        lat = u.get('Lat', u.get('lat'))
        lon = u.get('Lon', u.get('lon'))
        radio = u.get('Radius', u.get('radio'))
        limit = u.get('Limit', u.get('limite'))
        loc_id = u.get('ID', u.get('id', 'N/A'))

        # Círculo del área asegurada
        folium.Circle(
            location=[lat, lon],
            radius=radio * 1000,
            color='blue', fill=True, fill_opacity=0.1, weight=1,
            tooltip=f"Loc ID {loc_id}: R={radio}km, Lím=${limit:,.0f}"
        ).add_to(m)
        
        # Marcador de ubicación (azul estándar)
        folium.Marker(
            [lat, lon],
            icon=folium.Icon(color='blue', icon='map-marker')
        ).add_to(m)

    # 3. Dibujar Trayectoria (Puntos y Líneas)
    points = []
    segment_colors = [] 
    
    for _, row in df_trayectoria.iterrows():
        lat, lon = row['Lat'], row['Lon']
        wind = row['Wind_kt']
        wind_kmh = wind * 1.852
        cat, color = get_category_color(wind)
        
        points.append((lat, lon))
        segment_colors.append(color)

        # Popup con velocidad en nudos y km/h
        popup_text = f"""
        <b>Fecha:</b> {row['Date']} {row['Time']}<br>
        <b>Cat:</b> {cat}<br>
        <b>Viento:</b> {wind} kt / {wind_kmh:.1f} km/h
        """

        folium.CircleMarker(
            location=[lat, lon], radius=5,
            color=color, fill=True, fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=200)
        ).add_to(m)
    
    # 4. Dibujar Segmentos de Línea Coloreados
    if len(points) > 1:
        for i in range(len(points) - 1):
            folium.PolyLine(
                [points[i], points[i+1]],
                color=segment_colors[i],
                weight=2,
                opacity=0.8
            ).add_to(m)

    # 5. Agregar Leyenda HTML Flotante
    legend_html = '''
     <div style="position: fixed; 
     bottom: 50px; right: 50px; width: 150px; height: 190px; 
     border:2px solid grey; z-index:9999; font-size:12px;
     background-color:white; opacity: 0.85;
     padding: 10px; border-radius: 5px;">
     <b>Categoría</b><br>
     <i style="background:blue; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Dep. Tropical<br>
     <i style="background:cyan; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Tor. Tropical<br>
     <i style="background:yellow; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Huracán C1<br>
     <i style="background:orange; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Huracán C2<br>
     <i style="background:red; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Huracán C3<br>
     <i style="background:darkred; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Huracán C4<br>
     <i style="background:purple; width:10px; height:10px; display:inline-block; margin-right:5px;"></i>Huracán C5
     </div>
     '''
    m.get_root().html.add_child(folium.Element(legend_html))

    # Ajustar límites
    m.fit_bounds(m.get_bounds())
    
    return m