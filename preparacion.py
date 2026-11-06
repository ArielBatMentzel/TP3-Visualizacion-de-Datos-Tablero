"""
Preparación de DW_Pedidos para el tablero (TP3).
Lee el CSV original, renombra columnas, estandariza valores y guarda dos archivos limpios
optimizados con únicamente las columnas consumidas por app.py:
  data/processed/lineas.csv  -> una fila por línea de pedido (pedido x producto)
  data/processed/pedidos.csv -> una fila por pedido (para conteos y envíos)
"""
import os
import pandas as pd

ENTRADA = "data/raw/DW_Pedidos.csv"
SALIDA = "data/processed"

df = pd.read_csv(ENTRADA)

# 1) Renombrar columnas
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

# 3) Estandarizar texto
for col in cols_text:
    df[col] = df[col].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()

# 4) Estandarizar ciudades de clientes
df["CiudadCliente"] = df["CiudadCliente"].replace({
    "Sao Paulo": "São Paulo",  
    "Lion": "Lyon",
    "Francfurt": "Fráncfort",
    "Eugenia": "Eugene",       
})

ciudades = pd.read_csv("data/interim/ciudades.csv")
df = df.merge(ciudades, on="CiudadCliente", how="left")
assert df["LatitudCiudadCliente"].notna().all(), "Hay ciudades sin coordenadas"

# Mapeo de región por ciudad
mapa_regiones = {
    'Albuquerque': 'América del Norte', 'Anchorage': 'América del Norte', 'Boise': 'América del Norte',
    'Butte': 'América del Norte', 'Elgin': 'América del Norte', 'Eugene': 'América del Norte',
    'Kirkland': 'América del Norte', 'Lander': 'América del Norte', 'Montreal': 'América del Norte',
    'México D.F.': 'América del Norte', 'Portland': 'América del Norte', 'San Francisco': 'América del Norte',
    'Seattle': 'América del Norte', 'Tsawassen': 'América del Norte', 'Vancouver': 'América del Norte',
    'Walla Walla': 'América del Norte',
    
    'Barquisimeto': 'América del Sur', 'Buenos Aires': 'América del Sur', 'Campinas': 'América del Sur',
    'Caracas': 'América del Sur', 'I. de Margarita': 'América del Sur', 'Resende': 'América del Sur',
    'Rio de Janeiro': 'América del Sur', 'San Cristóbal': 'América del Sur', 'São Paulo': 'América del Sur',
    
    'Aachen': 'Europa', 'Barcelona': 'Europa', 'Berlín': 'Europa', 'Brandenburgo': 'Europa',
    'Bruselas': 'Europa', 'Bräcke': 'Europa', 'Bérgamo': 'Europa', 'Charleroi': 'Europa',
    'Cork': 'Europa', 'Cowes': 'Europa', 'Cunewalde': 'Europa', 'Estrasburgo': 'Europa',
    'Fráncfort': 'Europa', 'Graz': 'Europa', 'Génova': 'Europa', 'Helsinki': 'Europa',
    'Köln': 'Europa', 'København': 'Europa', 'Leipzig': 'Europa', 'Lille': 'Europa',
    'Lisboa': 'Europa', 'Londres': 'Europa', 'Luleå': 'Europa', 'Lyon': 'Europa',
    'Madrid': 'Europa', 'Mannheim': 'Europa', 'Marsella': 'Europa', 'München': 'Europa',
    'Münster': 'Europa', 'Nantes': 'Europa', 'Oulu': 'Europa', 'París': 'Europa',
    'Reggio Emilia': 'Europa', 'Reims': 'Europa', 'Salzburgo': 'Europa', 'Sevilla': 'Europa',
    'Stavern': 'Europa', 'Stuttgart': 'Europa', 'Torino': 'Europa', 'Toulouse': 'Europa',
    'Versalles': 'Europa', 'Warszawa': 'Europa', 'Århus': 'Europa'
}

df["RegionCliente"] = df["CiudadCliente"].map(mapa_regiones)

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

# 7) Selección de columnas consumidas por el tablero (app.py)
cols_lineas_app = [
    "FechaPedido", "Empleado", "IdPedido", "Valor", "IdCliente",
    "Producto", "Cantidad", "CiudadCliente", "RegionCliente", "LatitudCiudadCliente",
    "LongitudCiudadCliente", "Cliente"
]

cols_pedidos_app = [
    "FechaPedido", "FechaEntrega", "FechaEnvio", "Empleado"
]

lineas_out = df[cols_lineas_app]
pedidos_out = pedidos[cols_pedidos_app]

# 8) Guardar
os.makedirs(SALIDA, exist_ok=True)
lineas_out.to_csv(f"{SALIDA}/lineas.csv", index=False)
pedidos_out.to_csv(f"{SALIDA}/pedidos.csv", index=False)

print("lineas:", lineas_out.shape, "| pedidos:", pedidos_out.shape)
print("pendientes:", int(pedidos["Pendiente"].sum()),
      "| fuera de plazo:", int(pedidos["FueraDePlazo"].sum()))