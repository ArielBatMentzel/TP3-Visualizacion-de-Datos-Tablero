"""
Paleta "Rumbo": tema marítimo/comercial (arena -> verde agua -> turquesa -> petróleo -> azul marino).

- Construida en el espacio CAM02-UCS: la luminosidad baja de forma lineal y cada paso tiene la misma
  diferencia perceptual (dE ~ 0.36 entre pasos de 256), igual que viridis.
- Segura para daltonismo: va de claro a oscuro, así que se distingue también por luminosidad.
- Sentido de lectura: claro = poco, oscuro = mucho.

Uso con Plotly:
    px.scatter_geo(..., color_continuous_scale=RUMBO_CONTINUA)
    px.bar(..., color_discrete_sequence=rumbo_discreta(3))
"""

# Continua: 17 paradas [posición, color] (Plotly interpola entre ellas)
RUMBO_CONTINUA = [[0.0, '#F6EBCB'], [0.0625, '#DCE1C3'], [0.125, '#C5D6BB'], [0.1875, '#AECBB2'], [0.25, '#96C0A9'], [0.3125, '#7EB5A1'], [0.375, '#64AA99'], [0.4375, '#479F93'], [0.5, '#27938D'], [0.5625, '#0C8789'], [0.625, '#007B87'], [0.6875, '#006E84'], [0.75, '#00617E'], [0.8125, '#055271'], [0.875, '#0A4463'], [0.9375, '#0C3555'], [1.0, '#0A2747']]

# Discreta: 5 colores (para menos categorías usar rumbo_discreta(n))
RUMBO_DISCRETA = ['#A2C6AE', '#58A696', '#038288', '#005C7B', '#0B3352']

# Colores de uso general
BASE = "#035574"      # marcas por defecto (de la paleta, contraste 8.2:1 sobre blanco)
ACENTO = "#50A395"    # elemento seleccionado (de la paleta)
GRIS = "#BDBDBD"      # líneas auxiliares
AMARILLO = "#E5A000"  # advertencia (líneas, marcadores, números grandes)
AMARILLO_TEXTO = "#9A6700"  # advertencia en texto chico (el amarillo puro no se lee sobre blanco)
ROJO = "#D62728"      # problema


def _hex_a_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def _color_en(pos):
    """Color de la paleta continua en la posición pos (0 = claro, 1 = oscuro)."""
    pos = min(max(pos, 0.0), 1.0)
    for (p0, c0), (p1, c1) in zip(RUMBO_CONTINUA, RUMBO_CONTINUA[1:]):
        if pos <= p1:
            f = (pos - p0) / (p1 - p0)
            a, b = _hex_a_rgb(c0), _hex_a_rgb(c1)
            return "#%02X%02X%02X" % tuple(round(x + (y - x) * f) for x, y in zip(a, b))
    return RUMBO_CONTINUA[-1][1]


def rumbo_discreta(n, desde=0.25, hasta=0.95):
    """n colores equiespaciados de la paleta (se evita el extremo más claro porque no se ve sobre blanco)."""
    if n == 1:
        return [_color_en((desde + hasta) / 2)]
    return [_color_en(desde + (hasta - desde) * i / (n - 1)) for i in range(n)]
