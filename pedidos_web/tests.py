from decimal import Decimal
from django.test import TestCase

from .models import Articulo, Cliente, ListaPrecio, PrecioArticulo
from .views import _build_draft_header, _build_item_preview, _buscar_clientes, _buscar_articulos, _resolver_articulo, _resolver_cliente, _serialize_draft_for_session


class PedidoFlowTests(TestCase):
    def setUp(self):
        self.lista = ListaPrecio.objects.create(codigo="LP01", nombre="Lista General")
        self.articulo = Articulo.objects.create(
            codigo="A001",
            descripcion="Arroz 1kg",
            stock=100,
            iva=21,
        )
        PrecioArticulo.objects.create(articulo=self.articulo, lista=self.lista, precio=1250)
        self.cliente = Cliente.objects.create(
            codigo="C001",
            razon_social="Cliente Demo",
            codigo_vendedor="7",
            codigo_lista_precio="LP01",
        )

    def test_draft_header_uses_cliente_vendedor(self):
        header = _build_draft_header(self.cliente, "2026-07-17")

        self.assertEqual(header["cliente_codigo"], "C001")
        self.assertEqual(header["vendedor_codigo"], "7")
        self.assertEqual(header["fecha"], "2026-07-17")

    def test_item_preview_uses_client_price_list(self):
        preview = _build_item_preview(self.cliente, self.articulo)

        self.assertEqual(preview["descripcion"], "Arroz 1kg")
        self.assertEqual(preview["stock"], Decimal("100"))
        self.assertEqual(preview["precio"], Decimal("1250"))

    def test_client_lookup_returns_closest_matches_first(self):
        cliente_extra = Cliente.objects.create(codigo="C002", razon_social="Otra empresa", nombre_fantasia="La otra")

        matches = _buscar_clientes("c")

        self.assertEqual(matches[0].codigo, "C001")
        self.assertIn(cliente_extra, matches)

    def test_article_lookup_returns_closest_matches_first(self):
        matches = _buscar_articulos("a0")

        self.assertEqual(matches[0].codigo, "A001")

    def test_resolver_articulo_uses_partial_description(self):
        articulo = _resolver_articulo("arroz")

        self.assertEqual(articulo.codigo, "A001")

    def test_resolver_cliente_accepts_code_with_label(self):
        cliente = _resolver_cliente("C001 - Cliente Demo")

        self.assertEqual(cliente.codigo, "C001")

    def test_serialize_draft_for_session_converts_decimals(self):
        draft = {
            "items": [
                {
                    "cantidad": Decimal("2"),
                    "precio": Decimal("1250"),
                    "subtotal": Decimal("2500"),
                }
            ],
            "pending_item": {
                "precio": Decimal("1250"),
            },
        }

        serialized = _serialize_draft_for_session(draft)

        self.assertEqual(serialized["items"][0]["cantidad"], "2")
        self.assertEqual(serialized["items"][0]["precio"], "1250")
        self.assertEqual(serialized["items"][0]["subtotal"], "2500")
        self.assertEqual(serialized["pending_item"]["precio"], "1250")
