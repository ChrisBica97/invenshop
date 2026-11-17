"""App core: página de inicio y panel de gestión (dashboard del personal)."""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum
from django.views.generic import TemplateView

from catalogo.models import Categoria, Producto
from pedidos.models import Pedido


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["destacados"] = Producto.objects.activos().con_categoria().filter(stock__gt=0).order_by("-creado")[:4]
        ctx["categorias"] = Categoria.objects.annotate(total=Count("productos")).filter(total__gt=0)
        return ctx


class PanelView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Panel de gestión: solo Administrador y Empleado.
    UserPassesTestMixin -> un Cliente logueado recibe 403; un anónimo va al login.
    """
    template_name = "core/panel.html"

    def test_func(self):
        return self.request.user.es_personal

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Un solo query agrupado (GROUP BY estado) -> lista [(valor, etiqueta, cantidad)]
        conteo = dict(Pedido.objects.values_list("estado").annotate(n=Count("id")).order_by())
        ctx["resumen_estados"] = [(v, e, conteo.get(v, 0)) for v, e in Pedido.Estado.choices]
        ctx["productos_total"] = Producto.objects.count()
        ctx["productos_agotados"] = Producto.objects.activos().filter(stock=0).count()
        ctx["stock_bajo"] = Producto.objects.activos().con_categoria().filter(stock__lte=5).order_by("stock")[:5]
        ctx["ultimos_pedidos"] = Pedido.objects.select_related("usuario")[:5]
        ctx["facturado"] = (
            Pedido.objects.filter(estado__in=[Pedido.Estado.PAGADO, Pedido.Estado.ENVIADO])
            .aggregate(s=Sum("total"))["s"] or 0
        )
        return ctx
