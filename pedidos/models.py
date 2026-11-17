"""App pedidos - Pedido y DetallePedido, con la máquina de estados (5.3)."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.urls import reverse


class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        PAGADO = "Pagado", "Pagado"
        ENVIADO = "Enviado", "Enviado"
        CANCELADO = "Cancelado", "Cancelado"

    # Transiciones permitidas: Pendiente -> Pagado -> Enviado, y Cancelado
    # desde Pendiente o Pagado. Enviado y Cancelado son estados finales.
    TRANSICIONES = {
        Estado.PENDIENTE: [Estado.PAGADO, Estado.CANCELADO],
        Estado.PAGADO: [Estado.ENVIADO, Estado.CANCELADO],
        Estado.ENVIADO: [],
        Estado.CANCELADO: [],
    }

    # PROTECT: no se puede borrar un usuario con pedidos (se conserva el historial)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos", verbose_name="usuario"
    )
    fecha_creacion = models.DateTimeField("fecha de creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("última actualización", auto_now=True)
    estado = models.CharField("estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)

    # Datos de envío (pedidos en el checkout)
    direccion = models.CharField("dirección", max_length=150)
    ciudad = models.CharField("ciudad", max_length=80)
    codigo_postal = models.CharField("código postal", max_length=8)
    telefono_contacto = models.CharField("teléfono de contacto", max_length=20)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-fecha_creacion"]
        indexes = [models.Index(fields=["usuario", "-fecha_creacion"]), models.Index(fields=["estado"])]
        # Permisos personalizados (se asignan a los grupos en usuarios/roles.py)
        permissions = [
            ("cambiar_estado_pedido", "Puede cambiar el estado de un pedido"),
            ("ver_todos_pedidos", "Puede ver los pedidos de todos los clientes"),
            ("ver_reportes", "Puede ver los reportes de ventas"),
        ]

    def __str__(self):
        return f"Pedido {self.numero}"

    @property
    def numero(self):
        return f"#{self.pk:05d}" if self.pk else "#-----"

    def get_absolute_url(self):
        return reverse("pedidos:detalle", kwargs={"pk": self.pk})

    def estados_siguientes(self):
        return self.TRANSICIONES[self.estado]

    def puede_cambiar_a(self, nuevo_estado):
        return nuevo_estado in self.TRANSICIONES[self.estado]

    @transaction.atomic
    def cambiar_estado(self, nuevo_estado):
        """
        Cambia el estado validando la transición. Si se CANCELA, repone el
        stock descontado al confirmar el pedido (todo dentro de una transacción).
        """
        if not self.puede_cambiar_a(nuevo_estado):
            raise ValueError(f"No se puede pasar de {self.estado} a {nuevo_estado}.")
        if nuevo_estado == self.Estado.CANCELADO:
            from catalogo.models import Producto  # import local: evita importación circular

            for detalle in self.detalles.all():
                # F() hace la suma en la base de datos: evita condiciones de carrera
                Producto.objects.filter(pk=detalle.producto_id).update(
                    stock=F("stock") + detalle.cantidad
                )
        self.estado = nuevo_estado
        self.save(update_fields=["estado", "fecha_actualizacion"])


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="detalles")
    # PROTECT: un producto vendido no se puede borrar (se desactiva)
    producto = models.ForeignKey("catalogo.Producto", on_delete=models.PROTECT, related_name="detalles_pedido")
    cantidad = models.PositiveIntegerField("cantidad", validators=[MinValueValidator(1)])
    # Se guarda el precio del momento de la compra: si después cambia el precio
    # del producto, el historial del pedido NO se altera.
    precio_unitario = models.DecimalField("precio unitario", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "detalle de pedido"
        verbose_name_plural = "detalles de pedido"
        constraints = [
            models.UniqueConstraint(fields=["pedido", "producto"], name="producto_unico_por_pedido"),
        ]

    def __str__(self):
        return f"{self.cantidad} x {self.producto}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
