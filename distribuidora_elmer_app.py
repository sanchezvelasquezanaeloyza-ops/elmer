
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Distribuidora Elmer", layout="wide")

st.title("Distribuidora Elmer — Demo (Carga dinámica de meses)")

st.markdown("""
Demo interactiva que permite cargar archivos Excel (ventas, movimientos, sobrefacturación),
ver KPIs, tablas y gráficos. Si no subes archivos, la app intentará usar archivos cargados previamente en el servidor (si existen).
""")

# Helper to read uploaded or local file
def read_excel_maybe(uploaded, local_path=None, sheet_name=0):
    if uploaded is not None:
        try:
            return pd.read_excel(uploaded, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            uploaded.seek(0)
            return pd.read_excel(uploaded, sheet_name=sheet_name)
    else:
        if local_path is None:
            return None
        try:
            return pd.read_excel(local_path, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            try:
                return pd.read_excel(local_path)
            except Exception:
                return None

st.sidebar.header("Cargar archivos o usar los del servidor")
ventas_file = st.sidebar.file_uploader("Archivo VENTAS (.xlsx / .xlsm)", type=["xlsx","xlsm"])
mov_file = st.sidebar.file_uploader("Archivo MOV (movimientos) (.xlsx)", type=["xlsx","xlsm"])
sobre_file = st.sidebar.file_uploader("Archivo SOBREFACTURACIÓN (.xlsm / .xlsx)", type=["xlsx","xlsm"])
use_server_files = st.sidebar.checkbox("Usar archivos del servidor (si existen)", value=True)

# Try loading local server files if checkbox true and no upload
import os
local_ventas = "/mnt/data/2.-VENTAS OCT.xlsm"
local_mov = "/mnt/data/1.- MOV OCT.xlsx"
local_sobre = "/mnt/data/3.- SOBREFACTURACIÓN OCT.xlsm"

ventas_df = None
mov_df = None
sobre_df = None

if ventas_file is not None:
    ventas_df = read_excel_maybe(ventas_file)
elif use_server_files and os.path.exists(local_ventas):
    ventas_df = read_excel_maybe(None, local_ventas)

if mov_file is not None:
    mov_df = read_excel_maybe(mov_file)
elif use_server_files and os.path.exists(local_mov):
    mov_df = read_excel_maybe(None, local_mov)

if sobre_file is not None:
    sobre_df = read_excel_maybe(sobre_file)
elif use_server_files and os.path.exists(local_sobre):
    sobre_df = read_excel_maybe(None, local_sobre)

st.sidebar.markdown("---")
st.sidebar.markdown("**Instrucciones:**\n\n- Sube tus archivos o deja marcada la opción de usar archivos del servidor.\n- La demo acepta archivos .xlsx y .xlsm.\n- Para desplegar en Streamlit Cloud sube este archivo y crea requirements.txt con las dependencias listadas en las instrucciones que se muestran abajo.")


# Simple validation and preview
def preview_df(df, name):
    if df is None:
        st.info(f"No se cargó: {name}")
        return False
    st.markdown(f"#### Vista previa — {name}")
    st.dataframe(df.head(10))
    st.markdown(f"- Columnas: `{', '.join(df.columns.astype(str).tolist())}`")
    return True

col1, col2, col3 = st.columns(3)
with col1:
    ventas_loaded = preview_df(ventas_df, "VENTAS")
with col2:
    mov_loaded = preview_df(mov_df, "MOV")
with col3:
    sobre_loaded = preview_df(sobre_df, "SOBREFACTURACIÓN")

st.markdown("---")

# Basic processing assumptions: try to detect typical columns
def detect_date_column(df):
    if df is None:
        return None
    # common names
    candidates = ["fecha", "date", "FECHA", "Date"]
    cols = df.columns.astype(str).tolist()
    for c in cols:
        if c.lower() in [x.lower() for x in candidates]:
            return c
    # try to find datetime-like
    for c in cols:
        if np.issubdtype(df[c].dtype, np.datetime64):
            return c
    # try to parse first column
    for c in cols:
        try:
            parsed = pd.to_datetime(df[c], errors="coerce")
            if parsed.notna().sum() > 0:
                return c
        except Exception:
            pass
    return None

# Normalize and compute KPIs if possible
if ventas_df is not None:
    ventas = ventas_df.copy()
    date_col = detect_date_column(ventas)
    if date_col:
        ventas[date_col] = pd.to_datetime(ventas[date_col], errors="coerce")
    # try to find amount and quantity columns
    amt_candidates = ["importe", "monto", "amount", "valor", "total", "IMPO", "IMPORTE"]
    qty_candidates = ["cantidad", "qty", "unidades", "cantidad_vendida", "unid"]
    amt_col = None
    qty_col = None
    for c in ventas.columns:
        if any(x.lower() in str(c).lower() for x in amt_candidates):
            amt_col = c
            break
    for c in ventas.columns:
        if any(x.lower() in str(c).lower() for x in qty_candidates):
            qty_col = c
            break

    st.markdown("## KPIs — Ventas")
    k1, k2, k3, k4 = st.columns(4)
    total_sales = ventas[amt_col].sum() if amt_col is not None else None
    total_qty = ventas[qty_col].sum() if qty_col is not None else None
    unique_clients = ventas[ventas.columns[0]].nunique() if ventas.shape[1] > 0 else None

    k1.metric("Ventas totales", f"{total_sales:,.2f}" if total_sales is not None else "N/D")
    k2.metric("Unidades vendidas", f"{total_qty:,.0f}" if total_qty is not None else "N/D")
    k3.metric("Registros", f"{len(ventas):,}")
    k4.metric("Clientes únicos (ejemplo)", f"{unique_clients:,}" if unique_clients is not None else "N/D")

    st.markdown("### Gráfico: Ventas por fecha (si hay columna fecha)")
    if date_col:
        df_time = ventas[[date_col, amt_col]] if amt_col is not None else ventas[[date_col]]
        df_time = df_time.dropna(subset=[date_col]).groupby(pd.Grouper(key=date_col, freq="D")).sum().reset_index()
        fig = px.line(df_time, x=date_col, y=amt_col if amt_col is not None else df_time.columns[1], title="Ventas diarias")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No se detectó columna de fecha para Ventas.")

    st.markdown("### Tabla filtrable — Ventas")
    with st.expander("Mostrar tabla completa de Ventas"):
        st.dataframe(ventas)

if mov_df is not None:
    mov = mov_df.copy()
    st.markdown("## Movimientos / Stock")
    preview_df(mov, "MOV")
    # try to show a pivot if possible
    st.markdown("### Pivot: stock por producto y almacén (si existen columnas)")
    prod_col = None
    store_col = None
    qty_col_mov = None
    for c in mov.columns:
        if any(x in str(c).lower() for x in ["producto", "prod", "item"]):
            prod_col = c
        if any(x in str(c).lower() for x in ["almacen", "almác", "bodega", "store", "warehouse"]):
            store_col = c
        if any(x in str(c).lower() for x in ["cantidad", "qty", "stock", "existencia"]):
            qty_col_mov = c
    if prod_col is not None and qty_col_mov is not None:
        pivot = mov.groupby([prod_col, store_col] if store_col is not None else [prod_col])[qty_col_mov].sum().reset_index()
        st.dataframe(pivot.head(200))
    else:
        st.info("No se detectaron columnas claras para pivote de stock en MOV.")

if sobre_df is not None:
    sobre = sobre_df.copy()
    st.markdown("## Sobrefacturación — Análisis básico")
    preview_df(sobre, "SOBREFACTURACIÓN")
    # Attempt simple comparison with ventas if columns align
    if ventas_df is not None:
        st.markdown("### Comparación entre Ventas y Sobrefacturación (si hay columnas compatibles)")
        common_cols = set(ventas_df.columns).intersection(set(sobre_df.columns))
        if len(common_cols) > 0:
            st.write("Columnas comunes detectadas:", list(common_cols)[:10])
        else:
            st.info("No se detectaron columnas comunes automáticamente. Puedes revisar manualmente las tablas.")

st.markdown("---")
st.markdown("### Exportar datos filtrados")
st.markdown("Puedes descargar la tabla de ventas mostrada como archivo Excel:")

def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ventas")
    return output.getvalue()

if ventas_df is not None:
    st.download_button("Descargar Ventas (Excel)", data=to_excel_bytes(ventas_df), file_name="ventas_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("### Notas de despliegue")
st.markdown("""
- Para desplegar en **Streamlit Cloud** sube este archivo (`distribuidora_elmer_app.py`) a un repositorio GitHub público y crea un archivo `requirements.txt` con las dependencias:
```
streamlit
pandas
openpyxl
plotly
```
- Luego en https://share.streamlit.io conecta tu repositorio y despliega.  
- Si necesitas, te doy el `requirements.txt` y el `Procfile` opcional.
""")
