import streamlit as st
import pandas as pd
from fpdf import FPDF
import os

st.set_page_config(page_title="Reporte de Producción y Recepción", page_icon="🏭", layout="wide")
st.title("Reporte de Producción y Recepción de Leche")

# --- IDs DE GOOGLE DRIVE ---
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

# Función para interpretar el lote de producción
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
    
    # 1. Leer Producción
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

    df_prod['Producto'], df_prod['Grupo'] = zip(*df_prod['Lote'].astype(str).apply(procesar_lote))
    df_prod['Año'] = df_prod['Fecha'].dt.year
    df_prod['Mes'] = df_prod['Fecha'].dt.month

    # 2. Leer Recibo de Leche (Asumimos estructura estándar de la planilla de recibo)
    # Ajustá los índices de columnas según la solapa de tu resumen de recibo
    raw_recibo = pd.read_excel(URL_RECIBO) 
    df_recibo = pd.DataFrame()
    # Ejemplo genérico: Columna 0 Fecha de recibo, Columna 2 o similar Litros Ingresados
    # (Podemos adaptarlo exactamente según cómo esté armado tu excel de recibo)
    df_recibo['Fecha'] = pd.to_datetime(raw_recibo.iloc[:, 0], dayfirst=True, errors='coerce')
    df_recibo['Litros Ingresados'] = pd.to_numeric(raw_recibo.iloc[:, 1], errors='coerce').fillna(0) # Ajustar índice según tu excel
    df_recibo = df_recibo.dropna(subset=['Fecha'])
    df_recibo['Año'] = df_recibo['Fecha'].dt.year
    df_recibo['Mes'] = df_recibo['Fecha'].dt.month
    
    # Agrupar recibo por mes y año
    recibo_mensual = df_recibo.groupby(['Año', 'Mes'])['Litros Ingresados'].sum().reset_index()

    # Filtros laterales
    st.sidebar.header("Filtros de Búsqueda")
    opciones_anio = ["Todos"] + sorted(df_prod['Año'].unique().tolist())
    opciones_mes = ["Todos"] + sorted(df_prod['Mes'].unique().tolist())
    opciones_grupo = ["Todos", "Coopagro", "Mastellone"]

    filtro_anio = st.sidebar.selectbox("Seleccionar Año", opciones_anio)
    filtro_mes = st.sidebar.selectbox("Seleccionar Mes", opciones_mes)
    filtro_grupo = st.sidebar.selectbox("Seleccionar Grupo", opciones_grupo)

    df_filtrado = df_prod.copy()
    if filtro_anio != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Mes'] == filtro_mes]
    if filtro_grupo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo]

    # Totales globales de producción
    total_litros_proc = df_filtrado['Litros Procesados'].sum()
    total_prod = df_filtrado['Producto Terminado'].sum()
    total_pnc = df_filtrado['PNC'].sum()
    
    # Filtrar recibo según los mismos criterios de año y mes
    df_recibo_filtrado = recibo_mensual.copy()
    if filtro_anio != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Año'] == filtro_anio]
    if filtro_mes != "Todos":
        df_recibo_filtrado = df_recibo_filtrado[df_recibo_filtrado['Mes'] == filtro_mes]
    
    total_litros_ingresados = df_recibo_filtrado['Litros Ingresados'].sum()

    # Ratios globales
    ratio_conversion = (total_prod / total_litros_proc * 100) if total_litros_proc > 0 else 0
    rendimiento_ingreso = (total_prod / total_litros_ingresados * 100) if total_litros_ingresados > 0 else 0

    # Mostrar métricas en pantalla
    st.subheader("Resumen General de Planta (Producción y Recibo)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Litros Ingresados (Recibo)", fmt2(total_litros_ingresados))
    c2.metric("Litros Procesados", fmt2(total_litros_proc))
    c3.metric("Prod. Terminado", fmt2(total_prod))
    c4.metric("Ratio Proc. vs Term.", f"{ratio_conversion:.2f}%".replace(".", ","))
    c5.metric("Rendimiento Recibo vs Term.", f"{rendimiento_ingreso:.2f}%".replace(".", ","))

    # Detalle de lotes en pantalla
    st.subheader("Detalle de Producción")
    columnas_ordenadas = ['Fecha', 'Lote', 'Producto', 'Litros Procesados', 'Producto Terminado', 'PNC', '% PNC', 'Ratio de Conversión (%)']
    
    df_filtrado['Ratio de Conversión (%)'] = df_filtrado.apply(
        lambda x: f"{(x['Producto Terminado'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
    )
    df_filtrado['% PNC'] = df_filtrado.apply(
        lambda x: f"{(x['PNC'] / x['Litros Procesados'] * 100):.2f}%".replace(".", ",") if x['Litros Procesados'] > 0 else "0,00%", axis=1
    )
    
    df_view = df_filtrado[columnas_ordenadas].copy()
    df_view['Litros Procesados'] = df_view['Litros Procesados'].apply(fmt2)
    df_view['Producto Terminado'] = df_view['Producto Terminado'].apply(fmt2)
    df_view['PNC'] = df_view['PNC'].apply(fmt2)
    df_view['Fecha'] = df_view['Fecha'].dt.strftime('%d/%m/%Y')
    
    st.dataframe(df_view, use_container_width=True)

except Exception as e:
    st.error(f"Hubo un error al procesar las planillas desde Google Drive: {e}")
