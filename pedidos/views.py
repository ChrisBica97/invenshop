"""
Vistas de pedidos: carrito (5.2), checkout (5.3), historial, gestión y reportes.

Se combinan los dos estilos de control de acceso que pide la consigna 5.1:
  * Vistas de FUNCIÓN  -> @login_required y @permission_required
  * Vistas de CLASE    -> LoginRequiredMixin y PermissionRequiredMixin
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import IntegrityError
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, FormView, ListView

from catalogo.models import Producto

from .carrito import Carrito, StockInsuficiente
from .forms import CambiarEstadoForm, ConfirmarPedidoForm, DatosEnvioForm
from .models import DetallePedido, Pedido
from .servicios import crear_pedido

SESION_ENVIO = "checkout_envio"


def _cantidad_post(request, defecto=1):
    """Lee 'cantidad' del POST de forma segura (si viene basura, usa el defecto)."""
    try:
        return int(request.POST.get("cantidad", defecto))
    except (TypeError, ValueError):
        return defecto


# ===========================================================================
# CARRITO (vistas de función). Las que modifican usan @require_POST: así
# siempre pasan por la protección CSRF y no se ejecutan con un simple link.
# ===========================================================================
def carrito_detalle(request):
    carrito = Carrito(request)
    items = carrito.items()
    return render(request, "pedidos/carrito.html", {
        "items": items,
        "total": carrito.total(items),
        "hay_problemas_stock": any(i["supera_stock"] for i in items),
    })


@require_POST
def carrito_agregar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id, activo=True)
    try:
        Carrito(request).agregar(producto, _cantidad_post(request))
        messages.success(request, f"«{producto.nombre}» se agregó al carrito.")
    except (StockInsuficiente, ValueError) as e:
        messages.error(request, str(e))
    # Vuelve a la página desde donde se agregó (si es del propio sitio)
    siguiente = request.POST.get("next")
    if siguiente and siguiente.startswith("/") and not siguiente.startswith("//"):
        return redirect(siguiente)
    return redirect("pedidos:carrito")


@require_POST
def carrito_actualizar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    cantidad = _cantidad_post(request, 0)
    carrito = Carrito(request)
    if cantidad <= 0:
        carrito.quitar(producto_id)
        messages.info(request, f"Se quitó «{producto.nombre}» del carrito.")
    else:
        try:
            carrito.agregar(producto, cantidad, reemplazar=True)
            messages.success(request, "Cantidad actualizada.")
        except StockInsuficiente as e:
            messages.error(request, str(e))
    return redirect("pedidos:carrito")


@require_POST
def carrito_quitar(request, producto_id):
    Carrito(request).quitar(producto_id)
    messages.info(request, "Producto quitado del carrito.")
    return redirect("pedidos:carrito")


@require_POST
def carrito_vaciar(request):
    Carrito(request).vaciar()
    messages.info(request, "Vaciaste el carrito.")
    return redirect("pedidos:carrito")


# ===========================================================================
# CHECKOUT: 1) datos de envío -> 2) confirmación final -> se registra el pedido
# Solo para usuarios autenticados (LoginRequiredMixin).
# ===========================================================================
class CarritoNoVacioMixin:
    """Si el carrito está vacío (o tiene problemas de stock) vuelve al carrito."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.carrito = Carrito(request)
            self.items = self.carrito.items()
            if not self.items:
                messages.warning(request, "Tu carrito está vacío.")
                return redirect("catalogo:lista")
            if any(i["supera_stock"] for i in self.items):
                messages.error(request, "Algunos productos superan el stock disponible. Ajustá las cantidades.")
                return redirect("pedidos:carrito")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.items
        ctx["total"] = self.carrito.total(self.items)
        return ctx


@method_decorator(sensitive_post_parameters("telefono_contacto", "direccion"), name="dispatch")
class CheckoutView(LoginRequiredMixin, CarritoNoVacioMixin, FormView):
    form_class = DatosEnvioForm
    template_name = "pedidos/checkout.html"
    success_url = reverse_lazy("pedidos:confirmar")

    def get_initial(self):
        # Precarga los datos usados antes en esta sesión o el teléfono del perfil
        return self.request.session.get(SESION_ENVIO) or {"telefono_contacto": self.request.user.telefono}

    def form_valid(self, form):
        self.request.session[SESION_ENVIO] = form.cleaned_data  # se guarda hasta confirmar
        return super().form_valid(form)


class ConfirmarPedidoView(LoginRequiredMixin, CarritoNoVacioMixin, FormView):
    form_class = ConfirmarPedidoForm
    template_name = "pedidos/confirmar.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and SESION_ENVIO not in request.session:
            return redirect("pedidos:checkout")  # no se puede saltear el paso 1
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["envio"] = self.request.session.get(SESION_ENVIO)
        return ctx

    def form_valid(self, form):
        try:
            pedido = crear_pedido(self.request.user, self.carrito, self.request.session[SESION_ENVIO])
        except StockInsuficiente as e:
            messages.error(self.request, f"No se pudo registrar el pedido: {e}")
            return redirect("pedidos:carrito")
        except IntegrityError:
            # Última barrera: si dos compras chocan y el stock quedaría negativo, la base
            # lo rechaza (CHECK stock >= 0 de PositiveIntegerField) y transaction.atomic
            # deshace todo. En lugar de una página de error, se avisa como falta de stock.
            messages.error(
                self.request,
                "No se pudo registrar el pedido: otro cliente compró las últimas unidades. "
                "Revisá las cantidades de tu carrito.",
            )
            return redirect("pedidos:carrito")
        self.request.session.pop(SESION_ENVIO, None)
        messages.success(self.request, f"¡Gracias! Tu pedido {pedido.numero} fue registrado.")
        return redirect(pedido)


# ===========================================================================
# HISTORIAL (cliente) y DETALLE (dueño o personal autorizado)
# ===========================================================================
class MisPedidosListView(LoginRequiredMixin, ListView):
    template_name = "pedidos/mis_pedidos.html"
    context_object_name = "pedidos"
    paginate_by = 10

    def get_queryset(self):
        # Cada cliente ve SOLO sus pedidos. annotate calcula las unidades en la BD.
        return (
            Pedido.objects.filter(usuario=self.request.user)
            .annotate(unidades=Sum("detalles__cantidad"))
        )


class PedidoDetailView(LoginRequiredMixin, DetailView):
    template_name = "pedidos/pedido_detail.html"
    context_object_name = "pedido"

    def get_queryset(self):
        # select_related (FK hacia arriba) + prefetch_related (detalles hacia abajo)
        # -> 3 queries en total sin importar cuántos productos tenga el pedido.
        qs = Pedido.objects.select_related("usuario").prefetch_related("detalles__producto")
        if not self.request.user.has_perm("pedidos.ver_todos_pedidos"):
            qs = qs.filter(usuario=self.request.user)  # pedido ajeno -> 404
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.has_perm("pedidos.cambiar_estado_pedido") and self.object.estados_siguientes():
            ctx["form_estado"] = CambiarEstadoForm(pedido=self.object)
        return ctx


# ===========================================================================
# GESTIÓN DE PEDIDOS (Empleado / Administrador)
# ===========================================================================
class PedidoGestionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "pedidos.ver_todos_pedidos"
    template_name = "pedidos/gestion_pedidos.html"
    context_object_name = "pedidos"
    paginate_by = 15

    def get_queryset(self):
        qs = Pedido.objects.select_related("usuario").annotate(unidades=Sum("detalles__cantidad"))
        estado = self.request.GET.get("estado")
        if estado in Pedido.Estado.values:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get("q", "").strip().lstrip("#")
        if q:
            filtro = Q(usuario__email__icontains=q)
            if q.isdigit():
                filtro |= Q(pk=int(q))  # búsqueda por número de pedido
            qs = qs.filter(filtro)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Pedido.Estado.choices
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        return ctx


@login_required
@permission_required("pedidos.cambiar_estado_pedido", raise_exception=True)  # Cliente -> 403
@require_POST
def cambiar_estado_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = CambiarEstadoForm(request.POST, pedido=pedido)
    if form.is_valid():
        nuevo = form.cleaned_data["estado"]
        pedido.cambiar_estado(nuevo)
        extra = " Se repuso el stock de los productos." if nuevo == Pedido.Estado.CANCELADO else ""
        messages.success(request, f"El pedido {pedido.numero} pasó a «{nuevo}».{extra}")
    else:
        messages.error(request, "No se pudo cambiar el estado: transición no permitida.")
    return redirect(pedido)


@login_required
@permission_required("pedidos.ver_reportes", raise_exception=True)  # solo Administrador
def reportes(request):
    """Reportes de ventas calculados íntegramente con agregaciones del ORM."""
    vendidos = Pedido.objects.exclude(estado=Pedido.Estado.CANCELADO)
    contexto = {
        "por_estado": Pedido.objects.values("estado").annotate(cantidad=Count("id"), monto=Sum("total")).order_by("estado"),
        "facturado": vendidos.filter(estado__in=[Pedido.Estado.PAGADO, Pedido.Estado.ENVIADO]).aggregate(s=Sum("total"))["s"] or 0,
        "total_pedidos": Pedido.objects.count(),
        "mas_vendidos": (
            DetallePedido.objects.filter(pedido__in=vendidos)
            .values("producto__nombre").annotate(unidades=Sum("cantidad")).order_by("-unidades")[:5]
        ),
        "stock_bajo": Producto.objects.activos().con_categoria().filter(stock__lte=5).order_by("stock")[:10],
        "mejores_clientes": (
            vendidos.values("usuario__email").annotate(compras=Count("id"), monto=Sum("total")).order_by("-monto")[:5]
        ),
    }
    return render(request, "pedidos/reportes.html", contexto)
