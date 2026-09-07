import streamlit as st
import pandas as pd
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="Reporte de Producción", page_icon="🏭", layout="wide")
st.title("🏭 Generador de Reportes de Producción")

# 1. Conexión directa a Google Drive
# Reemplazá esto con el ID de tu archivo
ID_DEL_ARCHIVO = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf" 
URL_DRIVE = f"https://drive.google.com/uc?id={ID_DEL_ARCHIVO}"

try:
    st.info("Leyendo datos directamente desde Google Drive...")
    
    # 2. Lectura del Excel desde la nube indicando dónde arrancan los datos
    df = pd.read_excel(
        URL_DRIVE, 
        skiprows=6, # <--- ACÁ ESTÁ LA CLAVE: Saltea las filas 1 a 6.
        usecols=[0, 1, 3, 5, 6], 
        names=["Fecha", "Lote", "Litros Procesados", "Producto Terminado", "PNC"]
    )
    
    # Limpieza: quitamos filas donde la Fecha esté vacía
    df = df.dropna(subset=['Fecha'])
    
    # Convertimos la fecha para que se vea bien
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    # Forzar conversión a números para evitar errores si hay texto mezclado
    for col in ["Litros Procesados", "Producto Terminado", "PNC"]:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 3. Mostrar métricas rápidas
    st.subheader("📊 Resumen de Producción")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Litros Procesados", f"{df['Litros Procesados'].sum():.2f}")
    col2.metric("Total Prod. Terminado", f"{df['Producto Terminado'].sum():.2f}")
    col3.metric("Total PNC", f"{df['PNC'].sum():.2f}")

    st.dataframe(df, use_container_width=True)

    # 4. Función para generar el PDF
    def generar_pdf(dataframe):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="Reporte de Produccion", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", 'B', 10)
        anchos = [30, 30, 45, 45, 30]
        columnas = dataframe.columns.tolist()
        
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 10, columnas[i], border=1, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", '', 10)
        for index, row in dataframe.iterrows():
            pdf.cell(anchos[0], 10, str(row['Fecha']), border=1, align='C')
            pdf.cell(anchos[1], 10, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 10, str(row['Litros Procesados']), border=1, align='C')
            pdf.cell(anchos[3], 10, str(row['Producto Terminado']), border=1, align='C')
            pdf.cell(anchos[4], 10, str(row['PNC']), border=1, align='C')
            pdf.ln()
            
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf.output(temp_file.name)
        return temp_file.name

    # 5. Botón de Descarga
    st.subheader("📥 Descargar Reporte")
    if st.button("Generar PDF"):
        with st.spinner("Generando documento..."):
            ruta_pdf = generar_pdf(df)
            with open(ruta_pdf, "rb") as pdf_file:
                st.download_button(label="Descargar Reporte en PDF", data=pdf_file, file_name="Reporte_Produccion.pdf", mime="application/pdf")
            os.unlink(ruta_pdf)
            
except Exception as e:
    st.error(f"Hubo un error al leer el archivo de Drive: {e}")
