from pathlib import Path
import csv
import sqlite3
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "pedidos_vendedores.sqlite3"
PEDIDOS_DIR = BASE_DIR / "pedidos"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_next_id(conn, vendedor_codigo):
    row = conn.execute("SELECT MAX(id_pedido) as max_id FROM pedidos WHERE vendedor_codigo = ?", (vendedor_codigo,)).fetchone()
    max_id = row["max_id"] if row and row["max_id"] else None
    if max_id and str(max_id).isdigit():
        next_num = (int(max_id) // 10000) + 1
    else:
        next_num = 1
    return str(next_num * 10000 + int(vendedor_codigo))


def process_folder(vendedor_code: str, source_dir: Path):
    conn = connect()
    for header_path in sorted(source_dir.glob("encabezado_*.csv")):
        stem = header_path.stem.replace("encabezado_", "")
        detail_path = source_dir / f"detallePedido_{stem}.csv"
        if not detail_path.exists():
            continue

        with header_path.open("r", encoding="utf-8-sig", newline="") as handle:
            headers = list(csv.DictReader(handle))
        if not headers:
            continue
        header = headers[0]

        pedido_id = get_next_id(conn, vendedor_code)
        cliente_codigo = header.get("cliente_codigo", "")
        fecha = header.get("fecha", datetime.now().date())
        estado = header.get("estado", "pendiente")
        total = 0.0

        conn.execute(
            "INSERT INTO pedidos (id_pedido, vendedor_codigo, cliente_codigo, fecha, estado, total) VALUES (?, ?, ?, ?, ?, ?)",
            (pedido_id, vendedor_code, cliente_codigo, str(fecha), estado, total),
        )

        with detail_path.open("r", encoding="utf-8-sig", newline="") as handle:
            details = list(csv.DictReader(handle))

        for detail in details:
            precio = float(detail.get("precio", 0) or 0)
            cantidad = float(detail.get("cantidad", 0) or 0)
            subtotal = cantidad * precio
            total += subtotal
            conn.execute(
                "INSERT INTO detalle_pedido (id_pedido, codigo_articulo, cantidad, precio, subtotal) VALUES (?, ?, ?, ?, ?)",
                (pedido_id, detail.get("codigo_articulo", ""), cantidad, precio, subtotal),
            )

        conn.execute("UPDATE pedidos SET total = ? WHERE id_pedido = ?", (total, pedido_id))
        conn.commit()

        header_path.replace(source_dir.parent / "procesados" / header_path.name)
        detail_path.replace(source_dir.parent / "procesados" / detail_path.name)

    conn.close()


if __name__ == "__main__":
    for vendor_dir in sorted(PEDIDOS_DIR.glob("ven*")):
        process_folder(vendor_dir.name.replace("ven", ""), vendor_dir / "pendientes")
    print("Procesamiento finalizado")
