# Pedidos Vendedores

Proyecto base para gestionar pedidos por vendedor usando archivos CSV.

## Estructura

- data/: archivos CSV maestros (vendedores, listas de precio, artículos, clientes)
- pedidos/: carpetas por vendedor con subcarpetas pendientes, procesados y errores
- db/: base SQLite generada automáticamente
- importar_pedidos.py: procesa los CSV de pedidos desde las carpetas por vendedor

## Archivos maestros

- vendedores.csv
- listas_precio.csv
- articulos.csv
- precios_articulo.csv
- clientes.csv

## Uso

1. Instalar Python 3.10+
2. Ejecutar:
   python app.py
3. Para levantar la interfaz web:
   python manage.py runserver
4. Para procesar pedidos desde CSV:
   python importar_pedidos.py
