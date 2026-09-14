import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
import traceback

st.set_page_config(page_title="Reporte de Producción y Recepción", page_icon="🏭", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# ESTILOS CSS PROFESIONALES (UI/UX)
# ==========================================
st.markdown("""
    <style>
        .stApp { background-color: #f4f6f9; }
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e0e4e8;
            padding: 15px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.04);
            transition: transform 0.2s ease-in-out;
        }
        div[data-testid="metric-container"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 10px rgba(0, 0, 0, 0.08);
        }
        .main-header {
            color: #1e293b;
            font-weight: 700;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
            margin-bottom: 20px;
        }
        thead tr th {
            background-color: #f8fafc !important;
            color: #475569 !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">🏭 Reporte de Producción y Recepción</h1>', unsafe_allow_html=True)

# ==========================================
# CONFIGURACIÓN DE IDs DE GOOGLE DRIVE
# ==========================================
ID_PRODUCCION = "1wuIpzYmVuflX_pWoPt4Pz9olWF4LLKOf"
ID_RECIBO_INTERNO = "16Uh0EwP8tyW79TfJlvcjE8li5Lc6RSLj"
ID_RECIBO_MASTELLONE = "1sOBujAyTijDtNze0m9q5ZU2-7xWfc584"

URL_PRODUCCION = f"https://drive.google.com/uc?export=download&id={ID_PRODUCCION}"
URL_RECIBO_INTERNO = f"https://drive.google.com/uc?export=download&id={ID_RECIBO_INTERNO}"
URL_RECIBO_MASTELLONE = f"https://drive.google.com/uc?export=download&id={ID_RECIBO_MASTELLONE}"

def fmt2(val):
    try:
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

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
        '288': 'Coopagro', '125': 'Coopagro', '488': 'Coopagro', '840': 'Mastellone'
    }
    return mapping_prod.get(prod_code, f"Desconocido ({prod_code})"), mapping_grupo.get(prod_code, 'Otro')

try:
    with st.spinner("Sincronizando datos desde Google Drive..."):
        # 1. Leer Producción
        raw_prod = pd.read_excel(URL_PRODUCCION, skiprows=6)
        df_prod = pd.DataFrame()
        df_prod['Fecha'] = pd.to_datetime(raw_prod.iloc[:, 0], dayfirst=True, errors='coerce')
        df_prod['Lote'] = raw_prod.iloc[:, 1]
        df_prod['Litros Procesados'] = pd.to_numeric(raw_prod.iloc[:, 3], errors='coerce').fillna(0)
        df_prod['Producto Terminado'] = pd.to_numeric(raw_prod.iloc[:, 5], errors='coerce').fillna(0)
        df_prod['PNC'] = pd.to_numeric(raw_prod.iloc[:, 6], errors='coerce').fillna(0)
        
        df_prod = df_prod.dropna(subset=['Fecha'])

        if len(df_prod) > 0:
            df_prod['Producto'], df_prod['Grupo'] = zip(*df_prod['Lote'].astype(str).apply(procesar_lote))
        else:
            df_prod['Producto'] = []
            df_prod['Grupo'] = []

        df_prod['Fecha'] = pd.to_datetime(df_prod['Fecha'])
        df_prod['Año'] = df_prod['Fecha'].dt.year
        df_prod['Mes'] = df_prod['Fecha'].dt.month

        # 2A. Leer Recibo de Leche Interno
        raw_recibo_int = pd.read_excel(URL_RECIBO_INTERNO, skiprows=4)
        df_recibo_int = pd.DataFrame()
        df_recibo_int['Fecha'] = pd.to_datetime(raw_recibo_int.iloc[:, 1], dayfirst=True, errors='coerce')
        df_recibo_int['Litros Ingresados'] = pd.to_numeric(raw_recibo_int.iloc[:, 4], errors='coerce').fillna(0)
        df_recibo_int = df_recibo_int.dropna(subset=['Fecha'])
        df_recibo_int['Año'] = df_recibo_int['Fecha'].dt.year
        df_recibo_int['Mes'] = df_recibo_int['Fecha'].dt.month
        
        # 2B. Leer Recibo de Leche Mastellone (BLINDADO: Solo columnas D y Q)
        df_recibo_mast = pd.DataFrame(columns=['Fecha', 'Litros Ingresados', 'Año', 'Mes'])
        try:
            xls_mast = pd.ExcelFile(URL_RECIBO_MASTELLONE)
            nombre_solapa = next((s for s in xls_mast.sheet_names if 'cisterna' in s.lower() or 'recibo' in s.lower()), xls_mast.sheet_names[0])
            
            # usecols="D,Q" trae EXCLUSIVAMENTE esas dos columnas, sin importar las filas combinadas o títulos.
            raw_recibo_mast = pd.read_excel(URL_RECIBO_MASTELLONE, sheet_name=nombre_solapa, usecols="D,Q", header=None, names=['Fecha_Raw', 'Litros_Raw'])
            
            temp_mast = pd.DataFrame()
            
            # Convertimos la columna D a fecha de forma segura
            temp_mast['Fecha'] = pd.to_datetime(raw_recibo_mast['Fecha_Raw'], dayfirst=True, errors='coerce')
            
            # Recuperamos fechas que Excel pueda estar exportando como números de serie
            mask_nat = temp_mast['Fecha'].isna() & raw_recibo_mast['Fecha_Raw'].notna()
            if mask_nat.any():
                temp_mast.loc[mask_nat, 'Fecha'] = pd.to_datetime(pd.to_numeric(raw_recibo_mast.loc[mask_nat, 'Fecha_Raw'], errors='coerce'), unit='D', origin='1899-12-30', errors='coerce')

            # Convertimos la columna Q a números (litros)
            temp_mast['Litros Ingresados'] = pd.to_numeric(raw_recibo_mast['Litros_Raw'], errors='coerce').fillna(0)
            
            # Solo guardamos las filas que sí tienen una fecha real
            df_recibo_mast = temp_mast.dropna(subset=['Fecha']).copy()
            df_recibo_mast['Año'] = df_recibo_mast['Fecha'].dt.year
            df_recibo_mast['Mes'] = df_recibo_mast['Fecha'].dt.month
        except Exception as e_mast:
            st.sidebar.warning(f"Aviso Mastellone: No se pudo cargar automáticamente. Detalle: {e_mast}")

    # ==========================================
    # BARRA LATERAL (FILTROS)
    # ==========================================
    st.sidebar.markdown("### 🔍 Filtros de Búsqueda")
    
    opciones_anio = ["Todos"] + (sorted(df_prod['Año'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_mes = ["Todos"] + (sorted(df_prod['Mes'].unique().tolist()) if len(df_prod) > 0 else [])
    opciones_grupo = ["Todos", "Coopagro", "Mastellone"]

    filtro_anio = st.sidebar.selectbox("📅 Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("📆 Seleccionar Mes", opciones_mes)
    filtro_grupo = st.sidebar.selectbox("🏢 Seleccionar Grupo", opciones_grupo)
        
    st.sidebar.markdown("---")

    # ==========================================
    # PROCESAMIENTO DE DATOS FILTRADOS
    # ==========================================
    df_filtrado = df_prod.copy()
    if len(df_filtrado) > 0:
        if filtro_anio != "Todos": df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
        if filtro_mes != "Todos": df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
        if filtro_grupo != "Todos": df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo]

    # DataFrame Consolidado (Vista Única)
    df_consolidado = df_filtrado.copy()
    if len(df_consolidado) > 0:
        df_consolidado_raw = df_prod.copy()
        if filtro_anio != "Todos": df_consolidado_raw = df_consolidado_raw[df_consolidado_raw['Año'] == filtro_anio]
        if filtro_mes != "Todos": df_consolidado_raw = df_consolidado_raw[df_consolidado_raw['Mes'] == filtro_mes]
        if filtro_grupo != "Todos": df_consolidado_raw = df_consolidado_raw[df_consolidado_raw['Grupo'] == filtro_grupo]
            
        df_consolidado_raw['PT_Total'] = df_consolidado_raw['Producto Terminado'] + df_consolidado_raw['PNC']
        df_consolidado_raw['Ratio Consolidado (%)'] = df_consolidado_raw.apply(
            lambda x: f"{(x['PT_Total'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
        )
        
        df_consolidado = pd.DataFrame()
        df_consolidado['Fecha'] = df_consolidado_raw['Fecha']
        df_consolidado['Lote'] = df_consolidado_raw['Lote']
        df_consolidado['Producto'] = df_consolidado_raw['Producto']
        df_consolidado['Litros Procesados'] = df_consolidado_raw['Litros Procesados']
        df_consolidado['Producto Terminado'] = df_consolidado_raw['PT_Total']
        df_consolidado['Ratio de Conversión (%)'] = df_consolidado_raw['Ratio Consolidado (%)']
    else:
        df_consolidado = pd.DataFrame(columns=['Fecha', 'Lote', 'Producto', 'Litros Procesados', 'Producto Terminado', 'Ratio de Conversión (%)'])

    # --- CÁLCULO INTELIGENTE DE LITROS INGRESADOS ---
    df_int_filt = df_recibo_int.copy()
    df_mast_filt = df_recibo_mast.copy()

    if filtro_anio != "Todos":
        df_int_filt = df_int_filt[df_int_filt['Año'] == filtro_anio]
        df_mast_filt = df_mast_filt[df_mast_filt['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_int_filt = df_int_filt[df_int_filt['Mes'] == filtro_mes]
        df_mast_filt = df_mast_filt[df_mast_filt['Mes'] == filtro_mes]

    litros_int_sum = df_int_filt['Litros Ingresados'].sum()
    litros_mast_sum = df_mast_filt['Litros Ingresados'].sum()

    if filtro_grupo == "Mastellone":
        total_litros_ingresados = litros_mast_sum
    elif filtro_grupo == "Coopagro":
        total_litros_ingresados = litros_int_sum
    else: # "Todos"
        total_litros_ingresados = litros_int_sum + litros_mast_sum

    total_litros_proc = df_filtrado['Litros Procesados'].sum() if len(df_filtrado) > 0 else 0
    total_prod_consolidado = df_consolidado['Producto Terminado'].sum() if len(df_consolidado) > 0 else 0
    
    ratio_ponderado_proc = (total_prod_consolidado / total_litros_proc * 100) if total_litros_proc > 0 else 0
    rendimiento_ingreso = (total_prod_consolidado / total_litros_ingresados * 100) if total_litros_ingresados > 0 else 0

    meses_nombres = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
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

    if filtro_grupo == "Mastellone":
        prefijo_titulo = "Reporte de produccion Mastellone"
    elif filtro_grupo == "Coopagro":
        prefijo_titulo = "Reporte de produccion Coopagro"
    else:
        prefijo_titulo = "Reporte de produccion"

    titulo_pdf = f"{prefijo_titulo} {mes_str} {anio_str}".strip()

    # ==========================================
    # INTERFAZ PRINCIPAL (VISTA ÚNICA)
    # ==========================================
    st.markdown("### 📈 Indicadores Consolidados")
    g1, g2, g3 = st.columns(3)
    g1.metric("Total Lts Ingresados", fmt2(total_litros_ingresados))
    g2.metric("Total Lts Procesados", fmt2(total_litros_proc))
    g3.metric("Total Producto Terminado", fmt2(total_prod_consolidado))
    
    g4, g5, _ = st.columns(3)
    g4.metric("Ratio PT / Litros procesados", f"{ratio_ponderado_proc:.2f}%".replace(".", ","))
    g5.metric("Ratio PT / Litros ingresados", f"{rendimiento_ingreso:.2f}%".replace(".", ","))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📋 Registro de Lotes")
    if len(df_consolidado) > 0:
        df_consolidado_display = df_consolidado.copy()
        df_consolidado_display['Litros Procesados'] = df_consolidado_display['Litros Procesados'].apply(fmt2)
        df_consolidado_display['Producto Terminado'] = df_consolidado_display['Producto Terminado'].apply(fmt2)
        df_consolidado_display['Fecha'] = df_consolidado_display['Fecha'].dt.strftime('%d/%m/%Y')
        st.dataframe(df_consolidado_display, use_container_width=True, hide_index=True, height=350)
    else:
        st.info("No hay lotes en el período seleccionado.")

    # ==========================================
    # FUNCIONES DE EXPORTACIÓN (PDF ÚNICO)
    # ==========================================
    def generar_pdf(dataframe_consolidado, titulo_dinamico, lit_ingresados, rend_ingreso, ratio_pond, df_prod_raw):
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(190, 7, txt=titulo_dinamico, ln=True, align='C')
        pdf.ln(3)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Resumen", ln=True, align='L')
        pdf.set_font("Arial", '', 9)
        
        tot_lit = dataframe_consolidado['Litros Procesados'].sum()
        tot_pro = dataframe_consolidado['Producto Terminado'].sum()
        
        pdf.cell(95, 5, txt=f"Total Litros Ingresados: {fmt2(lit_ingresados)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio PT / Litros procesados: {ratio_pond:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Litros Procesados: {fmt2(tot_lit)}", ln=0)
        pdf.cell(95, 5, txt=f"Ratio PT / Litros ingresados: {rend_ingreso:.2f}%".replace(".", ","), ln=1)
        pdf.cell(95, 5, txt=f"Total Producto Terminado: {fmt2(tot_pro)}", ln=1)
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Cantidad por Producto:", ln=True, align='L')
        pdf.set_font("Arial", '', 8)
        
        prod_res = df_prod_raw.groupby('Producto')[['Litros Procesados', 'PT_Total']].sum().reset_index()
        for idx, row in prod_res.iterrows():
            ratio_prod = (row['PT_Total'] / row['Litros Procesados'] * 100) if row['Litros Procesados'] > 0 else 0
            ratio_prod_str = f"{ratio_prod:.2f}%".replace(".", ",")
            txt_linea = f"- {row['Producto']}: Litros Proc. {fmt2(row['Litros Procesados'])} | Prod. Terminado: {fmt2(row['PT_Total'])} | Ratio: {ratio_prod_str}"
            pdf.cell(190, 4.5, txt=txt_linea, ln=True)
            
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 5, txt="Detalle de Lotes", ln=True, align='L')
        pdf.ln(2)
        
        pdf.set_font("Arial", 'B', 7)
        anchos = [20, 28, 42, 32, 38, 30]
        columnas = dataframe_consolidado.columns.tolist()
        for i in range(len(columnas)):
            pdf.cell(anchos[i], 7, columnas[i], border=1, align='C')
        pdf.ln()
        
        pdf.set_font("Arial", '', 7)
        for index, row in dataframe_consolidado.iterrows():
            pdf.cell(anchos[0], 6, row['Fecha'].strftime('%d/%m/%Y'), border=1, align='C')
            pdf.cell(anchos[1], 6, str(row['Lote']), border=1, align='C')
            pdf.cell(anchos[2], 6, str(row['Producto']), border=1, align='L')
            pdf.cell(anchos[3], 6, fmt2(row['Litros Procesados']), border=1, align='R')
            pdf.cell(anchos[4], 6, fmt2(row['Producto Terminado']), border=1, align='R')
            pdf.cell(anchos[5], 6, row['Ratio de Conversión (%)'], border=1, align='C')
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        return pdf_output.encode('latin1') if isinstance(pdf_output, str) else pdf_output

    # ==========================================
    # BOTÓN DE DESCARGA ÚNICO
    # ==========================================
    st.markdown("---")
    st.markdown("### 📥 Exportar Reporte")
    
    if len(df_consolidado) > 0:
        df_prod_raw_pdf = df_prod.copy()
        if filtro_anio != "Todos": df_prod_raw_pdf = df_prod_raw_pdf[df_prod_raw_pdf['Año'] == filtro_anio]
        if filtro_mes != "Todos": df_prod_raw_pdf = df_prod_raw_pdf[df_prod_raw_pdf['Mes'] == filtro_mes]
        if filtro_grupo != "Todos": df_prod_raw_pdf = df_prod_raw_pdf[df_prod_raw_pdf['Grupo'] == filtro_grupo]
        df_prod_raw_pdf['PT_Total'] = df_prod_raw_pdf['Producto Terminado'] + df_prod_raw_pdf['PNC']

        pdf_bytes = generar_pdf(df_consolidado, titulo_pdf, total_litros_ingresados, rendimiento_ingreso, ratio_ponderado_proc, df_prod_raw_pdf)
        
        st.download_button(
            label="📄 Descargar Reporte en PDF",
            data=pdf_bytes,
            file_name=f"{titulo_pdf.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    else:
        st.warning("⚠️ No hay datos para los filtros seleccionados.")
            
except Exception as e:
    st.error(f"Hubo un error al leer los archivos de Drive o procesar los datos: {e}")
    with st.expander("Ver detalles técnicos del error"):
        st.code(traceback.format_exc())
