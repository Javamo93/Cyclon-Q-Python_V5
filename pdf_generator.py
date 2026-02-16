from fpdf import FPDF
import pandas as pd
import os

# Definimos el ancho de la barra lateral para usarlo en los cálculos
SIDEBAR_WIDTH = 20  # milímetros

class PDF(FPDF):
    def header(self):
        # --- IMAGEN LATERAL IZQUIERDA (SIDEBAR) ---
        ### NUEVO ###
        # Verificamos si existe la imagen de la barra lateral
        sidebar_path = "Huracan.png" # Asegúrate de tener esta imagen
        if os.path.exists(sidebar_path):
            # x=0, y=0 para que empiece en la esquina superior izquierda
            # w=SIDEBAR_WIDTH (40mm)
            # h=297 (altura aproximada de una página A4 para que cubra todo el alto)
            self.image(sidebar_path, x=0, y=0, w=SIDEBAR_WIDTH, h=297)

        # --- LOGO AON (Esquina Superior Derecha) ---
        logo_path = "logo_aon.png"
        if os.path.exists(logo_path):
            # x=165 está bien para el logo a la derecha
            self.image(logo_path, x=165, y=10, w=25)
        
        # Título del Reporte
        self.set_y(15)
        ### NUEVO ###
        # Ajustamos la posición X del título para que no empiece sobre la imagen.
        # Le damos un pequeño margen adicional de 5mm (40 + 5 = 45)
        self.set_x(SIDEBAR_WIDTH + 5)
        
        self.set_font('Arial', 'B', 14)
        self.set_text_color(0, 0, 0)
        self.cell(100, 10, 'Reporte de Cotización Paramétrica CIC', 0, 1, 'L')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        # Para el footer también necesitamos ajustar la X si queremos que esté centrado 
        # en el espacio de texto restante, no en la página completa.
        ### NUEVO ###
        self.set_x(SIDEBAR_WIDTH) 
        
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        # Usamos un ancho de celda 'w=0' que ahora tomará el ancho restante desde el nuevo margen
        self.cell(0, 10, f'Página {self.page_no()} | Generado por Cyclone-Q | Aon Reinsurance Solutions', 0, 0, 'C')

def create_pdf(inputs, results, client_name="No especificado"):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    ### NUEVO ###
    # --- CONFIGURACIÓN CRÍTICA DEL MARGEN ---
    # Establecemos un nuevo margen izquierdo de 45mm (40mm de imagen + 5mm de espacio).
    # Todo el contenido generado por cell(), multi_cell(), write() de aquí en adelante
    # respetará este nuevo margen y se desplazará a la derecha automáticamente.
    pdf.set_left_margin(SIDEBAR_WIDTH + 5)
    
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- NUEVO: MOSTRAR EL NOMBRE DEL CLIENTE ---
    pdf.set_y(30) # Un poco más abajo del título
    pdf.set_font('Arial', 'B', 11)
    pdf.set_text_color(100, 100, 100) # Gris oscuro
    pdf.cell(0, 6, f"Cliente: {client_name}", 0, 1, 'L')
    pdf.ln(5)
    # --------------------------------------------

    # ==============================================================================
    # 1. PARÁMETROS DE COBERTURA (Tablas de Confirmación)
    # ==============================================================================
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(0, 89, 119) # Aon Blue
    pdf.set_text_color(255, 255, 255)
    # Al usar w=0, la celda ocupa el ancho desde el nuevo margen izquierdo hasta el margen derecho
    pdf.cell(0, 8, "1. Configuración de Cobertura", 0, 1, 'L', fill=True)
    pdf.ln(4)

    # --- TABLA 1: UBICACIONES ---
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, "Tabla de Ubicaciones y Círculos:", 0, 1)
    
    # Encabezados
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(240, 240, 240)
    
    # Definir anchos: ID, Lat, Lon, Radio, Límite
    # Reduje ligeramente los anchos para asegurar que quepan bien en el espacio reducido
    cols_loc = [12, 22, 22, 18, 30] 
    headers_loc = ['ID', 'Latitud', 'Longitud', 'Radio (km)', 'Límite (USD)']
    
    for i, h in enumerate(headers_loc):
        pdf.cell(cols_loc[i], 6, h, 1, 0, 'C', fill=True)
    pdf.ln()
    
    # Filas
    pdf.set_font('Arial', '', 8)
    raw_locs = inputs.get('ubicaciones', [])
    for loc in raw_locs:
        pdf.cell(cols_loc[0], 6, str(loc.get('id', '-')), 1, 0, 'C')
        pdf.cell(cols_loc[1], 6, str(loc.get('lat', 0)), 1, 0, 'C')
        pdf.cell(cols_loc[2], 6, str(loc.get('lon', 0)), 1, 0, 'C')
        pdf.cell(cols_loc[3], 6, str(loc.get('radio', 0)), 1, 0, 'C')
        pdf.cell(cols_loc[4], 6, f"${loc.get('limite', 0):,.0f}", 1, 1, 'R')
    pdf.ln(4)

    # --- TABLA 2: MATRIZ DE PAGOS (Dinámica) ---
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, "Matriz de Pagos (Payouts):", 0, 1)
    
    raw_payouts = inputs.get('tabla_pagos', [])
    
    if raw_payouts:
        first_row = raw_payouts[0]
        payout_cols = sorted([k for k in first_row.keys() if k != 'min_speed'])
        
        # Recalcular ancho disponible: A4 ancho (210) - Margen Izq (45) - Margen Der (10 default) = ~155 útil
        available_width = 155
        w_speed = 25
        available_for_cols = available_width - w_speed
        w_col = min(22, available_for_cols / max(1, len(payout_cols))) 
        
        # Encabezados
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(240, 240, 240)
        
        pdf.cell(w_speed, 6, "Velocidad >=", 1, 0, 'C', fill=True)
        for col in payout_cols:
            pdf.cell(w_col, 6, col, 1, 0, 'C', fill=True)
        pdf.ln()
        
        # Filas
        pdf.set_font('Arial', '', 8)
        for row in raw_payouts:
            speed = row.get('min_speed', 0)
            pdf.cell(w_speed, 6, f"{speed} km/h", 1, 0, 'C')
            
            for col in payout_cols:
                val = row.get(col, 0)
                if val <= 1.0 and val > 0: val_fmt = f"{val*100:.0f}%"
                elif val == 0: val_fmt = "0%"
                else: val_fmt = f"{val:.0f}%"
                
                pdf.cell(w_col, 6, val_fmt, 1, 0, 'C')
            pdf.ln()
    else:
        pdf.cell(0, 6, "No hay tabla de pagos disponible.", 0, 1)
        
    pdf.ln(4)

    # --- PARÁMETROS GLOBALES ---
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(40, 6, "Límite por Evento:", 0)
    pdf.set_font('Arial', '', 9)
    pdf.cell(40, 6, f"${inputs.get('limite_evento', 0):,.0f}", 0, 0)
    
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(40, 6, "Límite Agregado:", 0)
    pdf.set_font('Arial', '', 9)
    pdf.cell(40, 6, f"${inputs.get('limite_agregado', 0):,.0f}", 0, 1)
    pdf.ln(8)

    # ==============================================================================
    # 2. RESULTADOS (ESCENARIO AGRESIVO)
    # ==============================================================================
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(0, 89, 119) # Aon
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "2. Resultados Financieros", 0, 1, 'L', fill=True)
    pdf.ln(4)

    stats = results.get('stats', {})
    pdf.set_text_color(0, 0, 0)
    
    # Dibujar recuadro de resultados clave
    pdf.set_fill_color(248, 248, 255)
    # Ajustamos el ancho del rectángulo al nuevo espacio disponible (~160mm)
    pdf.rect(pdf.get_x(), pdf.get_y(), 160, 25, 'F')
    
    pdf.set_y(pdf.get_y() + 5)
    # Guardamos la X actual, que ya incluye el margen izquierdo
    current_x = pdf.get_x()
    
    # Prima Neta (AGRESIVA)
    pdf.set_font('Arial', 'B', 10)
    # Ajustamos el padding interno del rectángulo (+5 desde el borde del rectángulo)
    pdf.set_x(current_x + 5)
    pdf.cell(50, 6, "Prima Neta:", 0, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(50, 6, f"${stats.get('Prima_Agresiva', 0):,.2f}", 0, 1)
    
    # RoL (AGRESIVO)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_x(current_x + 5)
    pdf.cell(50, 6, "Net Rate on Line:", 0, 0)
    pdf.set_font('Arial', '', 11)
    pdf.cell(50, 6, f"{stats.get('RoL_Agresivo_Pct', '0.00%')}", 0, 1)
    
    pdf.set_y(pdf.get_y() + 10)

    # ==============================================================================
    # 3. ANÁLISIS HISTÓRICO
    # ==============================================================================
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(0, 89, 119) # Aon
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "3. Desglose Histórico (As-If)", 0, 1, 'L', fill=True)
    pdf.ln(4)

    events = results.get('events', [])
    if events:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(230, 230, 230)
        
        # Encabezados Históricos - Ajustando anchos al nuevo espacio
        pdf.cell(18, 6, "Año", 1, 0, 'C', fill=True)
        pdf.cell(25, 6, "ID Huracán", 1, 0, 'C', fill=True)
        pdf.cell(70, 6, "Nombre", 1, 0, 'L', fill=True)
        pdf.cell(35, 6, "Pago (USD)", 1, 1, 'C', fill=True)
        
        pdf.set_font('Arial', '', 8)
        
        for ev in events:
            pdf.cell(18, 6, str(ev.get('Year', '')), 1, 0, 'C')
            pdf.cell(25, 6, str(ev.get('HuracanID', '')), 1, 0, 'C')
            pdf.cell(70, 6, str(ev.get('Name', '')), 1, 0, 'L')
            pdf.cell(35, 6, f"${ev.get('PagoEventoAdj', 0):,.2f}", 1, 1, 'R')
            
    else:
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 10, "Ningún evento histórico en la base de datos activó esta cobertura.", 0, 1)

    # Disclaimer final
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 7)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4, "Nota: Cifras indicativas basadas en modelación histórica propietaria. Sujeto a términos finales.")

    # --- AGREGAR CONTACTO AQUÍ ---
    pdf.ln(8)
    pdf.set_font('Arial', 'B', 9)
    pdf.set_text_color(255, 0, 0) # Rojo Aon
    pdf.cell(0, 5, "Contacto: cesar.castro2@aon.com, yanina.aguilar@aon.com", 0, 1, 'L')

    return pdf.output(dest='S').encode('latin-1', 'replace')