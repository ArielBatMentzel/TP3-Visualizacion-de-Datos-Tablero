import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestión comercial", layout="wide")

@st.cache_data  # se lee una sola vez, no en cada interacción
def cargar():
    lineas = pd.read_csv("data/processed/lineas.csv", parse_dates=["FechaPedido"])
    pedidos = pd.read_csv("data/processed/pedidos.csv", parse_dates=["FechaPedido", "FechaEntrega", "FechaEnvio"])
    lineas["Mes"] = lineas["FechaPedido"].dt.to_period("M").dt.to_timestamp()
    return lineas, pedidos

lineas, pedidos = cargar()


# --- FILTROS ---
st.sidebar.header("Filtros")

fmin, fmax = lineas["FechaPedido"].min().date(), lineas["FechaPedido"].max().date()
rango = st.sidebar.date_input("Período", value=(fmin, fmax), min_value=fmin, max_value=fmax)
if len(rango) != 2:   # mientras el usuario todavía no eligió la segunda fecha
    st.stop()

transportistas = st.sidebar.multiselect("Transportista", sorted(lineas["Transportista"].unique()))
medida = st.sidebar.radio("Medida", ["Valor", "Pedidos"], horizontal=True)

df = lineas[(lineas["FechaPedido"].dt.date >= rango[0]) & (lineas["FechaPedido"].dt.date <= rango[1])] # Ver si hacen falta los dt.date
if transportistas:                       # lista vacía = sin filtro
    df = df[df["Transportista"].isin(transportistas)]

# Empleados clickeados en el ranking (se usan para filtrar los OTROS gráficos)
emp_sel = st.session_state.get("emp_sel", [])   # empleados seleccionados
df_sel = df[df["Empleado"].isin(emp_sel)] if emp_sel else df



# --- ENCABEZADO---
st.title("Gestión comercial")
k1, k2, k3 = st.columns(3)
k1.metric("Valor vendido", f"${df_sel['Valor'].sum():,.0f}")
k2.metric("Pedidos", f"{df_sel['IdPedido'].nunique():,}")   # nunique: la fila es una línea de pedido
k3.metric("Valor promedio por pedido", f"${df_sel['Valor'].sum() / max(df_sel['IdPedido'].nunique(), 1):,.0f}")

tab1, tab2 = st.tabs(["Panorama", "Detalle de pedidos"])

BASE = "#31688E"     # azul de viridis: color por defecto de las marcas
ACENTO = "#35B779"   # verde de viridis: lo seleccionado / lo que se quiere resaltar
GRIS = "#BDBDBD"     # líneas auxiliares


texto_medida = "Valor vendido" if medida == "Valor" else "Cantidad de pedidos"

with tab1:
    izq, der = st.columns([3, 2])

    # --- GRÁFICO1: Podio empleados---
    with izq:
        st.subheader(f"{texto_medida} por empleado")
        rank = (df.groupby("Empleado", as_index=False)
                  .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"))
                  .sort_values(medida))        
        colores = [ACENTO if e in emp_sel else BASE for e in rank["Empleado"]]

        fig = px.scatter(rank, x=medida, y="Empleado", error_x_minus=rank[medida])  # la "barra fina" del lollipop
        fig.update_traces(marker=dict(size=14, color=colores),
                          error_x=dict(thickness=2, width=0, color=GRIS))

        promedio_mitad = rank[medida].mean() * 0.7
        fig.add_vline(x=promedio_mitad, line_dash="dash", line_color="red", opacity=0.4, 
                      annotation_text="70% del Promedio", annotation_position="top right")
        
        fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=0, t=10, b=0),
                          yaxis_title=None, xaxis_title=medida)
        fig.update_xaxes(rangemode="tozero")
        # La key cambia después de cada click (v), así el gráfico arranca "limpio" cada vez
        # y cada click llega como un evento nuevo: la selección real la guardamos nosotros en emp_sel.
        v = st.session_state.get("v", 0)
        evento = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key=f"ranking_{v}", width="stretch")
        clickeados = [p["y"] for p in evento["selection"]["points"]]
        if clickeados:
            st.session_state["emp_sel"] = sorted(set(emp_sel) ^ set(clickeados))  # ^ = agrega si no estaba, saca si estaba
            st.session_state["v"] = v + 1
            st.rerun()
        st.caption("*Click en el círculo de un empleado para filtrar el resto del tablero (click de nuevo para sacarlo, se pueden elegir varios).*")
        if emp_sel and st.button("Limpiar selección"):
            st.session_state["emp_sel"] = []
            st.rerun()


    # --- GRÁFICO2: Productos con mayores ingresos --- (se podría hacer margen bruto para ver rentabilidad) pero el top es el mismo porque todos los productos tienen el mismo margen}
    with der:
            st.subheader("Top 10 productos por ingresos generados")
            top = (df_sel.groupby("Producto", as_index=False)["Valor"].sum()
                         .nlargest(10, "Valor").sort_values("Valor"))
            fig = px.bar(top, x="Valor", y="Producto", orientation="h", text_auto=",.0f")
            fig.update_traces(marker_color=BASE)
            fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=0, t=10, b=0),
                              yaxis_title=None)
            st.plotly_chart(fig, width="stretch")

    # --- GRÁFICO3: Evolución mensual del valor vendido --- 
    st.subheader("Evolución mensual del valor vendido")
    mensual = df_sel.groupby("Mes", as_index=False)["Valor"].sum()
    fig = px.line(mensual, x="Mes", y="Valor", markers=True)
    fig.update_traces(line_color=BASE)
    fig.update_layout(template="plotly_white", height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")


    # --- GRÁFICO4: Mapa de clientes: importancia y recurrencia --- 
    st.subheader("Clientes por ciudad")
    st.caption("*Tamaño del círculo: cantidad de pedidos; Color: valor vendido.*")
    
    geo = (df_sel.groupby(["CiudadCliente", "LatitudCiudadCliente", "LongitudCiudadCliente"], as_index=False)
           .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique")))

    fig = px.scatter_geo(geo, lat="LatitudCiudadCliente", lon="LongitudCiudadCliente", size="Pedidos", color="Valor",
                         color_continuous_scale="Viridis",      # continua. Probá "Cividis", "Plasma", "Viridis_r"
                         hover_name="CiudadCliente", hover_data={"LatitudCiudadCliente": False, "LongitudCiudadCliente": False, "Valor": ":,.0f"},
                         projection="natural earth", size_max=30)
    fig.update_geos(showcountries=True, countrycolor="#DDDDDD", fitbounds="locations")
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")



# Corregir el gráfico de la evolución mensual (que sea por semanas sino o ver como se puede cambiar)

