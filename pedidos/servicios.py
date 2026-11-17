"""
Lógica de negocio para registrar un pedido de forma SEGURA (5.3 / objetivo 5).

Todo ocurre dentro de transaction.atomic(): si algo falla (por ejemplo, otro
cliente compró la última unidad un segundo antes), NO queda nada a medias:
ni pedido sin detalles, ni stock descontado de más.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from catalogo.models import Producto

from .carrito import StockInsuficiente
from .models import DetallePedido, Pedido


@transaction.atomic
def crear_pedido(usuario, carrito, datos_envio):
    items = carrito.items()
    if not items:
        raise StockInsuficiente("El carrito está vacío.")

    # select_for_update bloquea las filas de esos productos hasta el fin de la
    # transacción (en PostgreSQL), evitando vender dos veces la última unidad.
    ids = [i["producto"].pk for i in items]
    productos = Producto.objects.select_for_update().filter(pk__in=ids).in_bulk()

    # 1) Revalidar stock con los datos frescos de la base
    for item in items:
        p = productos.get(item["producto"].pk)
        if p is None or not p.activo:
            raise StockInsuficiente(f"«{item['producto'].nombre}» ya no está disponible.")
        if item["cantidad"] > p.stock:
            raise StockInsuficiente(f"Stock insuficiente para «{p.nombre}» (disponible: {p.stock}).")

    # 2) Crear el pedido y sus detalles con el precio ACTUAL de la BD
    pedido = Pedido.objects.create(usuario=usuario, **datos_envio)
    detalles, total = [], Decimal("0")
    for item in items:
        p = productos[item["producto"].pk]
        detalles.append(DetallePedido(pedido=pedido, producto=p, cantidad=item["cantidad"], precio_unitario=p.precio))
        total += p.precio * item["cantidad"]
    DetallePedido.objects.bulk_create(detalles)  # un único INSERT para todos los detalles

    # 3) Descontar stock (F() = resta en la BD, sin leer/escribir en Python)
    for item in items:
        Producto.objects.filter(pk=item["producto"].pk).update(stock=F("stock") - item["cantidad"])

    pedido.total = total
    pedido.save(update_fields=["total"])

    # 4) El carrito se vacía al confirmar el pedido
    carrito.vaciar()
    return pedido
