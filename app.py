import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

st.set_page_config(page_title="Reporte de Producción y Calidad", page_icon="🏭", layout="wide")
st.title("Reporte de producción")

# ==========================================
# CONFIGURACIÓN DE IDs DE GOOGLE DRIVE
# ==========================================
ID_PRODUCCION = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf"
ID_RECIBO = "16Uh0EwP8tyW79TfJlvcjE8li5Lc6RSLj"

URL_PRODUCCION = f"https://drive.google.com/uc?id={ID_PRODUCCION}"
URL_RECIBO = f"https://drive.google.com/uc?id={ID_RECIBO}"

# Función para formatear números con punto para miles y coma para decimales (2 decimales)
def fmt2(val):
    try:
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

# Función para interpretar el lote de producción y extraer Producto y Grupo
def procesar_lote(lote_str):
    if not isinstance(lote_str, str) or len(lote_str) < 8:
        return "Desconocido", "Desconocido"
    
    prod_code = lote_str[5:8]
    mapping_prod = {
        '288': 'Muzzarella Exportacion Coop.',
        '125': 'Muzarrella Piano',
        '488': 'Tybo Coop.',
        '840': 'Muzzarella Exportacion Mastellone'
    }
    mapping_grupo = {
        '288': 'Coopagro',
        '125': 'Coopagro',
        '488': 'Coopagro',
        '840': 'Mastellone'
    }
    return mapping_prod.get(prod_code, f"Desconocido ({prod_code})"), mapping_grupo.get(prod_code, 'Otro')

try:
    st.info("Leyendo datos desde Google Drive (Producción y Recibo)...")
    
    # 1. Leer Producción (Robusto por posición)
    raw_prod = pd.read_excel(URL_PRODUCCION, skiprows=6)
    df_prod = pd.DataFrame()
    df_prod['Fecha'] = raw_prod.iloc[:, 0]
    df_prod['Lote'] = raw_prod.iloc[:, 1]
    df_prod['Litros Procesados'] = raw_prod.iloc[:, 3]
    df_prod['Producto Terminado'] = raw_prod.iloc[:, 5]
    df_prod['PNC'] = raw_prod.iloc[:, 6]
    
    df_prod = df_prod.dropna(subset=['Fecha'])
    df_prod['Fecha'] = pd.to_datetime(df_prod['Fecha'], dayfirst=True, errors='coerce')
    df_prod = df_prod.dropna(subset=['Fecha'])

    for col in ["Litros Procesados", "Producto Terminado", "PNC"]:
        df_prod[col] = pd.to_numeric(df_prod[col], errors='coerce').fillna(0)

    if len(df_prod) > 0:
        df_prod['Producto'], df_prod['Grupo'] = zip(*df_prod['Lote'].astype(str).apply(procesar_lote))
    else:
        df_prod['Producto'] = []
        df_prod['Grupo'] = []

    df_prod['Año'] = df_prod['Fecha'].dt.year
    df_prod['Mes'] = df_prod['Fecha'].dt.month

    # 2. Leer Recibo de Leche (Fecha en Columna B -> índice 1, Litros en Columna F -> índice 5)
    raw_recibo = pd.read_excel(URL_RECIBO)
    df_recibo = pd.DataFrame()
    df_recibo['Fecha_Raw'] = raw_recibo.iloc[:, 1] 
    df_recibo['Litros Ingresados'] = pd.to_numeric(raw_recibo.iloc[:, 5], errors='coerce').fillna(0)
    
    df_recibo['Fecha'] = pd.to_datetime(df_recibo['Fecha_Raw'], dayfirst=True, errors='coerce')
    df_recibo = df_recibo.dropna(subset=['Fecha'])
    
    df_recibo['Año'] = df_recibo['Fecha'].dt.year
    df_recibo['Mes'] = df_recibo['Fecha'].dt.month

    recibo_mensual = df_recibo.groupby(['Año', 'Mes'])['Litros Ingresados'].sum().reset_index()

    # Filtros laterales
    st.sidebar.header("Filtros de Búsqueda")
    opciones_anio = ["Todos"] + (sorted(df_prod['Año'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_mes = ["Todos"] + (sorted(df_prod['Mes'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_grupo = ["Todos", "Coopagro", "Mastellone"]

    filtro_anio = st.sidebar.selectbox("Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("Seleccionar Mes", opciones_mes)
    filtro_grupo = st.sidebar.selectbox("Seleccionar Grupo", opciones_grupo)

    # Filtrar Producción Interna
    df_filtrado = df_prod.copy()
    if len(df_filtrado) > 0:
        if filtro_anio != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
        if filtro_grupo != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo]

    columnas_internas = [
        'Fecha', 'Lote', 'Producto', 'Litros Procesados', 
        'Producto Terminado', 'PNC', '% PNC', 'Ratio de Conversión (%)'
    ]
    
    if len(df_filtrado) > 0:
        df_filtrado['Ratio de Conversión (%)'] = df_filtrado.apply(
            lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
        )
        df_filtrado['% PNC'] = df_filtrado.apply(
            lambda x: f"{(x['PNC'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
        )
        df_filtrado = df_filtrado[columnas_internas]
    else:
        df_filtrado = pd.DataFrame(columns=columnas_internas)

    # Crear DataFrame para Gerencia (Suma Producto Terminado + PNC)
    df_gerencia = df_filtrado.copy()
    if len(df_gerencia) > 0:
        df_gerencia_raw = df_prod.copy()
        if filtro_anio != "Todos":
            df_gerencia_raw = df_gerencia_raw[df_gerencia_raw['Año'] == filtro_anio]
        if filtro_mes != "Todos":
            df_gerencia_raw = df_gerencia_raw[df_gerencia_raw['Mes'] == filtro_mes]
        if filtro_grupo != "Todos":
            df_gerencia_raw = df_gerencia_raw[df_gerencia_raw['Grupo'] == filtro_grupo]
            
        df_gerencia_raw['PT_Total'] = df_gerencia_raw['Producto Terminado'] + df_gerencia_raw['PNC']
        df_gerencia_raw['Ratio Gerencia (%)'] = df_gerencia_raw.apply(
            lambda x: f"{(x['PT_Total'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
        )
        
        df_gerencia = pd.DataFrame()
        df_gerencia['Fecha'] = df_gerencia_raw['Fecha']
        df_gerencia['Lote'] = df_gerencia_raw['Lote']
        df_gerencia['Producto'] = df_gerencia_raw['Producto']
        df_gerencia['Litros Procesados'] = df_gerencia_raw['Litros Procesados']
        df_gerencia['Producto Terminado'] = df_gerencia_raw['PT_Total']
        df_gerencia['Ratio de Conversión (%)'] = df_gerencia_raw['Ratio Gerencia (%)']
    else:
        df_gerencia = pd.DataFrame(columns=['Fecha', 'Lote', 'Producto', 'Litros Procesados', 'Producto Terminado', 'Ratio de Conversión (%)'])

    # Filtrar Recibo
    df_recibo_filtrado = recibo_mensual.copy()
    if filtro_anio != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Mes'] == filtro_mes]
    
    total_litros_ingresados = df_recibo_filtrado['Litros Ingresados'].sum()

    # Totales globales internos
    total_litros_proc = df_filtrado['Litros Procesados'].sum() if len(df_filtrado) > 0 else 0
    total_prod = df_filtrado['Producto Terminado'].sum() if len(df_filtrado) > 0 else 0
    total_pnc = df_filtrado['PNC'].sum() if len(df_filtrado) > 0 else 0
    ratio_ponderado = (total_prod / total_litros_proc * 100) if total_litros_proc > 0 else 0
    pnc_promedio = (total_pnc / total_litros_proc * 100) if total_litros_proc > 0 else 0
    rendimiento_ingreso = (total_prod / total_litros_ingresados * 100) if total_litros_ingresados > 0 else 0

    # Totales globales gerencia (PT + PNC)
    total_prod_gerencia = df_gerencia['Producto Terminado'].sum() if len(df_gerencia) > 0 else 0
    ratio_ponderado_gerencia = (total_prod_gerencia / total_litros_proc * 100) if total_litros_proc > 0 else 0
    rendimiento_ingreso_gerencia = (total_prod_gerencia / total_litros_ingresados * 100) if total_litros_ingresados > 0 else 0

    # Título dinámico PDF con Mes y Año
    meses_nombres = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 
        5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 
        9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    mes_str = meses_nombres.get(filtro_mes, "") if filtro_mes != "Todos" else ""
    if filtro_anio != "Todos":
        anio_str = str(filtro_anio)
    else:
        if len(df_filtrado) > 0:
            anios_unicos = df_prod.loc[df_prod.index.isin(df_filtrado.index), 'Fecha'].dt.year.unique() if 'Fecha' in df_filtrado else []
            anio_str = str(anios_unicos[0]) if len(anios_unicos) == 1 else "2026"
        else:
            anio_str = "2026"

    titulo_pdf = f"Reporte de producción {mes_str} {anio_str}".strip()

    # PESTAÑAS EN LA WEB
    tab_interno, tab_gerencia = st.tabs(["🔒 Vista Interna", "📊 Vista Gerencia"])

    with tab_interno:
        st.subheader("Resumen General Interno")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Litros Ingresados", fmt2(total_litros_ingresados))
        c2.metric("Litros Procesados", fmt2(total_litros_proc))
        c3.metric("Prod. Terminado", fmt2(total_prod))
        c4.metric("Total PNC", fmt2(total_pnc))
        c5.metric("Ratio Ponderado", f"{ratio_ponderado:.2f}%".replace(".", ","))
        c6.metric("Rend. Ingreso vs Term.", f"{rendimiento_ingreso:.2f}%".replace(".", ","))

        st.subheader("Detalle de Lotes (Interno)")
        if len(df_filtrado) > 0:
            df_display = df_filtrado.copy()
            df_display['Litros Procesados'] = df_display['Litros Procesados'].apply(fmt2)
            df_display['Producto Terminado'] = df_display['Producto Terminado'].apply(fmt2)
            df_display['PNC'] = df_display['PNC'].apply(fmt2)
            df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_display, use_container_width=True)

    with tab_gerencia:
        st.subheader("Resumen General Gerencia (PT + PNC)")
        g1, g2, g3, g4, g5 = st.columns(5)
        g1.metric("Litros Ingresados", fmt2(total_litros_ingresados))
        g2.metric("Litros Procesados", fmt2(total_litros_proc))
        g3.metric("Total Prod. Terminado", fmt2(total_prod_gerencia))
        g4.metric("Ratio PT / Litros procesados", f"{ratio_ponderado_gerencia:.2f}%".replace(".", ","))
        g5.metric("Ratio PT / Litros ingresados", f"{rendimiento_ingreso_gerencia:.2f}%".replace(".", ","))

        st.subheader("Detalle de Lotes (Gerencia)")
        if len(df_gerencia) > 0:
            df_gerencia_display = df_gerencia.copy()
            df_gerencia_display['Litros Procesados'] = df_gerencia_display['Litros Procesados'].apply(fmt2)
            df_gerencia_display['Producto Terminado'] = df_gerencia_display['Producto Terminado'].apply(fmt2)
            df_gerencia_display['Fecha'] = df_gerencia_display['Fecha'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_gerencia_display, use_container_width=True)

    # --- FUNCIONES DE PDF ---
    def generar_pdf_interno(dataframe_original, titulo_dinamico, lit_ingresados, rend_ingreso):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(190, 7, txt=titulo_dinamico + " (Interno)", ln=True, align='C')
        pdf.ln(3)
        
        # Resumen con fuente 9pt (más grande que el detalle)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Resumen Interno", ln=True, align='L')
        pdf.set_font("Arial", '', 9)
        
        tot_lit = dataframe_original['Litros Procesados'].sum()
        tot_pro = dataframe_original['Producto Terminado'].sum()
        tot_pn = dataframe_original['PNC'].sum()
        rat_pond = (tot_pro / tot_lit * 100) if tot_lit > 0 else 0
        pnc_glob = (tot_pn / tot_lit * 100) if tot_lit > 0 else 0
        
        pdf.cell(95, 5, txt=f"Total Litros Ingresados: {fmt2(lit_ingresados)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio Ponderado: {rat_pond:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Litros Procesados: {fmt2(tot_lit)}", ln=0)
        pdf.cell(95, 5, txt=f"Rendimiento Ingresado vs Term.: {rend_ingreso:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Producto Terminado: {fmt2(tot_pro)}", ln=0)
        pdf.cell(95, 5, txt=f"Total PNC: {fmt2(tot_pn)} (% PNC Global: {pnc_glob:.2f}%)".replace(".", ","), ln=1)
        pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Detalle de Lotes", ln=True, align='L')
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 6.5)
        anchos = [18, 24, 40, 24, 24, 14, 16, 30]
        columnas = dataframe_original.columns.tolist()
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 7, columnas[i], border=1, align='C')
        pdf.ln()
        
        # Detalle con fuente 7pt
        pdf.set_font("Arial", '', 7)
        for index, row in dataframe_original.iterrows():
            pdf.cell(anchos[0], 6, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 6, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 6, str(row['Producto']), border=1, align='L')
            pdf.cell(anchos[3], 6, fmt2(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 6, fmt2(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 6, fmt2(row['PNC']), border=1, align='R')
            pdf.cell(anchos[6], 6, row['% PNC'], border=1, align='C')
            pdf.cell(anchos[7], 6, row['Ratio de Conversión (%)'], border=1, align='C')
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        return pdf_output.encode('latin1') if isinstance(pdf_output, str) else pdf_output

    def generar_pdf_gerencia(dataframe_gerencia, titulo_dinamico, lit_ingresados, rend_gerencia, ratio_pond_gerenc):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(190, 7, txt=titulo_dinamico, ln=True, align='C')
        pdf.ln(3)
        
        # Resumen gerencial con fuente 9pt (más grande que el detalle)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Resumen", ln=True, align='L')
        pdf.set_font("Arial", '', 9)
        
        tot_lit = dataframe_gerencia['Litros Procesados'].sum()
        tot_pro_ger = dataframe_gerencia['Producto Terminado'].sum()
        
        pdf.cell(95, 5, txt=f"Total Litros Ingresados: {fmt2(lit_ingresados)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio PT / Litros procesados: {ratio_pond_gerenc:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Litros Procesados: {fmt2(tot_lit)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio PT / Litros ingresados: {rend_gerencia:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Producto Terminado: {fmt2(tot_pro_ger)}", ln=1)
        pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Detalle de Lotes", ln=True, align='L')
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 7)
        anchos = [20, 28, 42, 32, 38, 30]
        columnas = dataframe_gerencia.columns.tolist()
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 7, columnas[i], border=1, align='C')
        pdf.ln()
        
        # Detalle con fuente 7pt
        pdf.set_font("Arial", '', 7)
        for index, row in dataframe_gerencia.iterrows():
            pdf.cell(anchos[0], 6, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 6, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 6, str(row['Producto']), border=1, align='L')
            pdf.cell(anchos[3], 6, fmt2(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 6, fmt2(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 6, row['Ratio de Conversión (%)'], border=1, align='C')
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        return pdf_output.encode('latin1') if isinstance(pdf_output, str) else pdf_output

    # Botones de Descarga de ambos reportes
    st.subheader("📥 Descarga de Reportes")
    if len(df_filtrado) > 0:
        col_d1, col_d2 = st.columns(2)
        
        pdf_interno = generar_pdf_interno(df_filtrado, titulo_pdf, total_litros_ingresados, rendimiento_ingreso)
        with col_d1:
            st.download_button(
                label="📥 Descargar Reporte Interno (PDF)",
                data=pdf_interno,
                file_name="Reporte_Produccion_Interno.pdf",
                mime="application/pdf"
            )
            
        pdf_gerencia = generar_pdf_gerencia(df_gerencia, titulo_pdf, total_litros_ingresados, rendimiento_ingreso_gerencia, ratio_ponderado_gerencia)
        with col_d2:
            st.download_button(
                label="📥 Descargar Reporte Gerencia (PDF)",
                data=pdf_gerencia,
                file_name="Reporte_Produccion_Gerencia.pdf",
                mime="application/pdf"
            )
    else:
        st.warning("No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer los archivos de Drive o procesar los datos: {e}")
