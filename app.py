import streamlit as st
import pandas as pd
from fpy import FPDF # or fpdf
import os

# Configurar fpdf import compatible
from fpdf import FPDF

st.set_page_config(page_title="Reporte de Producción", page_icon="🏭", layout="wide")
st.title("Generador de Reportes de Producción")

# ID de Google Drive (ya integrado)
ID_DEL_ARCHIVO = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf" # Reemplazá con tu ID real de Drive
URL_DRIVE = f"https://drive.google.com/uc?id={ID_DEL_ARCHIVO}"

# Función para formatear números con 3 decimales: 1.234.567,890
def fmt3(val):
    try:
        return f"{val:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

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

    # Cálculo del Ratio de Conversión (%) por fila con 3 decimales
    df['Ratio de Conversión (%)'] = df.apply(
        lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.3f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,000%", 
        axis=1
    )

    # Filtros laterales
    st.sidebar.header("Filtros de Búsqueda")
    
    df['Año'] = df['Fecha'].dt.year
    df['Mes'] = df['Fecha'].dt.month
    df['Semana'] = df['Fecha'].dt.isocalendar().week

    opciones_anio = ["Todos"] + sorted(df['Año'].unique().tolist())
    opciones_mes = ["Todos"] + sorted(df['Mes'].unique().tolist())
    opciones_semana = ["Todos"] + sorted(df['Semana'].unique().tolist())

    filtro_anio = st.sidebar.selectbox("Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("Seleccionar Mes", opciones_mes)
    filtro_semana = st.sidebar.selectbox("Seleccionar Semana", opciones_semana)

    df_filtrado = df.copy()
    if filtro_anio != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
    if filtro_semana != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Semana'] == filtro_semana]

    df_filtrado = df_filtrado.drop(columns=['Año', 'Mes', 'Semana'])

    # Totales para métricas
    total_litros = df_filtrado['Litros Procesados'].sum()
    total_prod = df_filtrado['Producto Terminado'].sum()
    total_pnc = df_filtrado['PNC'].sum()
    ratio_promedio = (total_prod / total_litros * 100) if total_litros > 0 else 0

    # Mostrar métricas rápidas con formato aplicado
    st.subheader("📊 Resumen de Producción (Datos Filtrados)")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Litros Procesados", fmt3(total_litros))
    col2.metric("Total Prod. Terminado", fmt3(total_prod))
    col3.metric("Total PNC", fmt3(total_pnc))
    col4.metric("Ratio de Conversión Global", f"{ratio_promedio:.3f}%".replace(".", ","))

    # Preparamos una copia visual para la tabla web con los números formateados
    df_display = df_filtrado.copy()
    df_display['Litros Procesados'] = df_display['Litros Procesados'].apply(fmt3)
    df_display['Producto Terminado'] = df_display['Producto Terminado'].apply(fmt3)
    df_display['PNC'] = df_display['PNC'].apply(fmt3)
    df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_display, use_container_width=True)

    # Función para generar el PDF en A4 vertical y ancho ajustado (190mm total)
    def generar_pdf_bytes(dataframe_original):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(190, 10, txt="Reporte de Producción", ln=True, align='C')
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 8)
        # Anchos exactos que suman 190mm (ancho útil de hoja A4 vertical con margenes de 10mm)
        anchos = [25, 15, 40, 40, 25, 45]
        columnas = dataframe_original.columns.tolist()
        
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 8, columnas[i], border=1, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", '', 8)
        for index, row in dataframe_original.iterrows():
            pdf.cell(anchos[0], 7, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 7, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 7, fmt3(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[3], 7, fmt3(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[4], 7, fmt3(row['PNC']), border=1, align='R')
            pdf.cell(anchos[5], 7, row['Ratio de Conversión (%)'], border=1, align='C')
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        if isinstance(pdf_output, str):
            return pdf_output.encode('latin1')
        return pdf_output

    # Botón de Descarga Directa (Un solo botón)
    st.subheader("📥 Descargar Reporte")
    if len(df_filtrado) > 0:
        pdf_bytes = generar_pdf_bytes(df_filtrado)
        st.download_button(
            label="📥 Descargar Reporte en PDF",
            data=pdf_bytes,
            file_name="Reporte_Produccion.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer el archivo de Drive o procesar los datos: {e}")
