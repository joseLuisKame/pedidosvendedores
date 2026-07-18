from django.shortcuts import render, redirect
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Articulo, Cliente, Pedido, DetallePedido, ListaPrecio, PrecioArticulo
from decimal import Decimal
import csv
import json
from io import StringIO
from pathlib import Path
from datetime import datetime


def _serialize_draft_for_session(draft):
    def convert_value(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert_value(v) for v in value]
        return value

    return convert_value(draft)


def _deserialize_draft_from_session(draft):
    def convert_value(value):
        if isinstance(value, str):
            try:
                if "." in value or "e" in value.lower():
                    return Decimal(value)
            except Exception:
                pass
        if isinstance(value, dict):
            return {k: convert_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert_value(v) for v in value]
        return value

    return convert_value(draft)


def _import_articulos(rows):
    count = 0
    for row in rows:
        codigo = (row.get("codigo") or row.get("Codigo_Articulo") or "").strip()
        if not codigo:
            continue
        Articulo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "descripcion": (row.get("descripcion") or row.get("Descripcion") or "").strip(),
                "rubro": (row.get("rubro") or row.get("Rubro") or "").strip(),
                "marca": (row.get("marca") or row.get("Marca") or "").strip(),
                "iva": row.get("iva") or row.get("Iva") or 0,
                "stock": row.get("stock") or row.get("Stock") or 0,
            },
        )
        count += 1
    return count


def _import_listas_precio(rows):
    count = 0
    for row in rows:
        codigo = (row.get("codigo") or row.get("codigo_lista_precio") or "").strip()
        if not codigo:
            continue
        ListaPrecio.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": (row.get("nombre") or row.get("descripcion") or "Lista").strip()},
        )
        count += 1
    return count


def _import_precios(rows):
    count = 0
    for row in rows:
        articulo_codigo = (row.get("articulo_codigo") or row.get("articulo") or "").strip()
        lista_codigo = (row.get("lista_codigo") or row.get("lista") or "").strip()
        precio = row.get("precio", 0)
        if not articulo_codigo or not lista_codigo:
            continue
        articulo = Articulo.objects.filter(codigo=articulo_codigo).first()
        lista = ListaPrecio.objects.filter(codigo=lista_codigo).first()
        if articulo and lista:
            PrecioArticulo.objects.update_or_create(
                articulo=articulo,
                lista=lista,
                defaults={"precio": Decimal(str(precio))},
            )
            count += 1
    return count


def _import_clientes(rows):
    count = 0
    for row in rows:
        codigo = (row.get("codigo") or row.get("Codigo_cliente") or "").strip()
        if not codigo:
            continue
        Cliente.objects.update_or_create(
            codigo=codigo,
            defaults={
                "razon_social": (row.get("razon_social") or row.get("Razon_Social") or "").strip(),
                "nombre_fantasia": (row.get("nombre_fantasia") or row.get("Nombre_Fantasia") or "").strip(),
                "direccion": (row.get("direccion") or row.get("Direccion") or "").strip(),
                "localidad": (row.get("localidad") or row.get("Localidad") or "").strip(),
                "provincia": (row.get("provincia") or row.get("Provincia") or "").strip(),
                "cat_iva": (row.get("cat_iva") or row.get("Cat_Iva") or "").strip(),
                "cuit": (row.get("cuit") or row.get("Cuit") or "").strip(),
                "codigo_vendedor": (row.get("codigo_vendedor") or row.get("Codigo_vendedor") or "").strip(),
                "codigo_lista_precio": (row.get("codigo_lista_precio") or row.get("Codigo_lista_precio") or "").strip(),
            },
        )
        count += 1
    return count

BASE_DIR = Path(__file__).resolve().parent.parent

MAX_ITEMS = 5


def _get_item_inputs(request, count):
    items = []
    for index in range(1, count + 1):
        codigo = request.POST.get(f"articulo_{index}", "").strip()
        cantidad = request.POST.get(f"cantidad_{index}", "0").strip()
        items.append((index, codigo, cantidad))
    return items


def _buscar_clientes(texto):
    texto = (texto or "").strip()
    if not texto:
        return Cliente.objects.none()

    queryset = Cliente.objects.filter(
        Q(codigo__icontains=texto) |
        Q(razon_social__icontains=texto) |
        Q(nombre_fantasia__icontains=texto)
    )

    if texto.isdigit():
        queryset = queryset.order_by("codigo")
    else:
        queryset = queryset.order_by("razon_social", "nombre_fantasia", "codigo")
    return queryset[:10]


def _buscar_articulos(texto):
    texto = (texto or "").strip()
    if not texto:
        return Articulo.objects.none()

    queryset = Articulo.objects.filter(
        Q(codigo__icontains=texto) |
        Q(descripcion__icontains=texto) |
        Q(rubro__icontains=texto) |
        Q(marca__icontains=texto)
    )
    if texto.isdigit():
        queryset = queryset.order_by("codigo")
    else:
        queryset = queryset.order_by("descripcion", "codigo")
    return queryset[:10]


def _resolver_articulo(texto):
    texto = (texto or "").strip()
    if not texto:
        return None

    queryset = _buscar_articulos(texto)
    if queryset.exists():
        return queryset.first()

    return None


def _resolver_cliente(texto):
    texto = (texto or "").strip()
    if not texto:
        return None

    if " - " in texto:
        codigo = texto.split(" - ", 1)[0].strip()
        if codigo:
            cliente = Cliente.objects.filter(codigo=codigo).first()
            if cliente:
                return cliente

    return Cliente.objects.filter(codigo=texto).first() or Cliente.objects.filter(
        Q(razon_social__icontains=texto) |
        Q(nombre_fantasia__icontains=texto)
    ).first()


def _build_draft_header(cliente, fecha):
    return {
        "fecha": fecha,
        "cliente_codigo": cliente.codigo if cliente else "",
        "vendedor_codigo": cliente.codigo_vendedor if cliente else "",
    }


def _build_item_preview(cliente, articulo, cantidad=1):
    cantidad_dec = Decimal(str(cantidad or 1))
    precio = _get_precio_articulo(cliente, articulo)
    subtotal = cantidad_dec * precio
    return {
        "codigo": articulo.codigo,
        "descripcion": articulo.descripcion,
        "stock": articulo.stock,
        "cantidad": cantidad_dec,
        "precio": precio,
        "subtotal": subtotal,
    }


def home(request):
    pedidos_total = Pedido.objects.count()
    clientes_total = Cliente.objects.count()
    articulos_total = Articulo.objects.count()
    return render(request, "home.html", {
        "pedidos_total": pedidos_total,
        "clientes_total": clientes_total,
        "articulos_total": articulos_total,
    })


def import_csv(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("csv_file")
        if uploaded_file:
            decoded_file = uploaded_file.read().decode("utf-8-sig")
            reader = csv.DictReader(StringIO(decoded_file))
            for row in reader:
                Articulo.objects.update_or_create(
                    codigo=row.get("codigo", ""),
                    defaults={
                        "descripcion": row.get("descripcion", ""),
                        "rubro": row.get("rubro", ""),
                        "marca": row.get("marca", ""),
                        "iva": row.get("iva", 0),
                        "stock": row.get("stock", 0),
                    },
                )
            return redirect("home")
    return render(request, "import_csv.html")


def import_master_files(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("csv_file")
        if uploaded_file:
            decoded_file = uploaded_file.read().decode("utf-8-sig")
            reader = csv.DictReader(StringIO(decoded_file))
            rows = list(reader)
            if not rows:
                return render(request, "import_master_files.html", {"message": "El archivo está vacío."})

            headers = {h.lower() for h in rows[0].keys() if h}
            if "codigo" in headers and "descripcion" in headers:
                imported = _import_articulos(rows)
                return render(request, "import_master_files.html", {"message": f"Se importaron {imported} artículos."})

            if "codigo" in headers and "razon_social" in headers:
                imported = _import_clientes(rows)
                return render(request, "import_master_files.html", {"message": f"Se importaron {imported} clientes."})

            if "codigo" in headers and "nombre" in headers:
                imported = _import_listas_precio(rows)
                return render(request, "import_master_files.html", {"message": f"Se importaron {imported} listas de precio."})

            if "articulo_codigo" in headers and "lista_codigo" in headers:
                imported = _import_precios(rows)
                return render(request, "import_master_files.html", {"message": f"Se importaron {imported} precios."})

            if "articulo" in headers and "lista" in headers:
                imported = _import_precios(rows)
                return render(request, "import_master_files.html", {"message": f"Se importaron {imported} precios."})

            return render(request, "import_master_files.html", {"message": "El archivo no tiene la estructura esperada."})
    return render(request, "import_master_files.html")


def buscar_articulos(request):
    q = request.GET.get("q", "")
    articulos = list(_buscar_articulos(q))
    return render(request, "buscar_articulos.html", {"articulos": articulos, "q": q})


def _get_precio_articulo(cliente, articulo):
    if not cliente or not articulo:
        return Decimal("0")
    lista = ListaPrecio.objects.filter(codigo=cliente.codigo_lista_precio).first()
    if not lista:
        lista = ListaPrecio.objects.filter(codigo=cliente.codigo_lista_precio.zfill(2)).first()
    if not lista:
        return Decimal("0")
    precio_obj = PrecioArticulo.objects.filter(articulo=articulo, lista=lista).first()
    return precio_obj.precio if precio_obj else Decimal("0")


def crear_pedido(request):
    today = datetime.now().date().isoformat()
    draft = request.session.get("pedido_draft")
    if draft:
        draft = _deserialize_draft_from_session(draft)
    if not draft:
        draft = {
            "fecha": today,
            "cliente_codigo": "",
            "vendedor_codigo": "",
            "items": [],
            "pending_item": None,
            "show_item_form": False,
            "message": "",
            "error": "",
            "cliente_busqueda": "",
            "cliente_results": [],
        }

    cliente = None
    if draft.get("cliente_codigo"):
        cliente = Cliente.objects.filter(codigo=draft["cliente_codigo"]).first()

    clientes_sugeridos = [
        {
            "codigo": cliente.codigo,
            "razon_social": cliente.razon_social,
            "nombre_fantasia": cliente.nombre_fantasia or "",
            "label": f"{cliente.codigo} - {cliente.razon_social}" if cliente.nombre_fantasia else f"{cliente.codigo} - {cliente.razon_social}",
        }
        for cliente in Cliente.objects.order_by("razon_social", "nombre_fantasia", "codigo")[:100]
    ]
    articulos_sugeridos = [
        {
            "codigo": articulo.codigo,
            "descripcion": articulo.descripcion,
            "label": f"{articulo.codigo} - {articulo.descripcion}",
        }
        for articulo in Articulo.objects.order_by("descripcion", "codigo")[:100]
    ]

    items_display = []
    total_pedido = Decimal("0")
    for item in draft.get("items", []):
        preview_item = {
            "codigo": item.get("codigo", ""),
            "descripcion": item.get("descripcion", ""),
            "stock": item.get("stock", Decimal("0")) if isinstance(item.get("stock", Decimal("0")), Decimal) else Decimal(str(item.get("stock", "0"))),
            "cantidad": item.get("cantidad", Decimal("0")) if isinstance(item.get("cantidad", Decimal("0")), Decimal) else Decimal(str(item.get("cantidad", "0"))),
            "precio": item.get("precio", Decimal("0")) if isinstance(item.get("precio", Decimal("0")), Decimal) else Decimal(str(item.get("precio", "0"))),
            "subtotal": item.get("subtotal", Decimal("0")) if isinstance(item.get("subtotal", Decimal("0")), Decimal) else Decimal(str(item.get("subtotal", "0"))),
        }
        items_display.append(preview_item)
        total_pedido += preview_item["subtotal"]

    pending_item = None
    if draft.get("pending_item"):
        pending_item = {
            "codigo": draft["pending_item"].get("codigo", ""),
            "descripcion": draft["pending_item"].get("descripcion", ""),
            "stock": draft["pending_item"].get("stock", Decimal("0")) if isinstance(draft["pending_item"].get("stock", Decimal("0")), Decimal) else Decimal(str(draft["pending_item"].get("stock", "0"))),
            "cantidad": draft["pending_item"].get("cantidad", Decimal("0")) if isinstance(draft["pending_item"].get("cantidad", Decimal("0")), Decimal) else Decimal(str(draft["pending_item"].get("cantidad", "0"))),
            "precio": draft["pending_item"].get("precio", Decimal("0")) if isinstance(draft["pending_item"].get("precio", Decimal("0")), Decimal) else Decimal(str(draft["pending_item"].get("precio", "0"))),
            "subtotal": draft["pending_item"].get("subtotal", Decimal("0")) if isinstance(draft["pending_item"].get("subtotal", Decimal("0")), Decimal) else Decimal(str(draft["pending_item"].get("subtotal", "0"))),
        }

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "crear_cabecera":
            fecha = request.POST.get("fecha", today).strip() or today
            cliente_busqueda = request.POST.get("cliente_busqueda", "").strip()
            draft["cliente_busqueda"] = cliente_busqueda
            draft["cliente_results"] = []
            if not cliente_busqueda:
                draft["error"] = "Ingresá el cliente por código, razón social o nombre de fantasía."
                draft["message"] = ""
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            clientes = list(_buscar_clientes(cliente_busqueda))
            if not clientes:
                draft["error"] = "No se encontró ningún cliente con ese criterio."
                draft["message"] = ""
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            if len(clientes) == 1:
                cliente = clientes[0]
                draft = {
                    "fecha": fecha,
                    "cliente_codigo": cliente.codigo,
                    "vendedor_codigo": cliente.codigo_vendedor or "",
                    "items": [],
                    "pending_item": None,
                    "show_item_form": False,
                    "message": "Cabecera confirmada. Ahora podés agregar ítems.",
                    "error": "",
                    "cliente_busqueda": cliente_busqueda,
                    "cliente_results": [],
                }
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            draft["cliente_results"] = [
                {
                    "codigo": cliente.codigo,
                    "razon_social": cliente.razon_social,
                    "nombre_fantasia": cliente.nombre_fantasia or "-",
                }
                for cliente in clientes
            ]
            draft["message"] = "Encontramos varios clientes. Seleccioná uno para continuar."
            draft["error"] = ""
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "seleccionar_cliente":
            fecha = draft.get("fecha", today)
            cliente_codigo = request.POST.get("cliente_codigo", "").strip()
            cliente = _resolver_cliente(cliente_codigo)
            if not cliente:
                draft["error"] = "No se pudo seleccionar el cliente."
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            draft = {
                "fecha": fecha,
                "cliente_codigo": cliente.codigo,
                "vendedor_codigo": cliente.codigo_vendedor or "",
                "items": [],
                "pending_item": None,
                "show_item_form": False,
                "message": "Cabecera confirmada. Ahora podés agregar ítems.",
                "error": "",
                "cliente_busqueda": draft.get("cliente_busqueda", ""),
                "cliente_results": [],
            }
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "nuevo_item":
            draft["show_item_form"] = True
            draft["message"] = "Ingresá la cantidad y el artículo."
            draft["error"] = ""
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "buscar_articulos_ajax":
            query = request.POST.get("q", "").strip()
            articulos = list(_buscar_articulos(query))
            payload = [{"codigo": articulo.codigo, "descripcion": articulo.descripcion, "label": f"{articulo.codigo} - {articulo.descripcion}"} for articulo in articulos]
            return JsonResponse(payload, safe=False)

        if action == "preview_item":
            if not draft.get("cliente_codigo"):
                draft["error"] = "Primero confirmá la cabecera del pedido."
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            cantidad = request.POST.get("cantidad", "1").strip()
            codigo_articulo = request.POST.get("codigo_articulo", "").strip()
            articulo = _resolver_articulo(codigo_articulo)
            if not articulo:
                draft["error"] = f"No se encontró un artículo para: {codigo_articulo}."
                draft["show_item_form"] = True
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            cliente = Cliente.objects.filter(codigo=draft["cliente_codigo"]).first()
            preview = _build_item_preview(cliente, articulo, cantidad)
            draft["pending_item"] = {
                "codigo": preview["codigo"],
                "descripcion": preview["descripcion"],
                "stock": preview["stock"],
                "cantidad": preview["cantidad"],
                "precio": preview["precio"],
                "subtotal": preview["subtotal"],
            }
            draft["show_item_form"] = False
            draft["message"] = "Revisá el detalle del ítem antes de agregarlo."
            draft["error"] = ""
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "agregar_item":
            if draft.get("pending_item"):
                draft["items"].append(draft["pending_item"])
                draft["pending_item"] = None
                draft["show_item_form"] = False
                draft["message"] = "Ítem agregado al pedido."
                draft["error"] = ""
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            draft["error"] = "No hay un ítem para agregar."
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "cancelar_item":
            draft["pending_item"] = None
            draft["show_item_form"] = True
            draft["message"] = "Se canceló la carga del ítem."
            draft["error"] = ""
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "eliminar_item":
            item_index = request.POST.get("item_index", "")
            try:
                index = int(item_index)
            except ValueError:
                index = -1
            if 0 <= index < len(draft.get("items", [])):
                del draft["items"][index]
                draft["message"] = "Ítem eliminado del pedido."
                draft["error"] = ""
            else:
                draft["message"] = ""
                draft["error"] = "No se pudo eliminar el ítem."
            request.session["pedido_draft"] = _serialize_draft_for_session(draft)
            return redirect("crear_pedido")

        if action == "cancelar_pedido":
            request.session.pop("pedido_draft", None)
            return redirect("crear_pedido")

        if action == "cerrar_pedido":
            if not draft.get("items"):
                draft["error"] = "El pedido no tiene ítems cargados."
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            cliente = Cliente.objects.filter(codigo=draft["cliente_codigo"]).first()
            vendedor_codigo = draft.get("vendedor_codigo", "")
            if not cliente or not vendedor_codigo.isdigit():
                draft["error"] = "La cabecera del pedido no tiene un vendedor válido."
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            total = Decimal("0")
            detalles = []
            for item in draft.get("items", []):
                articulo = Articulo.objects.filter(codigo=item.get("codigo", "")).first()
                if not articulo:
                    continue
                cantidad_dec = Decimal(item.get("cantidad", "0"))
                precio = _get_precio_articulo(cliente, articulo)
                subtotal = cantidad_dec * precio
                total += subtotal
                detalles.append((articulo, cantidad_dec, precio, subtotal))

            if not detalles:
                draft["error"] = "No se pudieron procesar los ítems del pedido."
                request.session["pedido_draft"] = _serialize_draft_for_session(draft)
                return redirect("crear_pedido")

            max_id = Pedido.objects.filter(vendedor_codigo=vendedor_codigo).order_by('-id_pedido').values_list('id_pedido', flat=True).first()
            if max_id and max_id.isdigit():
                next_num = (int(max_id) // 10000) + 1
            else:
                next_num = 1
            pedido_id = str(next_num * 10000 + int(vendedor_codigo))
            pedido = Pedido.objects.create(
                id_pedido=pedido_id,
                vendedor_codigo=vendedor_codigo,
                cliente=cliente,
                fecha=datetime.now().date(),
                estado="pendiente",
                total=total,
            )
            for articulo, cantidad_dec, precio, subtotal in detalles:
                DetallePedido.objects.create(
                    pedido=pedido,
                    articulo=articulo,
                    cantidad=cantidad_dec,
                    precio=precio,
                    subtotal=subtotal,
                )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            vendor_dir = BASE_DIR / "pedidos" / f"ven{vendedor_codigo}" / "pendientes"
            vendor_dir.mkdir(parents=True, exist_ok=True)

            header_path = vendor_dir / f"encabezado_ven{vendedor_codigo}_{timestamp}.csv"
            detail_path = vendor_dir / f"detallePedido_ven{vendedor_codigo}_{timestamp}.csv"

            with header_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id_pedido", "vendedor_codigo", "cliente_codigo", "fecha", "estado", "total"])
                writer.writeheader()
                writer.writerow({
                    "id_pedido": pedido.id_pedido,
                    "vendedor_codigo": pedido.vendedor_codigo,
                    "cliente_codigo": pedido.cliente.codigo,
                    "fecha": pedido.fecha,
                    "estado": pedido.estado,
                    "total": pedido.total,
                })

            with detail_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id_pedido", "codigo_articulo", "cantidad", "precio", "subtotal"])
                writer.writeheader()
                for detalle in pedido.detalles.all():
                    writer.writerow({
                        "id_pedido": pedido.id_pedido,
                        "codigo_articulo": detalle.articulo.codigo,
                        "cantidad": detalle.cantidad,
                        "precio": detalle.precio,
                        "subtotal": detalle.subtotal,
                    })

            request.session.pop("pedido_draft", None)
            return redirect("pedidos")

    return render(request, "crear_pedido.html", {
        "draft": draft,
        "cliente": cliente,
        "items": items_display,
        "total_pedido": total_pedido,
        "pending_item": pending_item,
        "clientes_sugeridos": clientes_sugeridos,
        "articulos_sugeridos": articulos_sugeridos,
    })


def pedidos(request):
    pedidos = Pedido.objects.all().order_by("-id")
    return render(request, "pedidos.html", {"pedidos": pedidos})


def detalle_pedido(request, pedido_id):
    pedido = Pedido.objects.filter(id_pedido=pedido_id).first()
    if not pedido:
        return render(request, "detalle_pedido.html", {"error": "Pedido no encontrado"})
    return render(request, "detalle_pedido.html", {"pedido": pedido})


def clientes(request):
    q = request.GET.get("q", "")
    if q:
        lista = Cliente.objects.filter(
            Q(codigo__icontains=q) |
            Q(razon_social__icontains=q) |
            Q(nombre_fantasia__icontains=q)
        ).order_by("razon_social")
    else:
        lista = Cliente.objects.all().order_by("razon_social")
    return render(request, "clientes.html", {"clientes": lista, "q": q})


def articulos(request):
    q = request.GET.get("q", "")
    if q:
        lista = Articulo.objects.filter(
            Q(codigo__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(rubro__icontains=q) |
            Q(marca__icontains=q)
        ).order_by("descripcion")
    else:
        lista = Articulo.objects.all().order_by("descripcion")
    return render(request, "articulos.html", {"articulos": lista, "q": q})


def pedido_offline(request):
    from django.http import FileResponse
    return FileResponse(open(BASE_DIR / 'pedidos_web' / 'static' / 'pedido_offline.html', 'rb'), content_type='text/html')


def exportar_pedidos(request):
    if request.method == "POST":
        pedidos = Pedido.objects.all().order_by("id")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        vendors = sorted({pedido.vendedor_codigo for pedido in pedidos})
        for vendor_code in vendors:
            vendor_dir = BASE_DIR / "pedidos" / f"ven{vendor_code}" / "pendientes"
            vendor_dir.mkdir(parents=True, exist_ok=True)

            header_path = vendor_dir / f"encabezado_ven{vendor_code}_{timestamp}.csv"
            detail_path = vendor_dir / f"detallePedido_ven{vendor_code}_{timestamp}.csv"

            with header_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id_pedido", "vendedor_codigo", "cliente_codigo", "fecha", "estado", "total"])
                writer.writeheader()
                for pedido in pedidos.filter(vendedor_codigo=vendor_code):
                    writer.writerow({
                        "id_pedido": pedido.id_pedido,
                        "vendedor_codigo": pedido.vendedor_codigo,
                        "cliente_codigo": pedido.cliente.codigo,
                        "fecha": pedido.fecha,
                        "estado": pedido.estado,
                        "total": pedido.total,
                    })

            with detail_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id_pedido", "codigo_articulo", "cantidad", "precio", "subtotal"])
                writer.writeheader()
                for pedido in pedidos.filter(vendedor_codigo=vendor_code):
                    for detalle in pedido.detalles.all():
                        writer.writerow({
                            "id_pedido": pedido.id_pedido,
                            "codigo_articulo": detalle.articulo.codigo,
                            "cantidad": detalle.cantidad,
                            "precio": detalle.precio,
                            "subtotal": detalle.subtotal,
                        })

        return redirect("pedidos")

    return render(request, "exportar_pedidos.html")


def api_data(request):
    articulos = list(Articulo.objects.values('codigo', 'descripcion', 'rubro', 'marca', 'iva', 'stock'))
    clientes = list(Cliente.objects.values(
        'codigo', 'razon_social', 'nombre_fantasia', 'direccion',
        'localidad', 'provincia', 'cat_iva', 'cuit', 'codigo_vendedor', 'codigo_lista_precio'
    ))
    listas = list(ListaPrecio.objects.values('codigo', 'nombre'))
    precios = list(PrecioArticulo.objects.select_related('articulo', 'lista').values(
        'articulo__codigo', 'lista__codigo', 'precio'
    ))
    precios_fixed = [{'articulo_codigo': p['articulo__codigo'], 'lista_codigo': p['lista__codigo'], 'precio': p['precio']} for p in precios]
    return JsonResponse({
        'articulos': articulos,
        'clientes': clientes,
        'listas_precio': listas,
        'precios': precios_fixed,
    })


@csrf_exempt
def api_sync(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)

    pedidos_data = data.get('pedidos', [])
    synced = 0

    for pedido_info in pedidos_data:
        cliente_codigo = pedido_info.get('cliente_codigo', '')
        vendedor_codigo = pedido_info.get('vendedor_codigo', '')
        items = pedido_info.get('items', [])

        if not cliente_codigo or not items:
            continue

        cliente = Cliente.objects.filter(codigo=cliente_codigo).first()
        if not cliente:
            continue

        max_id = Pedido.objects.filter(vendedor_codigo=vendedor_codigo).order_by('-id_pedido').values_list('id_pedido', flat=True).first()
        if max_id and str(max_id).isdigit():
            next_num = (int(max_id) // 10000) + 1
        else:
            next_num = 1
        pedido_id = str(next_num * 10000 + int(vendedor_codigo))

        total = Decimal('0')
        pedido = Pedido.objects.create(
            id_pedido=pedido_id,
            vendedor_codigo=vendedor_codigo,
            cliente=cliente,
            fecha=datetime.now().date(),
            estado='pendiente',
            total=0,
        )

        for item in items:
            articulo = Articulo.objects.filter(codigo=item.get('codigo', '')).first()
            if not articulo:
                continue
            cantidad = Decimal(str(item.get('cantidad', 0)))
            precio = _get_precio_articulo(cliente, articulo)
            subtotal = cantidad * precio
            total += subtotal
            DetallePedido.objects.create(
                pedido=pedido,
                articulo=articulo,
                cantidad=cantidad,
                precio=precio,
                subtotal=subtotal,
            )

        pedido.total = total
        pedido.save()
        synced += 1

    return JsonResponse({'ok': True, 'synced': synced})
