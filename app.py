from datetime import timedelta

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

# Atajos de período: "hoy" es la última fecha del dataset (no la fecha real), y se cuenta hacia atrás desde ahí.
ATAJOS = {"Última semana": 7, "Último mes": 30, "Último trimestre": 90, "Último año": 365}

def periodo_atajo(dias):
    inicio = fmin if dias is None else max(fmax - timedelta(days=dias - 1), fmin)
    return (inicio, fmax)

def fijar_periodo(dias):
    # Se ejecuta ANTES de que corra el script: por eso puede cambiar el valor del date_input
    st.session_state["rango"] = periodo_atajo(dias)

if "rango" not in st.session_state:
    st.session_state["rango"] = (fmin, fmax)   # valor inicial (por eso el date_input no lleva value=)

rango = st.sidebar.date_input("Período", min_value=fmin, max_value=fmax, key="rango")

# Botones debajo del filtro (el que coincide con el período actual se muestra resaltado)
cols = st.sidebar.columns(2)
for i, (texto, dias) in enumerate(list(ATAJOS.items()) + [("Todo el período", None)]):
    activo = tuple(rango) == periodo_atajo(dias)
    cols[i % 2].button(texto, key=f"atajo_{i}", on_click=fijar_periodo, args=(dias,),
                       type="primary" if activo else "secondary", width="stretch")

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

# Mismos filtros pero sobre la tabla a nivel PEDIDO (una fila por pedido): para pendientes y envíos fuera de plazo
ped_sel = pedidos[(pedidos["FechaPedido"].dt.date >= rango[0]) & (pedidos["FechaPedido"].dt.date <= rango[1])]
if transportistas:
    ped_sel = ped_sel[ped_sel["Transportista"].isin(transportistas)]
if emp_sel:
    ped_sel = ped_sel[ped_sel["Empleado"].isin(emp_sel)]



BASE = "#31688E"     # azul de viridis: color por defecto de las marcas
ACENTO = "#35B779"   # verde de viridis: lo seleccionado / lo que se quiere resaltar
GRIS = "#BDBDBD"     # líneas auxiliares
ROJO = "#D62728"     # alerta: empleados por debajo del 70% del promedio / envíos fuera de plazo
AMARILLO = "#E5A000" # advertencia: pedidos pendientes (ámbar oscuro, el amarillo puro no se lee sobre blanco)


# --- ENCABEZADO---
st.title("Gestión comercial")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Clientes", f"{df_sel['IdCliente'].nunique():,}",
          help="Clientes distintos que hicieron al menos un pedido en el período.")
k2.metric("Valor vendido", f"${df_sel['Valor'].sum():,.0f}")
k3.metric("Pedidos", f"{df_sel['IdPedido'].nunique():,}")   # nunique: la fila es una línea de pedido
k4.metric("Valor promedio por pedido", f"${df_sel['Valor'].sum() / max(df_sel['IdPedido'].nunique(), 1):,.0f}")

# Pedidos pendientes: sin fecha de envío. Fuera de plazo: enviados después de FechaEntrega (la fecha prometida).
pendientes = int(ped_sel["FechaEnvio"].isna().sum())
enviados = int(ped_sel["FechaEnvio"].notna().sum())
fuera_plazo = int((ped_sel["FechaEnvio"] > ped_sel["FechaEntrega"]).sum())   # NaT (pendientes) da False
# Cada tarjeta va en un contenedor con "key": Streamlit le agrega la clase CSS st-key-<key>,
# y con eso se le cambia el color al número (st.metric no tiene un parámetro de color).
with k5.container(key="kpi_pendientes"):
    st.metric("Pedidos pendientes de envío", f"{pendientes:,}",
              help="Pedidos del período que todavía no tienen fecha de envío.")
with k6.container(key="kpi_fuera"):
    st.metric("Enviados fuera de plazo", f"{fuera_plazo:,}",
              delta=f"{fuera_plazo / enviados:.1%} de los enviados" if enviados else None,
              delta_color="off", delta_arrow="off",
              help="Pedidos enviados después de la fecha de entrega prometida.")

# Color solo si el valor es mayor a 0 (con 0 queda el color normal)
css = ""
if pendientes > 0:
    css += f'.st-key-kpi_pendientes [data-testid="stMetricValue"], .st-key-kpi_pendientes [data-testid="stMetricValue"] * {{ color: {AMARILLO}; }}'
if fuera_plazo > 0:
    css += f'.st-key-kpi_fuera [data-testid="stMetricValue"], .st-key-kpi_fuera [data-testid="stMetricValue"] * {{ color: {ROJO}; }}'
if css:
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Panorama", "Detalle de pedidos"])

texto_medida = "Valor vendido" if medida == "Valor" else "Cantidad de pedidos"

with tab1:

    # --- GRÁFICO1: Evolución del valor vendido o de pedidos, según la medida (la granularidad se adapta al período elegido) ---
    dias = (rango[1] - rango[0]).days + 1
    if dias <= 21:
        pfreq, nombre, fmt_eje = "D", "día", "%d/%m"
    elif dias <= 150:
        pfreq, nombre, fmt_eje = "W-SUN", "semana", "%d/%m/%y"    # semanas de lunes a domingo
    else:
        pfreq, nombre, fmt_eje = "M", "mes", "%m/%Y"

    titulo_evol = "valor vendido" if medida == "Valor" else "pedidos"
    st.subheader(f"Evolución de {titulo_evol} por {nombre}")

    # Todos los períodos del rango, incluso los sin ventas (valen 0, no "faltan")
    periodos = pd.period_range(pd.Timestamp(rango[0]), pd.Timestamp(rango[1]), freq=pfreq)
    por_periodo = df_sel.groupby(df_sel["FechaPedido"].dt.to_period(pfreq))
    serie = (por_periodo["Valor"].sum() if medida == "Valor"
             else por_periodo["IdPedido"].nunique())        # pedidos: se cuentan pedidos distintos, no líneas
    serie = serie.reindex(periodos, fill_value=0)
    evol = pd.DataFrame({"Inicio": periodos.start_time, medida: serie.values})
    etiqueta = {"D": "", "W-SUN": "Semana del ", "M": ""}[pfreq]
    evol["Etiqueta"] = etiqueta + evol["Inicio"].dt.strftime("%m/%Y" if pfreq == "M" else "%d/%m/%Y")

    hover_medida = "Valor vendido: $%{y:,.0f}" if medida == "Valor" else "Pedidos: %{y:,.0f}"
    fig = px.line(evol, x="Inicio", y=medida, markers=True, custom_data=["Etiqueta"])
    fig.update_traces(line_color=BASE, hovertemplate="%{customdata[0]}<br>" + hover_medida + "<extra></extra>")
    fig.update_layout(template="plotly_white", height=300, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None)
    fig.update_xaxes(tickformat=fmt_eje)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")

    # Si el período corta la primera/última semana o mes, esos puntos quedan incompletos
    if pfreq != "D" and (periodos[0].start_time.date() < rango[0] or periodos[-1].end_time.date() > rango[1]):
        st.caption(f"*Ojo: los puntos de los extremos pueden estar incompletos (agrupación por {nombre}: el período seleccionado los corta).*")



    izq, der = st.columns([3, 2])

    # --- GRÁFICO2: Podio empleados---
    with izq:
        st.subheader(f"{texto_medida} por empleado")
        st.caption("*Click en el círculo de un empleado para filtrar el resto del tablero (click de nuevo para sacarlo, se pueden elegir varios).*")
        rank = (df.groupby("Empleado", as_index=False)
                  .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"))
                  .sort_values(medida))        
        colores = [ACENTO if e in emp_sel else BASE for e in rank["Empleado"]]

        fig = px.scatter(rank, x=medida, y="Empleado", error_x_minus=rank[medida])  # la "barra fina" del lollipop
        fig.update_traces(marker=dict(size=14, color=colores),
                          error_x=dict(thickness=2, width=0, color=GRIS))

        umbral = rank[medida].mean() * 0.7
        fig.add_vline(x=umbral, line_dash="dash", line_color=ROJO, opacity=0.6,
                      annotation_text="70% del Promedio", annotation_position="top right")

        # Nombres en rojo (y en negrita) para los empleados por debajo del umbral.
        # Plotly no colorea etiquetas por separado, pero acepta HTML simple en ticktext.
        ticktext = [f'<span style="color:{ROJO}"><b>{e}</b></span>' if v < umbral else e
                    for e, v in zip(rank["Empleado"], rank[medida])]
        fig.update_yaxes(tickmode="array", tickvals=rank["Empleado"], ticktext=ticktext)
        
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
        if emp_sel and st.button("Limpiar selección"):
            st.session_state["emp_sel"] = []
            st.rerun()


    # --- GRÁFICO3: Productos con mayores ingresos --- (se podría hacer margen bruto para ver rentabilidad) pero el top es el mismo porque todos los productos tienen el mismo margen}
    with der:
            st.subheader("Top 10 productos por ingresos generados")
            top = (df_sel.groupby("Producto", as_index=False)["Valor"].sum()
                         .nlargest(10, "Valor").sort_values("Valor"))
            fig = px.bar(top, x="Valor", y="Producto", orientation="h", text_auto=",.0f")
            fig.update_traces(marker_color=BASE)
            fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=0, t=10, b=0),
                              yaxis_title=None)
            st.plotly_chart(fig, width="stretch")

    # --- GRÁFICO4: Mapa de clientes (izquierda) y GRÁFICO5: Top clientes por % de ingresos (derecha) ---
    mapa, top_cli = st.columns([3, 2])

    with mapa:
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

    with top_cli:
        TOP_CLIENTES = 10
        st.subheader(f"Top {TOP_CLIENTES} clientes por % de ingresos")
        st.caption("*Porcentaje del valor vendido total (según los filtros activos) que aporta cada cliente.*")
        total_valor = df_sel["Valor"].sum()
        if total_valor > 0:
            clientes = (df_sel.groupby(["IdCliente", "Cliente"], as_index=False)
                              .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique")))
            clientes["Participacion"] = clientes["Valor"] / total_valor
            top_c = clientes.nlargest(TOP_CLIENTES, "Participacion").sort_values("Participacion")   # ascendente: el mayor queda arriba
            top_c["Texto"] = top_c["Participacion"].map(lambda x: f"{x:.1%}")

            fig = px.bar(top_c, x="Participacion", y="Cliente", orientation="h", text="Texto",
                         custom_data=["Valor", "Pedidos"])
            fig.update_traces(marker_color=BASE, textposition="outside", cliponaxis=False,
                              hovertemplate="%{y}<br>%{x:.1%} del total<br>Valor: $%{customdata[0]:,.0f}"
                                            "<br>Pedidos: %{customdata[1]}<extra></extra>")
            fig.update_layout(template="plotly_white", height=420, margin=dict(l=0, r=30, t=10, b=0),
                              yaxis_title=None, xaxis_title=None)
            fig.update_xaxes(tickformat=".0%", rangemode="tozero")
            st.plotly_chart(fig, width="stretch")
            sujeto = f"Estos {len(top_c)} clientes suman" if len(top_c) > 1 else "Este cliente suma"
            st.caption(f"*{sujeto} el {top_c['Participacion'].sum():.0%} del valor vendido.*")
        else:
            st.info("No hay ventas con los filtros seleccionados.")
