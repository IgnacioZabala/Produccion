import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="Reporte de Producción", page_icon="🏭", layout="wide")
st.title("Generador de Reportes de Producción")

# 1. Conexión directa a Google Drive
# Reemplazá esto con el ID de tu archivo
ID_DEL_ARCHIVO = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf" 
URL_DRIVE = f"https://drive.google.com/uc?id={ID_DEL_ARCHIVO}"

try:
    st.info("Leyendo datos directamente desde Google Drive...")
    
    # 2. Lectura del Excel
    df = pd.read_excel(
        URL_DRIVE, 
        skiprows=6, 
        usecols=[0, 1, 3, 5, 6], 
        names=["Fecha", "Lote", "Litros Procesados", "Producto Terminado", "PNC"]
    )
    
    df = df.dropna(subset=['Fecha'])
    
    # Le indicamos explícitamente a Pandas que el día va primero
    df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Fecha'])

    # Forzar conversión a números
    for col in ["Litros Procesados", "Producto Terminado", "PNC"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # NUEVO: Cálculo del Ratio de Conversión (%) por fila
    df['Ratio (%)'] = df.apply(
        lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.2f}%" if x['Litros Procesados'] > 0 else "0.00%", 
        axis=1
    )

    # 3. FILTROS LATERALES
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
    
    # FORMATO dd/mm/aaaa
    df_filtrado['Fecha'] = df_filtrado['Fecha'].dt.strftime('%d/%m/%Y')

    # 4. Mostrar métricas rápidas (AHORA CON 4 COLUMNAS)
    st.subheader("📊 Resumen de Producción (Datos Filtrados)")
    col1, col2, col3, col4 = st.columns(4)
    
    total_litros = df_filtrado['Litros Procesados'].sum()
    total_prod = df_filtrado['Producto Terminado'].sum()
    ratio_promedio = (total_prod / total_litros * 100) if total_litros > 0 else 0

    col1.metric("Total Litros Procesados", f"{total_litros:.2f}")
    col2.metric("Total Prod. Terminado", f"{total_prod:.2f}")
    col3.metric("Total PNC", f"{df_filtrado['PNC'].sum():.2f}")
    col4.metric("Ratio de Conversión Global", f"{ratio_promedio:.2f}%")

    st.dataframe(df_filtrado, use_container_width=True)

    # 5. Función para generar el PDF (AHORA CON LA COLUMNA DE RATIO)
    def generar_pdf(dataframe):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, txt="Reporte de Produccion", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", 'B', 9)
        # Ajustamos los anchos para que entren las 6 columnas en el ancho de la hoja (190mm)
        anchos = [22, 18, 35, 35, 20, 25]
        columnas = dataframe.columns.tolist()
        
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 10, columnas[i][:15], border=1, align='C') # [:15] acorta nombres muy largos en el título
        pdf.ln()
        
        pdf.set_font("Arial", '', 9)
        for index, row in dataframe.iterrows():
            pdf.cell(anchos[0], 10, str(row['Fecha']), border=1, align='C')
            pdf.cell(anchos[1], 10, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 10, str(row['Litros Procesados']), border=1, align='C')
            pdf.cell(anchos[3], 10, str(row['Producto Terminado']), border=1, align='C')
            pdf.cell(anchos[4], 10, str(row['PNC']), border=1, align='C')
            pdf.cell(anchos[5], 10, str(row['Ratio (%)']), border=1, align='C')
            pdf.ln()
            
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(temp_file.name)
        return temp_file.name

    # 6. Botón de Descarga
    st.subheader("📥 Descargar Reporte")
    if len(df_filtrado) > 0:
        if st.button("Generar PDF con los datos en pantalla"):
            with st.spinner("Generando documento..."):
                ruta_pdf = generar_pdf(df_filtrado)
                with open(ruta_pdf, "rb") as pdf_file:
                    st.download_button(label="Descargar Reporte en PDF", data=pdf_file, file_name="Reporte_Produccion.pdf", mime="application/pdf")
                os.unlink(ruta_pdf)
    else:
        st.warning("No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer el archivo de Drive o procesar los datos: {e}")
