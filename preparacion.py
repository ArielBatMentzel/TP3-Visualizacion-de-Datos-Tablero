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

COLUMNAS_RAW = ["IdPedido", "IdCliente", "NombreCompania", "Ciudad", "Nombre", "Apellidos",
                "NombreProducto", "PrecioUnidad", "Cantidad", "FechaPedido", "FechaEntrega", "FechaEnvío"]

df = pd.read_csv(ENTRADA, usecols=COLUMNAS_RAW).rename(columns={
    "NombreCompania": "Cliente",
    "Ciudad": "CiudadCliente",
    "Apellidos": "ApellidoEmpleado",
    "Nombre": "NombreEmpleado",
    "NombreProducto": "Producto",
    "FechaEnvío": "FechaEnvio",
})

for fecha in ["FechaPedido", "FechaEntrega", "FechaEnvio"]:
    df[fecha] = pd.to_datetime(df[fecha], format="%m/%d/%Y")

for col in ["IdCliente", "Cliente", "CiudadCliente", "ApellidoEmpleado", "NombreEmpleado", "Producto"]:
    df[col] = df[col].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()

df["CiudadCliente"] = df["CiudadCliente"].replace({
    "Sao Paulo": "São Paulo",
    "Lion": "Lyon",
    "Francfurt": "Fráncfort",
    "Eugenia": "Eugene",
})

ciudades = pd.read_csv("data/interim/ciudades.csv")
df = df.merge(ciudades, on="CiudadCliente", how="left")
assert df["LatitudCiudadCliente"].notna().all(), "Hay ciudades sin coordenadas"

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
assert df["RegionCliente"].notna().all(), "Hay ciudades sin región asignada"

df["Empleado"] = df["NombreEmpleado"] + " " + df["ApellidoEmpleado"]
df["Valor"] = (df["Cantidad"] * df["PrecioUnidad"]).round(2)

cols_lineas = [
    "FechaPedido", "Empleado", "IdPedido", "Valor", "IdCliente",
    "Producto", "Cantidad", "CiudadCliente", "RegionCliente", "LatitudCiudadCliente",
    "LongitudCiudadCliente", "Cliente"
]
cols_pedidos = ["FechaPedido", "FechaEntrega", "FechaEnvio", "Empleado"]

chequeo = df.groupby("IdPedido")[cols_pedidos].nunique(dropna=False).max()
assert (chequeo == 1).all(), f"Hay datos de pedido que varían entre líneas:\n{chequeo}"

lineas = df[cols_lineas]
pedidos = df.drop_duplicates("IdPedido")[cols_pedidos]

os.makedirs(SALIDA, exist_ok=True)
lineas.to_csv(f"{SALIDA}/lineas.csv", index=False)
pedidos.to_csv(f"{SALIDA}/pedidos.csv", index=False)

print("lineas:", lineas.shape, "| pedidos:", pedidos.shape)
