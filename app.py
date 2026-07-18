from pathlib import Path
import csv
import shutil
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PEDIDOS_DIR = BASE_DIR / "pedidos"
DB_DIR = BASE_DIR / "db"
DB_PATH = DB_DIR / "pedidos_vendedores.sqlite3"


def ensure_dirs() -> None:
    DB_DIR.mkdir(exist_ok=True)
    for vendor_dir in [PEDIDOS_DIR / "ven01", PEDIDOS_DIR / "ven02"]:
        (vendor_dir / "pendientes").mkdir(parents=True, exist_ok=True)
        (vendor_dir / "procesados").mkdir(parents=True, exist_ok=True)
        (vendor_dir / "errores").mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS vendedores (
            codigo TEXT PRIMARY KEY,
            nombre TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS listas_precio (
            codigo TEXT PRIMARY KEY,
            nombre TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS articulos (
            codigo TEXT PRIMARY KEY,
            descripcion TEXT NOT NULL,
            rubro TEXT,
            marca TEXT,
            iva REAL,
            stock REAL
        );

        CREATE TABLE IF NOT EXISTS precios_articulo (
            articulo_codigo TEXT NOT NULL,
            lista_codigo TEXT NOT NULL,
            precio REAL NOT NULL,
            PRIMARY KEY (articulo_codigo, lista_codigo)
        );

        CREATE TABLE IF NOT EXISTS clientes (
            codigo TEXT PRIMARY KEY,
            razon_social TEXT NOT NULL,
            nombre_fantasia TEXT,
            direccion TEXT,
            localidad TEXT,
            provincia TEXT,
            cat_iva TEXT,
            cuit TEXT,
            codigo_vendedor TEXT,
            codigo_lista_precio TEXT
        );

        CREATE TABLE IF NOT EXISTS pedido_counters (
            vendedor_codigo TEXT PRIMARY KEY,
            siguiente INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido TEXT PRIMARY KEY,
            vendedor_codigo TEXT NOT NULL,
            cliente_codigo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL,
            total REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS detalle_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pedido TEXT NOT NULL,
            codigo_articulo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            precio REAL NOT NULL,
            subtotal REAL NOT NULL
        );
        """
    )
    conn.commit()


def import_csv_table(conn: sqlite3.Connection, table_name: str, csv_path: Path, columns: list[str]) -> int:
    if not csv_path.exists():
        return 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        return 0

    placeholders = ", ".join(["?"] * len(columns))
    columns_sql = ", ".join(columns)
    for row in rows:
        values = [row.get(column, "") for column in columns]
        conn.execute(f"INSERT OR REPLACE INTO {table_name} ({columns_sql}) VALUES ({placeholders})", values)
    conn.commit()
    return len(rows)


def load_master_data(conn: sqlite3.Connection) -> None:
    import_csv_table(conn, "vendedores", DATA_DIR / "vendedores.csv", ["codigo", "nombre"])
    import_csv_table(conn, "listas_precio", DATA_DIR / "listas_precio.csv", ["codigo", "nombre"])
    import_csv_table(conn, "articulos", DATA_DIR / "articulos.csv", ["codigo", "descripcion", "rubro", "marca", "iva", "stock"])
    import_csv_table(conn, "precios_articulo", DATA_DIR / "precios_articulo.csv", ["articulo_codigo", "lista_codigo", "precio"])
    import_csv_table(conn, "clientes", DATA_DIR / "clientes.csv", ["codigo", "razon_social", "nombre_fantasia", "direccion", "localidad", "provincia", "cat_iva", "cuit", "codigo_vendedor", "codigo_lista_precio"])

    for codigo in ["01", "02"]:
        conn.execute("INSERT OR IGNORE INTO pedido_counters (vendedor_codigo, siguiente) VALUES (?, ?)", (codigo, 1))
    conn.commit()


def get_next_order_id(conn: sqlite3.Connection, vendedor_codigo: str) -> str:
    row = conn.execute("SELECT siguiente FROM pedido_counters WHERE vendedor_codigo = ?", (vendedor_codigo,)).fetchone()
    if row is None:
        next_number = 1
        conn.execute("INSERT INTO pedido_counters (vendedor_codigo, siguiente) VALUES (?, ?)", (vendedor_codigo, 2))
    else:
        next_number = int(row["siguiente"])
        conn.execute("UPDATE pedido_counters SET siguiente = ? WHERE vendedor_codigo = ?", (next_number + 1, vendedor_codigo))
    conn.commit()
    return str(next_number * 100 + int(vendedor_codigo))


def process_pending_orders(conn: sqlite3.Connection) -> int:
    processed_count = 0
    for vendor_dir in sorted(PEDIDOS_DIR.glob("ven*")):
        pending_dir = vendor_dir / "pendientes"
        processed_dir = vendor_dir / "procesados"
        processed_dir.mkdir(exist_ok=True)
        for header_path in sorted(pending_dir.glob("encabezado_*.csv")):
            stem = header_path.stem.replace("encabezado_", "")
            detail_path = pending_dir / f"detallePedido_{stem}.csv"
            if not detail_path.exists():
                continue

            with header_path.open("r", encoding="utf-8-sig", newline="") as handle:
                header_rows = list(csv.DictReader(handle))
            if not header_rows:
                continue

            header = header_rows[0]
            vendedor_codigo = vendor_dir.name.replace("ven", "").zfill(2)
            cliente_codigo = header.get("cliente_codigo", "")
            fecha = header.get("fecha", "")
            estado = header.get("estado", "pendiente")

            id_pedido = get_next_order_id(conn, vendedor_codigo)
            total = 0.0
            conn.execute(
                "INSERT INTO pedidos (id_pedido, vendedor_codigo, cliente_codigo, fecha, estado, total) VALUES (?, ?, ?, ?, ?, ?)",
                (id_pedido, vendedor_codigo, cliente_codigo, fecha, estado, 0.0),
            )

            with detail_path.open("r", encoding="utf-8-sig", newline="") as handle:
                detail_rows = list(csv.DictReader(handle))

            for detail in detail_rows:
                codigo_articulo = detail.get("codigo_articulo", "")
                cantidad = float(detail.get("cantidad", 0) or 0)
                precio = float(detail.get("precio", 0) or 0)
                subtotal = cantidad * precio
                total += subtotal
                conn.execute(
                    "INSERT INTO detalle_pedido (id_pedido, codigo_articulo, cantidad, precio, subtotal) VALUES (?, ?, ?, ?, ?)",
                    (id_pedido, codigo_articulo, cantidad, precio, subtotal),
                )

            conn.execute("UPDATE pedidos SET total = ? WHERE id_pedido = ?", (total, id_pedido))
            conn.commit()

            shutil.move(str(header_path), str(processed_dir / header_path.name))
            shutil.move(str(detail_path), str(processed_dir / detail_path.name))
            processed_count += 1

    return processed_count


def main() -> None:
    ensure_dirs()
    conn = connect()
    create_tables(conn)
    load_master_data(conn)
    processed = process_pending_orders(conn)
    print(f"Base creada en: {DB_PATH}")
    print(f"Pedidos importados: {processed}")
    conn.close()


if __name__ == "__main__":
    main()
