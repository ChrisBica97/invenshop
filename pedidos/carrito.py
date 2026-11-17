"""
Carrito de compras guardado en la SESIÓN (django.contrib.sessions) - 5.2.

No toca la base de datos hasta que se confirma el pedido.
Estructura guardada en request.session["carrito"]:
    {"<producto_id>": <cantidad>, ...}
Solo se guardan ids y cantidades (no precios): el precio se lee siempre de la
BD al mostrar el carrito, así no se puede manipular desde el navegador.
"""
from decimal import Decimal

from django.conf import settings

from catalogo.models import Producto


class StockInsuficiente(Exception):
    """La cantidad pedida supera el stock disponible."""


class Carrito:
    def __init__(self, request):
        self.session = request.session
        carrito = self.session.get(settings.CARRITO_SESSION_ID)
        if carrito is None:
            carrito = self.session[settings.CARRITO_SESSION_ID] = {}
        self.carrito = carrito

    # ------------------------------------------------------------------
    # Operaciones: agregar, modificar cantidad, quitar, vaciar
    # ------------------------------------------------------------------
    def agregar(self, producto, cantidad=1, reemplazar=False):
        """
        Suma `cantidad` al producto (o la reemplaza si reemplazar=True).
        Valida que el producto esté activo y que no se supere el stock.
        """
        if cantidad < 1:
            raise ValueError("La cantidad debe ser al menos 1.")
        if not producto.activo:
            raise StockInsuficiente(f"«{producto.nombre}» no está disponible.")
        if producto.agotado:
            raise StockInsuficiente(f"«{producto.nombre}» está agotado.")

        clave = str(producto.pk)  # la sesión se guarda en JSON: claves string
        nueva = cantidad if reemplazar else self.carrito.get(clave, 0) + cantidad
        if nueva > producto.stock:
            raise StockInsuficiente(
                f"Solo hay {producto.stock} unidad(es) de «{producto.nombre}» "
                f"(en tu carrito: {self.carrito.get(clave, 0)})."
            )
        self.carrito[clave] = nueva
        self._guardar()

    def quitar(self, producto_id):
        if self.carrito.pop(str(producto_id), None) is not None:
            self._guardar()

    def vaciar(self):
        self.session[settings.CARRITO_SESSION_ID] = {}
        self.carrito = self.session[settings.CARRITO_SESSION_ID]
        self._guardar()

    def _guardar(self):
        self.session.modified = True  # avisa a Django que debe persistir la sesión

    # ------------------------------------------------------------------
    # Lectura: items, subtotales y total
    # ------------------------------------------------------------------
    def items(self):
        """
        Devuelve una lista de dicts con producto, cantidad, precio y subtotal.
        Trae TODOS los productos en UN solo query (id__in) -> sin N+1.
        Si un producto se desactivó o se borró, se descarta del carrito.
        """
        ids = list(self.carrito.keys())
        productos = Producto.objects.con_categoria().filter(pk__in=ids, activo=True).in_bulk()
        resultado, invalidos = [], []
        for clave, cantidad in self.carrito.items():
            producto = productos.get(int(clave))
            if producto is None:
                invalidos.append(clave)
                continue
            resultado.append({
                "producto": producto,
                "cantidad": cantidad,
                "precio": producto.precio,
                "subtotal": producto.precio * cantidad,
                "supera_stock": cantidad > producto.stock,
            })
        for clave in invalidos:
            self.carrito.pop(clave, None)
        if invalidos:
            self._guardar()
        return resultado

    def total(self, items=None):
        items = self.items() if items is None else items
        return sum((i["subtotal"] for i in items), Decimal("0"))

    def __len__(self):
        """Cantidad total de unidades (para el contador del navbar)."""
        return sum(self.carrito.values())

    def esta_vacio(self):
        return not self.carrito
