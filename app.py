import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

st.set_page_config(page_title="Reporte de Producción", page_icon="🏭", layout="wide")
st.title("Generador de Reportes de Producción y Calidad")

# ID de Google Drive (ya integrado)
ID_DEL_ARCHIVO = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf" 
URL_DRIVE = f"https://drive.google.com/uc?id={ID_DEL_ARCHIVO}"

# Función para formatear números con 3 decimales: 1.234.567,890
def fmt3(val):
    try:
        return f"{val:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

# Función para interpretar el lote y extraer Producto y Grupo
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
    
    producto = mapping_prod.get(prod_code, f"Desconocido ({prod_code})")
    grupo = mapping_grupo.get(prod_code, 'Otro')
    
    return producto, grupo

try:
    st.info("Leyendo datos directamente desde Google Drive...")
    
    # Lectura robusta por posición
    raw_df = pd.read_excel(URL_DRIVE, skiprows=6)
    
    df = pd.DataFrame()
    df['Fecha'] = raw_df.iloc[:, 0]
    df['Lote'] = raw_df.iloc[:, 1]
    df['Litros Procesados'] = raw_df.iloc[:, 3]
    df['Producto Terminado'] = raw_df.iloc[:, 5]
    df['PNC'] = raw_df.iloc[:, 6]
    
    df = df.dropna(subset=['Fecha'])
    df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Fecha'])

    for col in ["Litros Procesados", "Producto Terminado", "PNC"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Extraemos Producto y Grupo a partir del Lote
    df['Producto'], df['Grupo'] = zip(*df['Lote'].astype(str).apply(procesar_lote))

    # Cálculo del Ratio de Conversión (%) por fila
    df['Ratio de Conversión (%)'] = df.apply(
        lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.3f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,000%", 
        axis=1
    )

    # Cálculo del % de PNC por fila
    df['% PNC'] = df.apply(
        lambda x: f"{(x['PNC'] / x['Litros Procesados'] * 100):.3f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,000%", 
        axis=1
    )

    columnas_ordenadas = [
        'Fecha', 'Lote', 'Producto', 'Litros Procesados', 
        'Producto Terminado', 'PNC', '% PNC', 'Ratio de Conversión (%)'
    ]
    df['Año'] = df['Fecha'].dt.year
    df['Mes'] = df['Fecha'].dt.month

    # Filtros laterales
    st.sidebar.header("Filtros de Búsqueda")
    
    opciones_anio = ["Todos"] + sorted(df['Año'].unique().tolist())
    opciones_mes = ["Todos"] + sorted(df['Mes'].unique().tolist())
    opciones_grupo = ["Todos", "Coopagro", "Mastellone"]

    filtro_anio = st.sidebar.selectbox("Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("Seleccionar Mes", opciones_mes)
    filtro_grupo = st.sidebar.selectbox("Seleccionar Grupo", opciones_grupo)

    df_filtrado = df.copy()
    if filtro_anio != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
    if filtro_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo]

    df_filtrado = df_filtrado[columnas_ordenadas]

    # Totales y métricas globales
    total_litros = df_filtrado['Litros Procesados'].sum()
    total_prod = df_filtrado['Producto Terminado'].sum()
    total_pnc = df_filtrado['PNC'].sum()
    
    ratio_ponderado = (total_prod / total_litros * 100) if total_litros > 0 else 0
    pnc_promedio = (total_pnc / total_litros * 100) if total_litros > 0 else 0

    # Mostrar métricas rápidas en pantalla
    st.subheader("📊 Resumen de Producción y Calidad")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Litros Procesados", fmt3(total_litros))
    col2.metric("Prod. Terminado", fmt3(total_prod))
    col3.metric("Total PNC", fmt3(total_pnc))
    col4.metric("Ratio Ponderado", f"{ratio_ponderado:.3f}%".replace(".", ","))
    col5.metric("% PNC Global", f"{pnc_promedio:.3f}%".replace(".", ","))

    # Resumen por producto en pantalla
    st.subheader("📦 Producción por Producto")
    resumen_prod = df_filtrado.groupby('Producto')[['Litros Procesados', 'Producto Terminado', 'PNC']].sum().reset_index()
    st.dataframe(resumen_prod, use_container_width=True)

    # Detalle de lotes en pantalla
    st.subheader("📋 Detalle de Lotes")
    df_display = df_filtrado.copy()
    df_display['Litros Procesados'] = df_display['Litros Procesados'].apply(fmt3)
    df_display['Producto Terminado'] = df_display['Producto Terminado'].apply(fmt3)
    df_display['PNC'] = df_display['PNC'].apply(fmt3)
    df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_display, use_container_width=True)

    # Función para generar el PDF con el Resumen Ejecutivo Arriba
    def generar_pdf_bytes(dataframe_original):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        # Título principal
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(190, 7, txt="Reporte de Producción y Calidad", ln=True, align='C')
        pdf.ln(3)
        
        # --- SECCIÓN DE RESUMEN EJECUTIVO ARRIBA ---
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 5, txt="Resumen Ejecutivo", ln=True, align='L')
        
        pdf.set_font("Arial", '', 8)
        tot_lit = dataframe_original['Litros Procesados'].sum()
        tot_pro = dataframe_original['Producto Terminado'].sum()
        tot_pn = dataframe_original['PNC'].sum()
        rat_pond = (tot_pro / tot_lit * 100) if tot_lit > 0 else 0
        pnc_glob = (tot_pn / tot_lit * 100) if tot_lit > 0 else 0
        
        pdf.cell(95, 5, txt=f"Total Litros Procesados: {fmt3(tot_lit)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio Ponderado: {rat_pond:.3f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Producto Terminado: {fmt3(tot_pro)}", ln=0)
        pdf.cell(95, 5, txt=f"Total PNC: {fmt3(tot_pn)} (% PNC Global: {pnc_glob:.3f}%)".replace(".", ","), ln=1)
        pdf.ln(2)
        
        # Desglose de cantidad por producto
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 5, txt="Cantidad por Producto:", ln=True, align='L')
        pdf.set_font("Arial", '', 7.5)
        
        prod_res = dataframe_original.groupby('Producto')[['Litros Procesados', 'Producto Terminado']].sum().reset_index()
        for idx, row in prod_res.iterrows():
            txt_linea = f"- {row['Producto']}: Litros Proc. {fmt3(row['Litros Procesados'])} | Prod. Terminado: {fmt3(row['Producto Terminado'])}"
            pdf.cell(190, 4.5, txt=txt_linea, ln=True)
            
        pdf.ln(4)
        # -------------------------------------------
        
        # Título de la tabla de detalle
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 5, txt="Detalle de Lotes", ln=True, align='L')
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 6)
        anchos = [18, 24, 40, 24, 24, 14, 16, 30]
        columnas = dataframe_original.columns.tolist()
        
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 7, columnas[i], border=1, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", '', 6.5)
        for index, row in dataframe_original.iterrows():
            pdf.cell(anchos[0], 6, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 6, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 6, str(row['Producto']), border=1, align='L')
            pdf.cell(anchos[3], 6, fmt3(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 6, fmt3(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 6, fmt3(row['PNC']), border=1, align='R')
            pdf.cell(anchos[6], 6, row['% PNC'], border=1, align='C')
            pdf.cell(anchos[7], 6, row['Ratio de Conversión (%)'], border=1, align='C')
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            return pdf_output.encode('latin1')
        return pdf_output

    # Botón de Descarga Directa
    st.subheader("📥 Descargar Reporte")
    if len(df_filtrado) > 0:
        pdf_bytes = generar_pdf_bytes(df_filtrado)
        st.download_button(
            label="📥 Descargar Reporte en PDF",
            data=pdf_bytes,
            file_name="Reporte_Produccion_Calidad.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer el archivo de Drive o procesar los datos: {e}")
