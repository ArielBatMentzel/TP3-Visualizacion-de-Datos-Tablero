from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
import plotly.graph_objects as go
import numpy as np

from paleta import ACENTO, AMARILLO, AMARILLO_TEXTO, BASE, GRIS, ROJO, RUMBO_CONTINUA, RUMBO_DISCRETA

st.set_page_config(page_title="Gestión Comercial", layout="wide")


@st.cache_data  # se lee una sola vez, no en cada interacción (porque lo guarda en cache de streamlit)
def cargar():
    lineas = pd.read_csv("data/processed/lineas.csv", parse_dates=["FechaPedido"])
    pedidos = pd.read_csv("data/processed/pedidos.csv", parse_dates=["FechaPedido", "FechaEntrega", "FechaEnvio"])
    return lineas, pedidos


lineas, pedidos = cargar()


# ============================================================ FILTROS (barra lateral)
st.sidebar.header("Filtros")

fmin, fmax = lineas["FechaPedido"].min().date(), lineas["FechaPedido"].max().date()

# Atajos de período 
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

# Empleados clickeados en el ranking (filtran todo el tablero)
emp_sel = st.session_state.get("emp_sel", [])


def filtrar(tabla, desde, hasta, con_empleados=True):
    """Filtra una tabla (líneas o pedidos) por fechas y, opcionalmente, empleados seleccionados."""
    d = tabla[(tabla["FechaPedido"].dt.date >= desde) & (tabla["FechaPedido"].dt.date <= hasta)]
    if con_empleados and emp_sel:
        d = d[d["Empleado"].isin(emp_sel)]
    return d


df = filtrar(lineas, rango[0], rango[1], con_empleados=False)   # para el ranking de empleados
df_sel = filtrar(lineas, rango[0], rango[1])                    # para todo lo demás
ped_sel = filtrar(pedidos, rango[0], rango[1])                  # a nivel pedido

# Período anterior de igual duración, inmediatamente antes del seleccionado
dias = (rango[1] - rango[0]).days + 1
prev_fin = rango[0] - timedelta(days=1)
prev_ini = prev_fin - timedelta(days=dias - 1)
comparable = prev_ini >= fmin          # solo se compara si el período anterior está completo dentro de los datos
df_prev = filtrar(lineas, prev_ini, prev_fin) if comparable else None


# ===== ENCABEZADO
st.title("Gestión Comercial")
# se añade un subtítulo con una breve explicación
st.subheader("Seguimiento de ventas, control de entregas y desempeño comercial.")

if emp_sel:
    a, b = st.columns([6, 1])
    a.markdown(f"**Filtro activo — empleados:** {', '.join(emp_sel)}")
    if b.button("Limpiar selección"):
        st.session_state["emp_sel"] = []
        st.rerun()

if df.empty:
    st.warning("No hay ventas en el período seleccionado.")
    st.stop()


def resumen(d):
    return {"clientes": d["IdCliente"].nunique(), "valor": d["Valor"].sum(),
            "pedidos": d["IdPedido"].nunique()}      # nunique: la fila es una línea de pedido


actual = resumen(df_sel)
anterior = resumen(df_prev) if comparable else None


def variacion(clave):
    """Variación % contra el período anterior (None si no hay con qué comparar)."""
    if anterior is None or not anterior[clave]:
        return None
    return f"{(actual[clave] - anterior[clave]) / anterior[clave]:+.1%}"


grupo_izq, espacio_centro, grupo_der = st.columns([5, 4, 3])

with grupo_izq:
    k1, k2, k3 = st.columns([0.85, 1.5, 1], gap="small")

with grupo_der:
    k4, k5 = st.columns(2)

k1.metric("Clientes", f"{actual['clientes']:,}", delta=variacion("clientes"),
          help="Clientes distintos que hicieron al menos un pedido en el período.")
k2.metric("Valor vendido", f"${actual['valor']:,.0f}", delta=variacion("valor"),
          help="**Total vendido en el período**")
k3.metric("Pedidos", f"{actual['pedidos']:,}", delta=variacion("pedidos"))

# --- PREGUNTA 5 — ¿Cuántos pedidos se enviaron fuera de término y cuántos siguen pendientes de envío?
# Pedidos pendientes: sin fecha de envío. Fuera de plazo: enviados después de FechaEntrega.
# Los pintamos solamente si su valor es distinto de 0
pendientes = int(ped_sel["FechaEnvio"].isna().sum())
enviados = int(ped_sel["FechaEnvio"].notna().sum())
fuera_plazo = int((ped_sel["FechaEnvio"] > ped_sel["FechaEntrega"]).sum()) 

# Cada tarjeta va en un contenedor con "key": Streamlit le agrega la clase CSS st-key-<key>,
# y con eso se le cambia el color al número.
with k4.container(key="kpi_pendientes"):
    st.metric(" ", f"{pendientes:,}",
              help="**Pedidos pendientes de envío**")
with k5.container(key="kpi_fuera"):
    st.metric(" ", f"{fuera_plazo:,}",
              delta=f"{fuera_plazo / enviados:.1%} de los enviados" if enviados else None,
              delta_color="off", delta_arrow="off",
              help="Pedidos enviados fuera de plazo")

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


# ===== VISTA 1: VENTAS Y EQUIPO
with tab1:

    # --- PREGUNTA 1 — ¿Cómo evolucionan el valor vendido y la cantidad de pedidos en el período elegido, y cómo se comparan con el período anterior?
    if dias <= 21:
      pfreq, nombre, fmt_eje = "D", "día", "%d/%m"
    elif dias <= 150:
      pfreq, nombre, fmt_eje = "W-SUN", "semana", "%d/%m/%y"
    else:
      pfreq, nombre, fmt_eje = "M", "mes", "%m/%Y"

    titulo_evol = "valor vendido" if medida == "Valor" else "pedidos"
    st.subheader(f"Evolución de {titulo_evol} por {nombre}")

    def evolucion(d, desde, hasta):
      """Serie por día/semana/mes con todos los períodos del rango.

      Las etiquetas detectan semanas/meses incompletos en los extremos y
      muestran el rango de fechas exacto consumido.
      """
      periodos = pd.period_range(
          pd.Timestamp(desde), pd.Timestamp(hasta), freq=pfreq
      )
      por_periodo = d.groupby(d["FechaPedido"].dt.to_period(pfreq))
      serie = (
          por_periodo["Valor"].sum()
          if medida == "Valor"
          else por_periodo["IdPedido"].nunique()
      )
      serie = serie.reindex(periodos, fill_value=0)

      desde_d = pd.Timestamp(desde).date()
      hasta_d = pd.Timestamp(hasta).date()
      etiquetas = []

      for p in periodos:
        eff_start = max(p.start_time.date(), desde_d)
        eff_end = min(p.end_time.date(), hasta_d)

        if pfreq == "D":
          lbl = eff_start.strftime("%d/%m/%Y")
        elif pfreq == "M":
          if eff_start == p.start_time.date() and eff_end == p.end_time.date():
            lbl = p.start_time.strftime("%m/%Y")
          else:
            lbl = f"Del {eff_start:%d/%m} al {eff_end:%d/%m/%Y}"
        else:
          if eff_start == p.start_time.date() and eff_end == p.end_time.date():
            lbl = f"Semana del {eff_start:%d/%m/%Y}"
          else:
            lbl = f"Del {eff_start:%d/%m} al {eff_end:%d/%m/%Y}"
        etiquetas.append(lbl)

      evol = pd.DataFrame(
          {"Inicio": periodos.start_time, medida: serie.values, "Etiqueta": etiquetas}
      )
      return evol

    evol = evolucion(df_sel, rango[0], rango[1])
    hover_medida = (
        "Valor vendido: $%{y:,.0f}"
        if medida == "Valor"
        else "Pedidos: %{y:,.0f}"
    )

    # Gráfico de líneas: valor vendido o pedidos por día/semana/mes; el período anterior va en línea punteada.
    fig = px.line(
        evol, x="Inicio", y=medida, markers=True, custom_data=["Etiqueta"]
    )
    fig.update_traces(
        name="Período seleccionado",
        showlegend=False,
        line_color=BASE,
        marker_color=BASE,
        hovertemplate="%{customdata[0]}<br>" + hover_medida + "<extra></extra>",
    )

    if comparable:
      evol_prev = evolucion(df_prev, prev_ini, prev_fin)
      n_puntos = min(len(evol), len(evol_prev))

      fig.add_scatter(
          x=evol["Inicio"].iloc[:n_puntos],
          y=evol_prev[medida].iloc[:n_puntos],
          mode="lines",
          name="Período anterior",
          showlegend=True,
          line=dict(color=GRIS, dash="dash", width=2),
          customdata=evol_prev[["Etiqueta"]].iloc[:n_puntos],
          hovertemplate=(
              "Anterior: %{customdata[0]}<br>" + hover_medida + "<extra></extra>"
          ),
      )

    fig.update_layout(
        template="plotly_white",
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title=None,
        legend=dict(
            orientation="h",
            y=1.12,
            x=0,
            title_text="",
        ),
    )
    fig.update_xaxes(tickformat=fmt_eje)
    fig.update_yaxes(rangemode="tozero")
    st.plotly_chart(fig, width="stretch")

    # --- PREGUNTA 2 — ¿Qué empleados tienen mayor rendimiento y cuáles quedan por debajo del 70% del promedio? ¿Hay diferencia por menor volumen y/o por menor valor de los pedidos?
    st.subheader(f"{texto_medida} por empleado")
    st.caption("*Amarillo: posible necesidad de apoyo.*  \n"
               "*Click en un empleado para filtrar el resto del tablero y click de nuevo para sacarlo; pudiendo elegir varios.*")

    rank = (df.groupby("Empleado", as_index=False)
              .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"))
              .sort_values(medida))
    rank["ValorPorPedido"] = rank["Valor"] / rank["Pedidos"]
    promedio = rank[medida].mean()
    umbral = promedio * 0.7
    abajo = rank[medida] < umbral

    colores = [ACENTO if e in emp_sel else (AMARILLO if a_ else BASE) for e, a_ in zip(rank["Empleado"], abajo)]

    # Gráfico de lollipop (puntos con tallo): una fila por empleado, según la medida elegida (valor o pedidos).
    fig = go.Figure()

    # Tallos horizontales del lollipop.
    for _, fila in rank.iterrows():
        fig.add_shape(
            type="line",
            x0=0, x1=fila[medida],
            y0=fila["Empleado"], y1=fila["Empleado"],
            line=dict(color="rgba(128, 128, 128, 0.5)", width=0.5),
            layer="below"
        )

    # Puntos.
    fig.add_trace(go.Scatter(
        x=rank[medida],
        y=rank["Empleado"],
        mode="markers",
        marker=dict(size=13, color=colores),
        customdata=rank[["Valor", "Pedidos", "ValorPorPedido"]],
        hovertemplate="<b>%{y}</b><br>Valor: $%{customdata[0]:,.0f}"
                    "<br>Pedidos: %{customdata[1]}"
                    "<br>Valor por pedido: $%{customdata[2]:,.0f}<extra></extra>",
        showlegend=False
    ))

    fig.update_xaxes(type="linear", rangemode="tozero")
    fig.update_yaxes(showgrid=False)
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

    # La key cambia después de cada click (v), así el gráfico arranca "limpio" cada vez
    # y cada click llega como un evento nuevo: la selección real la guardamos nosotros en emp_sel.
    v = st.session_state.get("v", 0)
    evento = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key=f"ranking_{v}", width="stretch")
    clickeados = [p["y"] for p in evento["selection"]["points"]]
    if clickeados:
        st.session_state["emp_sel"] = sorted(set(emp_sel) ^ set(clickeados))  # ^ = agrega si no estaba, saca si estaba
        st.session_state["v"] = v + 1
        st.rerun()


# ===== VISTA 2: PRODUCTOS, CLIENTES Y CIUDADES
with tab2:

    # --- PREGUNTA 4 — ¿Qué productos generan más valor y cuáles se vendieron en mayor cantidad?
    prod = (df_sel.groupby("Producto", as_index=False)
                  .agg(Valor=("Valor", "sum"), Unidades=("Cantidad", "sum")))
    top_valor = prod.nlargest(10, "Valor").sort_values("Valor")
    top_unid = prod.nlargest(10, "Unidades").sort_values("Unidades")
    en_ambos = set(top_valor["Producto"]) & set(top_unid["Producto"])


    # Gráfico de barras horizontales: top 10 productos; en verde los que están en ambos rankings.
    def barras_top(d, col, plantilla):
        fig = px.bar(d, x=col, y="Producto", orientation="h")
        fig.update_traces(marker_color=[ACENTO if p in en_ambos else BASE for p in d["Producto"]],
                          texttemplate=plantilla, textposition="outside", cliponaxis=False, hovertemplate=None, hoverinfo="skip")
        fig.update_layout(template="plotly_white", height=380, margin=dict(l=0, r=40, t=10, b=0),
                          yaxis_title=None, xaxis_title=None)
        return fig


    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Top 10 productos por valor vendido")
        st.plotly_chart(barras_top(top_valor, "Valor", "$%{x:,.0f}"), width="stretch")
    with col_b:
        st.subheader("Top 10 productos por unidades vendidas")
        st.plotly_chart(barras_top(top_unid, "Unidades", "%{x:,.0f}"), width="stretch")
    st.caption(f"*Verde: productos que están en los dos rankings ({len(en_ambos)} de 10).*")

    # --- PREGUNTA 3 — ¿Cómo se distribuyen el valor y los pedidos por ciudad, y qué clientes son los más relevantes respecto al valor y la recurrencia?
    st.subheader("Valor y pedidos por ciudad")
    st.caption("*EL tamaño del círculo indica la cantidad de pedidos y el color indica el valor vendido (más oscuro = mayor valor).*  \n"
                "*Se nombran las 5 ciudades con más valor.*")
    geo = (df_sel.groupby(["CiudadCliente", "LatitudCiudadCliente", "LongitudCiudadCliente"], as_index=False)
                    .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"), Clientes=("IdCliente", "nunique")))
    top_ciudades = set(geo.nlargest(5, "Valor")["CiudadCliente"])
    geo["Etiqueta"] = geo["CiudadCliente"].where(geo["CiudadCliente"].isin(top_ciudades), "")

    # Mapa de burbujas: tamaño = pedidos, color = valor vendido, una burbuja por ciudad.
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


    # --- PREGUNTA 3 (parte 2) — clientes más relevantes: importancia (valor) vs. recurrencia (pedidos)
    st.subheader("Análisis de Clientes: Importancia (Valor) vs. Recurrencia (Pedidos)")
    st.caption("*Las líneas punteadas representan la mediana de la empresa.*  \n"
               "*Se pueden ocultar regiones haciendo click en su leyenda.*")

    # Agrupamos a nivel cliente
    clientes = (
        df_sel.groupby(["IdCliente", "Cliente", "CiudadCliente", "RegionCliente"], as_index=False)
            .agg(Valor=("Valor", "sum"), Pedidos=("IdPedido", "nunique"))
    )

    # Agregamos un jitter para solucionar, en cierta medida, la superposición de puntos
    np.random.seed(42)
    clientes["Pedidos_Jitter"] = clientes["Pedidos"] + np.random.uniform(-0.15, 0.15, size=len(clientes))

    # Generamos las características de los puntos por región (forma y color)
    simbolos_region = {
        "Europa": "circle",
        "América del Norte": "square",
        "América del Sur": "diamond"
    }
    colores_region = {
        "Europa": BASE,
        "América del Norte": ACENTO,
        "América del Sur": RUMBO_DISCRETA[0]
    }

    # Gráfico de dispersión: un punto por cliente (x = pedidos, y = valor), forma y color según región.
    fig = px.scatter(
        clientes,
        x="Pedidos_Jitter",
        y="Valor",
        color="RegionCliente",
        symbol="RegionCliente",
        color_discrete_map=colores_region,
        symbol_map=simbolos_region,
        custom_data=["Cliente", "CiudadCliente", "RegionCliente", "Valor", "Pedidos"]
    )

    # Calculamos la mediana general (1 única línea X e Y para toda la empresa)
    mediana_x = clientes["Pedidos"].median()
    mediana_y = clientes["Valor"].median()

    fig.add_vline(x=mediana_x, line_dash="dot", line_color=GRIS)
    fig.add_hline(y=mediana_y, line_dash="dot", line_color=GRIS)


    fig.update_traces(
        marker=dict(size=10, opacity=0.85, line=dict(width=0.6, color="white")),
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]}, %{customdata[2]})<br>"
                    "Pedidos reales: <b>%{customdata[4]}</b><br>"
                    "Valor vendido: <b>$%{customdata[3]:,.0f}</b><extra></extra>"
    )

    fig.update_layout(
        template="plotly_white",
        height=400,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Cantidad de pedidos realizados (Recurrencia)",
        yaxis_title="Valor vendido total ($ - Importancia)",
        legend=dict(orientation="h", y=1.1, x=0, title_text="Región:")
    )
    fig.update_xaxes(rangemode="tozero")
    fig.update_yaxes(rangemode="tozero")

    st.plotly_chart(fig, width="stretch")

