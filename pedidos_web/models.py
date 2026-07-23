from django.db import models


class Vendedor(models.Model):
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class ListaPrecio(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Articulo(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.CharField(max_length=200)
    rubro = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    iva = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class PrecioArticulo(models.Model):
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE)
    lista = models.ForeignKey(ListaPrecio, on_delete=models.CASCADE)
    precio = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("articulo", "lista")


class Cliente(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    razon_social = models.CharField(max_length=200)
    nombre_fantasia = models.CharField(max_length=200, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    localidad = models.CharField(max_length=100, blank=True)
    provincia = models.CharField(max_length=100, blank=True)
    cat_iva = models.CharField(max_length=20, blank=True)
    cuit = models.CharField(max_length=20, blank=True)
    codigo_vendedor = models.CharField(max_length=10, blank=True)
    codigo_lista_precio = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.razon_social


class Pedido(models.Model):
    id_pedido = models.CharField(max_length=20, unique=True)
    vendedor_codigo = models.CharField(max_length=10)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    fecha = models.DateField()
    fecha_hora_creacion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, default="pendiente")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    total_con_descuento = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    observaciones = models.CharField(max_length=200, blank=True)
    ubicacion = models.CharField(max_length=200, blank=True)


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    articulo = models.ForeignKey(Articulo, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
