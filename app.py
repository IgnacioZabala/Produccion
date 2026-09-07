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
    
    # Lectura del Excel
    df = pd.read_excel(
        URL_DRIVE, 
        skiprows=6, 
        usecols=[0, 1, 3, 5, 6], 
        names=["Fecha", "Lote", "Litros Procesados", "Producto Terminado", "PNC"]
    )
    
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

    # ORDEN EXPLICITO DE COLUMNAS (Asegura que queden en el orden lógico correcto)
    columnas_ordenadas = [
        'Fecha', 'Lote', 'Producto', 'Litros Procesados', 
        'Producto Terminado', 'PNC', '% PNC', 'Ratio de Conversión (%)'
    ]
    df = df[columnas_ordenadas + ['Año' if 'Año' in df else 'Fecha', 'Mes' if 'Mes' in df else 'Fecha', 'Grupo']] # Mantenemos temporales temporalmente

    # FILTROS LATERALES (Solo Año, Mes y Grupo)
    st.sidebar.header("Filtros de Búsqueda")
    
    df['Año'] = df['Fecha'].dt.year
    df['Mes'] = df['Fecha'].dt.month

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

    # Nos quedamos estrictamente con las 8 columnas finales ordenadas
    df_filtrado = df_filtrado[columnas_ordenadas]

    # Totales y métricas globales
    total_litros = df_filtrado['Litros Procesados'].sum()
    total_prod = df_filtrado['Producto Terminado'].sum()
    total_pnc = df_filtrado['PNC'].sum()
    
    ratio_promedio = (total_prod / total_litros * 100) if total_litros > 0 else 0
    pnc_promedio = (total_pnc / total_litros * 100) if total_litros > 0 else 0

    # Mostrar métricas rápidas (5 columnas)
    st.subheader("📊 Resumen de Producción y Calidad")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Litros Procesados", fmt3(total_litros))
    col2.metric("Prod. Terminado", fmt3(total_prod))
    col3.metric("Total PNC", fmt3(total_pnc))
    col4.metric("Ratio Conversión", f"{ratio_promedio:.3f}%".replace(".", ","))
    col5.metric("% PNC Global", f"{pnc_promedio:.3f}%".replace(".", ","))

    # Preparamos una copia visual para la tabla web
    df_display = df_filtrado.copy()
    df_display['Litros Procesados'] = df_display['Litros Procesados'].apply(fmt3)
    df_display['Producto Terminado'] = df_display['Producto Terminado'].apply(fmt3)
    df_display['PNC'] = df_display['PNC'].apply(fmt3)
    df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_display, use_container_width=True)

    # Función para generar el PDF en A4 vertical optimizado para 8 columnas
    def generar_pdf_bytes(dataframe_original):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, txt="Reporte de Producción y Calidad", ln=True, align='C')
        pdf.ln(4)
        
        pdf.set_font("Arial", 'B', 6)
        
        # Anchos exactos que suman 190 mm (PNC achicado a 14mm, Producto ampliado a 40mm)
        # Orden: Fecha, Lote, Producto, Litros, Terminado, PNC, % PNC, Ratio
        anchos = [18, 24, 40, 24, 24, 14, 16, 30]
        columnas = dataframe_original.columns.tolist()
        
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 8, columnas[i], border=1, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", '', 6.5)
        for index, row in dataframe_original.iterrows():
            pdf.cell(anchos[0], 7, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 7, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 7, str(row['Producto']), border=1, align='L')
            pdf.cell(anchos[3], 7, fmt3(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 7, fmt3(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 7, fmt3(row['PNC']), border=1, align='R')
            pdf.cell(anchos[6], 7, row['% PNC'], border=1, align='C')
            pdf.cell(anchos[7], 7, row['Ratio de Conversión (%)'], border=1, align='C')
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
