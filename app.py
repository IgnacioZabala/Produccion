import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
import tempfile
import os

# Configuración de la página
st.set_page_config(page_title="Reporte de Producción", page_icon="🏭", layout="wide")

st.title("Generador de Reportes de Producción")
st.markdown("Subí el archivo **RE-PRO-52 Registro produccion.xlsx** para visualizar los datos y descargar el reporte en PDF.")

# 1. Carga del archivo Excel
archivo_subido = st.file_uploader("Cargar Excel de Producción", type=["xlsx"])

if archivo_subido is not None:
    try:
        # 2. Lectura del Excel (Solo las columnas especificadas: A=0, B=1, D=3, F=5, G=6)
        # Se asume que la fila 0 es el encabezado. Si tus datos empiezan más abajo, ajustá el 'skiprows'
        df = pd.read_excel(
            archivo_subido, 
            usecols=[0, 1, 3, 5, 6], 
            names=["Fecha", "Lote", "Litros Procesados", "Producto Terminado", "PNC"]
        )
        
        # Limpieza básica: quitar filas donde la Fecha esté vacía
        df = df.dropna(subset=['Fecha'])
        
        # Convertir fecha a formato string legible (día/mes/año)
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')
        
        # Llenar valores nulos con 0 para los cálculos numéricos
        df = df.fillna(0)

        # 3. Mostrar métricas rápidas
        st.subheader("📊 Resumen de Producción")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Litros Procesados", f"{df['Litros Procesados'].sum():.2f}")
        col2.metric("Total Prod. Terminado", f"{df['Producto Terminado'].sum():.2f}")
        col3.metric("Total PNC", f"{df['PNC'].sum():.2f}")

        # Mostrar la tabla en la app
        st.dataframe(df, use_container_width=True)

        # 4. Función para generar el PDF
        def generar_pdf(dataframe):
            pdf = FPDF()
            pdf.add_page()
            
            # Título del PDF
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="Reporte de Produccion", ln=True, align='C')
            pdf.ln(10)
            
            # Encabezados de la tabla
            pdf.set_font("Arial", 'B', 10)
            anchos = [30, 30, 45, 45, 30] # Ancho de las columnas
            columnas = dataframe.columns.tolist()
            
            for i in range(len(columnas)):
                pdf.cell(anchos[i], 10, columnas[i], border=1, align='C')
            pdf.ln()
            
            # Datos de la tabla
            pdf.set_font("Arial", '', 10)
            for index, row in dataframe.iterrows():
                pdf.cell(anchos[0], 10, str(row['Fecha']), border=1, align='C')
                pdf.cell(anchos[1], 10, str(row['Lote']), border=1, align='C')
                pdf.cell(anchos[2], 10, str(row['Litros Procesados']), border=1, align='C')
                pdf.cell(anchos[3], 10, str(row['Producto Terminado']), border=1, align='C')
                pdf.cell(anchos[4], 10, str(row['PNC']), border=1, align='C')
                pdf.ln()
                
            # Guardar en un archivo temporal
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(temp_file.name)
            return temp_file.name

        # 5. Botón de Descarga
        st.subheader("📥 Descargar Reporte")
        if st.button("Generar PDF"):
            with st.spinner("Generando documento..."):
                ruta_pdf = generar_pdf(df)
                
                with open(ruta_pdf, "rb") as pdf_file:
                    st.download_button(
                        label="Descargar Reporte en PDF",
                        data=pdf_file,
                        file_name="Reporte_Produccion.pdf",
                        mime="application/pdf"
                    )
                # Limpiar archivo temporal
                os.unlink(ruta_pdf)
                
    except Exception as e:
        st.error(f"Hubo un error al procesar el archivo: {e}")
        st.info("Asegurate de que el Excel tenga los datos en las columnas correctas (A, B, D, F, G).")
