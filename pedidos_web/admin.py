from django.contrib import admin
from .models import Articulo, Cliente, ListaPrecio, PrecioArticulo, Pedido, DetallePedido, Vendedor


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre")
    search_fields = ("codigo", "nombre")


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "rubro", "marca", "stock")
    search_fields = ("codigo", "descripcion", "rubro", "marca")
    list_filter = ("rubro", "marca")


@admin.register(PrecioArticulo)
class PrecioArticuloAdmin(admin.ModelAdmin):
    list_display = ("articulo", "lista", "precio")
    search_fields = ("articulo__codigo", "articulo__descripcion", "lista__codigo")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("codigo", "razon_social", "nombre_fantasia", "codigo_vendedor", "codigo_lista_precio")
    search_fields = ("codigo", "razon_social", "nombre_fantasia")
    list_filter = ("codigo_vendedor", "codigo_lista_precio")


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id_pedido", "vendedor_codigo", "cliente", "fecha", "estado", "total")
    search_fields = ("id_pedido", "vendedor_codigo", "cliente__codigo", "cliente__razon_social")
    list_filter = ("estado", "fecha")


@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ("pedido", "articulo", "cantidad", "precio", "subtotal")
    search_fields = ("pedido__id_pedido", "articulo__codigo", "articulo__descripcion")
