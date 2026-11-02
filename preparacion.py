"""
Preparación de DW_Pedidos para el tablero (TP3).
Lee el CSV original, renombra columnas, estandariza valores y guarda dos archivos limpios:
  data/lineas.csv  -> una fila por línea de pedido (pedido x producto)
  data/pedidos.csv -> una fila por pedido (para conteos y envíos)
"""
import os
import pandas as pd

ENTRADA = "data/raw/DW_Pedidos.csv"
SALIDA = "data/processed"

df = pd.read_csv(ENTRADA)

# 1) Renombrar columnas: sin tildes, sin duplicados (Ciudad / Ciudad.1, etc.)
#    y aclarando a quién pertenece cada dato (cliente / empleado / transportista)
df = df.rename(columns={
    "NombreCompania": "Cliente",
    "NombreContacto": "ContactoCliente",
    "CargoContacto": "CargoContactoCliente",
    "Dirección": "DireccionCliente",
    "Ciudad": "CiudadCliente",
    "Telefono": "TelefonoCliente",

    "Apellidos": "ApellidoEmpleado",
    "Nombre": "NombreEmpleado",
    "FechaNacimiento": "FechaNacimientoEmpleado",
    "FechaContratación": "FechaContratacionEmpleado",
    "Dirección.1": "DireccionEmpleado",
    "Ciudad.1": "CiudadEmpleado",
    "País": "PaisEmpleado",

    "FechaEnvío": "FechaEnvio",
    
    "FormaEnvío": "IdTransportista",
    "NombreCompañía": "Transportista",
    "Teléfono": "TelefonoTransportista",

    "NombreProducto": "Producto",
    "Costo": "CostoUnidad", 
})

# 2) Tipos de datos
fechas = ["FechaNacimientoEmpleado", "FechaContratacionEmpleado",
          "FechaPedido", "FechaEntrega", "FechaEnvio"]
numericas = ["IdPedido", "IdEmpleado", "IdTransportista",
             "PrecioUnidad", "Cantidad", "CostoUnidad"]
cols_text = [col for col in df.columns if col not in fechas + numericas]

for fecha in fechas:
    df[fecha] = pd.to_datetime(df[fecha], format="%m/%d/%Y")  

# 3) Estandarizar texto: espacios dobles y bordes
for col in cols_text:
    df[col] = df[col].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()

# 4) Estandarizar ciudades de clientes (duplicados y errores de traducción)
df["CiudadCliente"] = df["CiudadCliente"].replace({
    "Sao Paulo": "São Paulo",  
    "Lion": "Lyon",
    "Francfurt": "Fráncfort",
    "Eugenia": "Eugene",       
})

ciudades = pd.read_csv("data/interim/ciudades.csv")
df = df.merge(ciudades, on="CiudadCliente", how="left")
assert df["LatitudCiudadCliente"].notna().all(), "Hay ciudades sin coordenadas"

# 5) Columnas calculadas fila por fila
df["Empleado"] = df["NombreEmpleado"] + " " + df["ApellidoEmpleado"]
df["Valor"] = (df["Cantidad"] * df["PrecioUnidad"]).round(2)
df["CostoTotal"] = (df["Cantidad"] * df["CostoUnidad"]).round(2)


# 6) Tabla a nivel pedido (una fila por IdPedido)
cols_pedido = ["IdPedido", "IdCliente", "Cliente", "CiudadCliente",
               "IdEmpleado", "Empleado", "IdTransportista", "Transportista",
               "FechaPedido", "FechaEntrega", "FechaEnvio"]
chequeo = df.groupby("IdPedido")[cols_pedido[1:]].nunique(dropna=False).max()
assert (chequeo == 1).all(), f"Hay datos de pedido que varían entre líneas:\n{chequeo}"

pedidos = df[cols_pedido].drop_duplicates("IdPedido").copy()
pedidos["ValorPedido"] = pedidos["IdPedido"].map(df.groupby("IdPedido")["Valor"].sum())
pedidos["CostoTotalPedido"] = pedidos["IdPedido"].map(df.groupby("IdPedido")["CostoTotal"].sum())
pedidos["Pendiente"] = pedidos["FechaEnvio"].isna()
pedidos["DiasHastaEnvio"] = (pedidos["FechaEnvio"] - pedidos["FechaPedido"]).dt.days
pedidos["FueraDePlazo"] = ((pedidos["FechaEnvio"] > pedidos["FechaEntrega"])
                           .astype("boolean").mask(pedidos["Pendiente"]))  

# 7) Guardar
os.makedirs(SALIDA, exist_ok=True)
df.to_csv(f"{SALIDA}/lineas.csv", index=False)
pedidos.to_csv(f"{SALIDA}/pedidos.csv", index=False)

print("lineas:", df.shape, "| pedidos:", pedidos.shape)
print("pendientes:", int(pedidos["Pendiente"].sum()),
      "| fuera de plazo:", int(pedidos["FueraDePlazo"].sum()))
