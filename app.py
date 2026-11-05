from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# paleta.py tiene que estar en la misma carpeta que este archivo
from paleta import ACENTO, AMARILLO, AMARILLO_TEXTO, BASE, GRIS, ROJO, RUMBO_CONTINUA

st.set_page_config(page_title="Gestión comercial", layout="wide")


@st.cache_data  # se lee una sola vez, no en cada interacción
def cargar():
    lineas = pd.read_csv("data/processed/lineas.csv", parse_dates=["FechaPedido"])
    pedidos = pd.read_csv("data/processed/pedidos.csv", parse_dates=["FechaPedido", "FechaEntrega", "FechaEnvio"])
    return lineas, pedidos


lineas, pedidos = cargar()


# ============================================================ FILTROS (barra lateral)
st.sidebar.header("Filtros")

fmin, fmax = lineas["FechaPedido"].min().date(), lineas["FechaPedido"].max().date()

# Atajos de período: "hoy" es la última fecha del dataset (no la fecha real), y se cuenta hacia atrás desde ahí.
ATAJOS = {"Última semana": 7, "Último mes": 30, "Último trimestre": 90, "Último año": 365}


def periodo_atajo(n_dias):
    inicio = fmin if n_dias is None else max(fmax - timedelta(days=n_dias - 1), fmin)
    return (inicio, fmax)


def fijar_periodo(n_dias):
    # Se ejecuta ANTES de que corra el script: por eso puede cambiar el valor del date_input
    st.session_state["rango"] = periodo_atajo(n_dias)


if "rango" not in st.session_state:
    st.session_state["rango"] = (fmin, fmax)   # valor inicial (por eso el date_input no lleva value=)

rango = st.sidebar.date_input("Período", min_value=fmin, max_value=fmax, key="rango")

# Botones debajo del filtro (el que coincide con el período actual se muestra resaltado)
cols = st.sidebar.columns(2)
for i, (texto, n_dias) in enumerate(list(ATAJOS.items()) + [("Todo el período", None)]):
    activo = tuple(rango) == periodo_atajo(n_dias)
    cols[i % 2].button(texto, key=f"atajo_{i}", on_click=fijar_periodo, args=(n_dias,),
                       type="primary" if activo else "secondary", width="stretch")

if len(rango) != 2:   # mientras el usuario todavía no eligió la segunda fecha
    st.stop()

medida = st.sidebar.radio("Medida (Ventas y equipo)", ["Valor", "Pedidos"], horizontal=True)
texto_medida = "Valor vendido" if medida == "Valor" else "Cantidad de pedidos"

# Empleados clickeados en el ranking (filtran todo el tablero menos el propio ranking)
emp_sel = st.session_state.get("emp_sel", [])


def filtrar(tabla, desde, hasta, con_empleados=True):
    """Filtra una tabla (líneas o pedidos) por fechas, transportista y, opcionalmente, empleados seleccionados."""
    d = tabla[(tabla["FechaPedido"].dt.date >= desde) & (tabla["FechaPedido"].dt.date <= hasta)]
    if con_empleados and emp_sel:
        d = d[d["Empleado"].isin(emp_sel)]
    return d


df = filtrar(lineas, rango[0], rango[1], con_empleados=False)   # para el ranking de empleados
df_sel = filtrar(lineas, rango[0], rango[1])                    # para todo lo demás
ped_sel = filtrar(pedidos, rango[0], rango[1])                  # a nivel pedido (una fila por pedido)

# Período anterior de igual duración, inmediatamente antes del seleccionado
dias = (rango[1] - rango[0]).days + 1
prev_fin = rango[0] - timedelta(days=1)
prev_ini = prev_fin - timedelta(days=dias - 1)
comparable = prev_ini >= fmin          # solo se compara si el período anterior está completo dentro de los datos
df_prev = filtrar(lineas, prev_ini, prev_fin) if comparable else None


# ============================================================ ENCABEZADO
st.title("Gestión comercial")

if emp_sel:
    a, b = st.columns([6, 1])
    a.markdown(f"**Filtro activo — empleados:** {', '.join(emp_sel)}")
    if b.button("Limpiar selección"):
        st.session_state["emp_sel"] = []
        st.rerun()

if df.empty:
    st.warning("No hay ventas en el período y transportista seleccionados.")
    st.stop()


def resumen(d):
    n_pedidos = d["IdPedido"].nunique()      # nunique: la fila es una línea de pedido
    valor = d["Valor"].sum()
    return {"clientes": d["IdCliente"].nunique(), "valor": valor, "pedidos": n_pedidos,
            "promedio": valor / n_pedidos if n_pedidos else 0}


actual = resumen(df_sel)
anterior = resumen(df_prev) if comparable else None


def variacion(clave):
    """Variación % contra el período anterior (None si no hay con qué comparar)."""
    if anterior is None or not anterior[clave]:
        return None
    return f"{(actual[clave] - anterior[clave]) / anterior[clave]:+.1%}"


k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Clientes", f"{actual['clientes']:,}", delta=variacion("clientes"),
          help="Clientes distintos que hicieron al menos un pedido en el período.")
k2.metric("Valor vendido", f"${actual['valor']:,.0f}", delta=variacion("valor"),
          help="Suma de Cantidad × PrecioUnidad de todas las líneas de pedido del período.")
k3.metric("Pedidos", f"{actual['pedidos']:,}", delta=variacion("pedidos"),
          help="Pedidos distintos realizados en el período.")
k4.metric("Valor promedio por pedido", f"${actual['promedio']:,.0f}", delta=variacion("promedio"),
          help="Valor vendido dividido por la cantidad de pedidos.")

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

if comparable:
    st.caption(f"*Período anterior de igual duración ({prev_ini:%d/%m/%Y} a {prev_fin:%d/%m/%Y}).*")
else:
    st.caption("*El período anterior queda fuera del rango de datos*")

if df_sel.empty:
    st.info("No hay ventas con la selección de empleados actual. Probá limpiar la selección.")
    st.stop()

tab1, tab2 = st.tabs(["Ventas y equipo", "Productos, clientes y ciudades"])

# ============================================================ VISTA 1: VENTAS Y EQUIPO
with tab1:

    # ---------------------------------------------------------------------------
    # PREGUNTA 1 — ¿Cómo evolucionan el valor vendido y los pedidos? ¿Viene por encima o por debajo del período anterior?
    # La granularidad (día / semana / mes) se adapta a la duración del período elegido.
    # ---------------------------------------------------------------------------
    if dias <= 21:
        pfreq, nombre, fmt_eje = "D", "día", "%d/%m"
    elif dias <= 150:
        pfreq, nombre, fmt_eje = "W-SUN", "semana", "%d/%m/%y"    # semanas de lunes a domingo
    else:
        pfreq, nombre, fmt_eje = "M", "mes", "%m/%Y"

    titulo_evol = "valor vendido" if medida == "Valor" else "pedidos"
    st.subheader(f"Evolución de {titulo_evol} por {nombre}")

    def evolucion(d, desde, hasta):
        """Serie por día/semana/mes con TODOS los períodos del rango (los sin ventas valen 0, no 'faltan')."""
        periodos = pd.period_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq=pfreq)
        por_periodo = d.groupby(d["FechaPedido"].dt.to_period(pfreq))
        serie = (por_periodo["Valor"].sum() if medida == "Valor"
                 else por_periodo["IdPedido"].nunique())      # pedidos: pedidos distintos, no líneas
        serie = serie.reindex(periodos, fill_value=0)
        evol = pd.DataFrame({"Inicio": periodos.start_time, medida: serie.values})
        prefijo = "Semana del " if pfreq == "W-SUN" else ""
        evol["Etiqueta"] = prefijo + evol["Inicio"].dt.strftime("%m/%Y" if pfreq == "M" else "%d/%m/%Y")
        return periodos, evol

    periodos, evol = evolucion(df_sel, rango[0], rango[1])
    hover_medida = "Valor vendido: $%{y:,.0f}" if medida == "Valor" else "Pedidos: %{y:,.0f}"

    fig = px.line(evol, x="Inicio", y=medida, markers=True, custom_data=["Etiqueta"])
    fig.update_traces(name="Período seleccionado", showlegend=comparable, line_color=BASE, marker_color=BASE,
                      hovertemplate="%{customdata[0]}<br>" + hover_medida + "<extra></extra>")
    if comparable:
        # Período anterior desplazado hacia adelante para superponerlo con el actual
        _, evol_prev = evolucion(df_prev, prev_ini, prev_fin)
        fig.add_scatter(x=evol_prev["Inicio"] + pd.Timedelta(days=dias), y=evol_prev[medida], mode="lines",
                        name="Período anterior", line=dict(color=GRIS, dash="dash", width=2),
                        customdata=evol_prev[["Etiqueta"]],
                        hovertemplate="Anterior: %{customdata[0]}<br>" + hover_medida + "<extra></extra>")
    fig.update_layout(template="plotly_white", height=320, margin=dict(l=0, r=0, t=10, b=0), xaxis_title=None,
                      legend=dict(orientation="h", y=1.12, x=0, title_text=""))
    fig.update_xaxes(tickformat=fmt_eje)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")

    # Si el período corta la primera/última semana o mes, esos puntos quedan incompletos
    if pfreq != "D" and (periodos[0].start_time.date() < rango[0] or periodos[-1].end_time.date() > rango[1]):
        st.caption(f"*Ojo: los puntos de los extremos pueden estar incompletos (agrupación por {nombre}: el período seleccionado los corta).*")

    # ---------------------------------------------------------------------------
    # PREGUNTA 2 — ¿Qué empleados rinden más y quiénes están por debajo del objetivo (70% del promedio)?
    # ---------------------------------------------------------------------------
    st.subheader(f"{texto_medida} por empleado")
    st.caption("*Amarillo: por debajo del 70% del promedio del equipo (posible necesidad de apoyo). "
               "Click en un empleado para filtrar el resto del tablero; click de nuevo para sacarlo; se pueden elegir varios.*")

    rank = (df.groupby("Empleado", as_index=False)
              .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"))
              .sort_values(medida))
    rank["ValorPorPedido"] = rank["Valor"] / rank["Pedidos"]
    promedio = rank[medida].mean()
    umbral = promedio * 0.7
    rank["PctPromedio"] = rank[medida] / promedio
    abajo = rank[medida] < umbral

    colores = [ACENTO if e in emp_sel else (AMARILLO if a_ else BASE) for e, a_ in zip(rank["Empleado"], abajo)]

    fig = px.scatter(rank, x=medida, y="Empleado", error_x_minus=rank[medida],   # la "barra fina" del lollipop
                     custom_data=["Valor", "Pedidos", "ValorPorPedido", "PctPromedio"])
    fig.update_traces(marker=dict(size=14, color=colores),
                      error_x=dict(thickness=2, width=0, color=GRIS),
                      hovertemplate="<b>%{y}</b><br>Valor: $%{customdata[0]:,.0f}<br>Pedidos: %{customdata[1]}"
                                    "<br>Valor por pedido: $%{customdata[2]:,.0f}"
                                    f"<br>% del promedio ({medida.lower()}): " + "%{customdata[3]:.0%}<extra></extra>")
    fig.add_vline(x=promedio, line_dash="dot", line_color=GRIS,
                  annotation_text="Promedio", annotation_position="top right", annotation_font=dict(color="#6B7280", size=11))
    fig.add_vline(x=umbral, line_dash="dash", line_color=AMARILLO,
                  annotation_text="70% del promedio", annotation_position="top left",
                  annotation_font=dict(color=AMARILLO_TEXTO, size=11))

    # Nombres en ocre y negrita para los empleados por debajo del umbral.
    # Plotly no colorea etiquetas por separado, pero acepta HTML simple en ticktext.
    ticktext = [f'<span style="color:{AMARILLO_TEXTO}"><b>{e}</b></span>' if a_ else e
                for e, a_ in zip(rank["Empleado"], abajo)]
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


# ============================================================ VISTA 2: PRODUCTOS, CLIENTES Y CIUDADES
with tab2:

    # ---------------------------------------------------------------------------
    # PREGUNTA 4 — ¿Qué productos tuvieron mayores ingresos y cuáles se vendieron en mayor cantidad?
    # ---------------------------------------------------------------------------
    prod = (df_sel.groupby("Producto", as_index=False)
                  .agg(Valor=("Valor", "sum"), Unidades=("Cantidad", "sum")))
    top_valor = prod.nlargest(10, "Valor").sort_values("Valor")
    top_unid = prod.nlargest(10, "Unidades").sort_values("Unidades")
    en_ambos = set(top_valor["Producto"]) & set(top_unid["Producto"])


    def barras_top(d, col, plantilla):
        d = d.copy()
        fig = px.bar(d, x=col, y="Producto", orientation="h")
        fig.update_traces(marker_color=[ACENTO if p in en_ambos else BASE for p in d["Producto"]],
                          texttemplate=plantilla, textposition="outside", cliponaxis=False, hovertemplate=None, hoverinfo="none")
        fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=40, t=10, b=0),
                          yaxis_title=None, xaxis_title=None)
        return fig


    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Top 10 productos por ingresos")
        st.plotly_chart(barras_top(top_valor, "Valor", "$%{x:,.0f}"), width="stretch")
    with col_b:
        st.subheader("Top 10 productos por unidades vendidas")
        st.plotly_chart(barras_top(top_unid, "Unidades", "%{x:,.0f}"), width="stretch")
    st.caption(f"*Verde: productos que están en los dos rankings ({len(en_ambos)} de 10).*")

    # ---------------------------------------------------------------------------
    # PREGUNTA 3 — ¿Cómo se concentran valor y pedidos por ciudad? ¿Qué clientes son los más importantes?
    # ---------------------------------------------------------------------------
    mapa, top_cli = st.columns([3, 2])

    with mapa:
        st.subheader("Valor y pedidos por ciudad")
        st.caption("*Tamaño del círculo: cantidad de pedidos. Color: valor vendido (más oscuro = más valor). "
                   "Se rotulan las 5 ciudades con más valor.*")
        geo = (df_sel.groupby(["CiudadCliente", "LatitudCiudadCliente", "LongitudCiudadCliente"], as_index=False)
                     .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"), Clientes=("IdCliente", "nunique")))
        top_ciudades = set(geo.nlargest(5, "Valor")["CiudadCliente"])
        geo["Etiqueta"] = geo["CiudadCliente"].where(geo["CiudadCliente"].isin(top_ciudades), "")

        fig = px.scatter_geo(geo, lat="LatitudCiudadCliente", lon="LongitudCiudadCliente", size="Pedidos", color="Valor",
                             color_continuous_scale=RUMBO_CONTINUA, text="Etiqueta",
                             custom_data=["CiudadCliente", "Valor", "Pedidos", "Clientes"],
                             projection="natural earth", size_max=30)
        fig.update_traces(textposition="top center", textfont=dict(size=11, color="#374151"),
                          marker=dict(line=dict(width=0.8, color="#5B6770")),   # borde: los círculos claros se ven sobre el fondo
                          hovertemplate="<b>%{customdata[0]}</b><br>Valor: $%{customdata[1]:,.0f}"
                                        "<br>Pedidos: %{customdata[2]}<br>Clientes: %{customdata[3]}<extra></extra>")
        fig.update_geos(showcountries=True, countrycolor="#D1D5DB", showland=True, landcolor="#F3F4F6", fitbounds="locations")
        fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0), coloraxis_colorbar=dict(title="Valor ($)"))
        st.plotly_chart(fig, width="stretch")

    with top_cli:
        TOP_CLIENTES = 10
        st.subheader(f"Top {TOP_CLIENTES} clientes por % de ingresos")
        st.caption("*Porcentaje del valor vendido total (según los filtros activos) que aporta cada cliente.*")
        total_valor = df_sel["Valor"].sum()
        clientes = (df_sel.groupby(["IdCliente", "Cliente", "CiudadCliente"], as_index=False)
                          .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique")))
        clientes["Participacion"] = clientes["Valor"] / total_valor
        top_c = clientes.nlargest(TOP_CLIENTES, "Participacion").sort_values("Participacion")   # ascendente: el mayor queda arriba
        top_c["Texto"] = top_c["Participacion"].map(lambda x: f"{x:.1%}")

        fig = px.bar(top_c, x="Participacion", y="Cliente", orientation="h", text="Texto",
                     custom_data=["Valor", "Pedidos", "CiudadCliente"])
        fig.update_traces(marker_color=BASE, textposition="outside", cliponaxis=False,
                          hovertemplate="Valor: $%{customdata[0]:,.0f}"
                                        "<br>Pedidos: %{customdata[1]}<extra></extra>")
        fig.update_layout(template="plotly_white", height=430, margin=dict(l=0, r=30, t=10, b=0),
                          yaxis_title=None, xaxis_title=None)
        fig.update_xaxes(tickformat=".0%", rangemode="tozero")
        st.plotly_chart(fig, width="stretch")

        # Cuánto depende la empresa de pocos clientes
        acumulado = clientes["Participacion"].sort_values(ascending=False).cumsum()
        n_mitad = int((acumulado < 0.5).sum()) + 1
        sujeto = f"Estos clientes suman" if len(top_c) > 1 else "Este cliente suma"
        st.caption(f"*{sujeto} el {top_c['Participacion'].sum():.0%}. "
                   f"La mitad del valor la generan {n_mitad} de {len(clientes)} clientes.*")

    # Clientes importantes (valor) vs recurrentes (pedidos)
    st.subheader("Clientes: importancia (valor) vs recurrencia (pedidos)")
    st.caption("*Cada punto es un cliente. Las líneas punteadas marcan el promedio. Arriba a la derecha: importantes y recurrentes; "
               "Se rotulan los 5 clientes con más valor.*")
    clientes["Etiqueta"] = clientes["Cliente"].where(clientes["Valor"].rank(ascending=False, method="first") <= 5, "")
    fig = px.scatter(clientes, x="Pedidos", y="Valor", text="Etiqueta", custom_data=["Cliente", "CiudadCliente"])
    fig.update_traces(marker=dict(size=10, color=BASE, opacity=0.85, line=dict(width=0.6, color="white")),
                      textposition="top center", textfont=dict(size=11, color="#374151"),
                      hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Pedidos: %{x}<br>Valor: $%{y:,.0f}<extra></extra>")
    fig.add_vline(x=clientes["Pedidos"].mean(), line_dash="dot", line_color=GRIS)
    fig.add_hline(y=clientes["Valor"].mean(), line_dash="dot", line_color=GRIS)
    fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis_title="Pedidos realizados", yaxis_title="Valor vendido ($)")
    fig.update_xaxes(rangemode="tozero")
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")
