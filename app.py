import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

st.set_page_config(page_title="Reporte de Producción y Calidad", page_icon="🏭", layout="wide")
st.title("Reporte de producción y recepción de leche")

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

    # SEGURIDAD: Validar si hay filas antes de desempaquetar
    if len(df_prod) > 0:
        df_prod['Producto'], df_prod['Grupo'] = zip(*df_prod['Lote'].astype(str).apply(procesar_lote))
    else:
        df_prod['Producto'] = []
        df_prod['Grupo'] = []

    df_prod['Año'] = df_prod['Fecha'].dt.year
    df_prod['Mes'] = df_prod['Fecha'].dt.month

    # 2. Leer Recibo de Leche (Columna D = índices 3, Año 2026 desde fila 375 en adelante)
    raw_recibo = pd.read_excel(URL_RECIBO)
    df_recibo = pd.DataFrame()
    df_recibo['Fecha_Raw'] = raw_recibo.iloc[:, 0] 
    df_recibo['Litros Ingresados'] = pd.to_numeric(raw_recibo.iloc[:, 3], errors='coerce').fillna(0)
    
    df_recibo['Fecha'] = pd.to_datetime(df_recibo['Fecha_Raw'], dayfirst=True, errors='coerce')
    
    anios_recibo = []
    meses_recibo = []
    for idx, row in df_recibo.iterrows():
        f = row['Fecha']
        if idx >= 374: # Desde la fila 375 el año es 2026
            anio = 2026
        else:
            anio = f.year if pd.notnull(f) else 2026
            
        mes = f.month if pd.notnull(f) else 1
        anios_recibo.append(anio)
        meses_recibo.append(mes)
        
    df_recibo['Año'] = anios_recibo
    df_recibo['Mes'] = meses_recibo

    recibo_mensual = df_recibo.groupby(['Año', 'Mes'])['Litros Ingresados'].sum().reset_index()

    # Filtros laterales
    st.sidebar.header("Filtros de Búsqueda")
    opciones_anio = ["Todos"] + (sorted(df_prod['Año'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_mes = ["Todos"] + (sorted(df_prod['Mes'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_grupo = ["Todos", "Coopagro", "Mastellone"]

    filtro_anio = st.sidebar.selectbox("Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("Seleccionar Mes", opciones_mes)
    filtro_grupo = st.sidebar.selectbox("Seleccionar Grupo", opciones_grupo)

    # Filtrar Producción
    df_filtrado = df_prod.copy()
    if len(df_filtrado) > 0:
        if filtro_anio != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
        if filtro_grupo != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo]

    columnas_ordenadas = [
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
        df_filtrado = df_filtrado[columnas_ordenadas]
    else:
        df_filtrado = pd.DataFrame(columns=columnas_ordenadas)

    # Filtrar Recibo
    df_recibo_filtrado = recibo_mensual.copy()
    if filtro_anio != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Mes'] == filtro_mes]
    
    total_litros_ingresados = df_recibo_filtrado['Litros Ingresados'].sum()

    # Totales globales
    total_litros_proc = df_filtrado['Litros Procesados'].sum() if len(df_filtrado) > 0 else 0
    total_prod = df_filtrado['Producto Terminado'].sum() if len(df_filtrado) > 0 else 0
    total_pnc = df_filtrado['PNC'].sum() if len(df_filtrado) > 0 else 0
    
    ratio_ponderado = (total_prod / total_litros_proc * 100) if total_litros_proc > 0 else 0
    pnc_promedio = (total_pnc / total_litros_proc * 100) if total_litros_proc > 0 else 0
    rendimiento_ingreso = (total_prod / total_litros_ingresados * 100) if total_litros_ingresados > 0 else 0

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
            anios_unicos = df_filtrado['Fecha'].dt.year.unique()
            anio_str = str(anios_unicos[0]) if len(anios_unicos) == 1 else "2026"
        else:
            anio_str = "2026"

    titulo_pdf = f"Reporte de producción {mes_str} {anio_str}".strip()

    # Mostrar métricas rápidas en pantalla
    st.subheader("Resumen General de Planta")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Litros Ingresados", fmt2(total_litros_ingresados))
    c2.metric("Litros Procesados", fmt2(total_litros_proc))
    c3.metric("Prod. Terminado", fmt2(total_prod))
    c4.metric("Total PNC", fmt2(total_pnc))
    c5.metric("Ratio Ponderado", f"{ratio_ponderado:.2f}%".replace(".", ","))
    c6.metric("Rend. Ingreso vs Term.", f"{rendimiento_ingreso:.2f}%".replace(".", ","))

    # Resumen por producto en pantalla
    st.subheader("Cantidad por Producto")
    if len(df_filtrado) > 0:
        resumen_prod = df_filtrado.groupby('Producto')[['Litros Procesados', 'Producto Terminado', 'PNC']].sum().reset_index()
        resumen_prod['Ratio de Conversión (%)'] = resumen_prod.apply(
            lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", 
            axis=1
        )
        resumen_display = resumen_prod.copy()
        resumen_display['Litros Procesados'] = resumen_display['Litros Procesados'].apply(fmt2)
        resumen_display['Producto Terminado'] = resumen_display['Producto Terminado'].apply(fmt2)
        resumen_display['PNC'] = resumen_display['PNC'].apply(fmt2)
        st.dataframe(resumen_display, use_container_width=True)
    else:
        st.info("No hay datos para mostrar con los filtros seleccionados.")

    # Detalle de lotes en pantalla
    st.subheader("Detalle de Lotes")
    if len(df_filtrado) > 0:
        df_display = df_filtrado.copy()
        df_display['Litros Procesados'] = df_display['Litros Procesados'].apply(fmt2)
        df_display['Producto Terminado'] = df_display['Producto Terminado'].apply(fmt2)
        df_display['PNC'] = df_display['PNC'].apply(fmt2)
        df_display['Fecha'] = df_display['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_display, use_container_width=True)

    # Función para generar el PDF completo
    def generar_pdf_bytes(dataframe_original, titulo_dinamico, lit_ingresados, rend_ingreso):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(190, 7, txt=titulo_dinamico, ln=True, align='C')
        pdf.ln(3)
        
        # --- SECCIÓN DE RESUMEN ---
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 5, txt="Resumen", ln=True, align='L')
        
        pdf.set_font("Arial", '', 8)
        tot_lit = dataframe_original['Litros Procesados'].sum()
        tot_pro = dataframe_original['Producto Terminado'].sum()
        tot_pn = dataframe_original['PNC'].sum()
        rat_pond = (tot_pro / tot_lit * 100) if tot_lit > 0 else 0
        pnc_glob = (tot_pn / tot_lit * 100) if tot_lit > 0 else 0
        
        rat_pond_str = f"{rat_pond:.2f}%".replace(".", ",")
        pnc_glob_str = f"{pnc_glob:.2f}%".replace(".", ",")
        rend_str = f"{rend_ingreso:.2f}%".replace(".", ",")
        
        pdf.cell(95, 5, txt=f"Total Litros Ingresados: {fmt2(lit_ingresados)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio Ponderado: {rat_pond_str}", ln=1)
        pdf.cell(95, 5, txt=f"Total Litros Procesados: {fmt2(tot_lit)}", ln=0)
        pdf.cell(95, 5, txt=f"Rendimiento Ingresado vs Term.: {rend_str}", ln=1)
        pdf.cell(95, 5, txt=f"Total Producto Terminado: {fmt2(tot_pro)}", ln=0)
        pdf.cell(95, 5, txt=f"Total PNC: {fmt2(tot_pn)} (% PNC Global: {pnc_glob_str})", ln=1)
        pdf.ln(2)
        
        # Cantidad por producto con ratio
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(190, 5, txt="Cantidad por Producto:", ln=True, align='L')
        pdf.set_font("Arial", '', 7.5)
        
        prod_res = dataframe_original.groupby('Producto')[['Litros Procesados', 'Producto Terminado']].sum().reset_index()
        for idx, row in prod_res.iterrows():
            ratio_prod = (row['Producto Terminado'] / row['Litros Procesados'] * 100) if row['Litros Procesados'] > 0 else 0
            ratio_prod_str = f"{ratio_prod:.2f}%".replace(".", ",")
            txt_linea = f"- {row['Producto']}: Litros Proc. {fmt2(row['Litros Procesados'])} | Prod. Terminado: {fmt2(row['Producto Terminado'])} | Ratio: {ratio_prod_str}"
            pdf.cell(190, 4.5, txt=txt_linea, ln=True)
            
        pdf.ln(4)
        
        # Detalle de lotes
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
            pdf.cell(anchos[3], 6, fmt2(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 6, fmt2(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 6, fmt2(row['PNC']), border=1, align='R')
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
        pdf_bytes = generar_pdf_bytes(df_filtrado, titulo_pdf, total_litros_ingresados, rendimiento_ingreso)
        st.download_button(
            label="📥 Descargar Reporte en PDF",
            data=pdf_bytes,
            file_name="Reporte_Produccion.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer los archivos de Drive o procesar los datos: {e}")
