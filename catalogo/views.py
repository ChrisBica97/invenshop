"""
Vistas del catálogo.

PÚBLICAS (5.2):  ProductoListView y ProductoDetailView.
GESTIÓN (5.1):   CRUD de productos y categorías protegido con
                 LoginRequiredMixin + PermissionRequiredMixin.
                 - Anónimo           -> redirige al login.
                 - Logueado sin permiso (Cliente) -> 403 Prohibido.
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import AgregarAlCarritoForm, CategoriaForm, FiltroCatalogoForm, ProductoForm
from .models import Categoria, Producto


# ===========================================================================
# CATÁLOGO PÚBLICO
# ===========================================================================
class ProductoListView(ListView):
    """
    Listado con: paginación de 12, filtro por categoría + búsqueda (combinables),
    solo productos activos, y orden por precio o nombre.
    """
    template_name = "catalogo/producto_list.html"
    context_object_name = "productos"
    paginate_by = 12

    def get_queryset(self):
        qs = Producto.objects.activos().con_categoria()  # 1 solo query (select_related)
        self.filtros = FiltroCatalogoForm(self.request.GET or None)
        self.categoria_actual = None

        if self.filtros.is_valid():
            datos = self.filtros.cleaned_data
            if datos["q"]:
                # Búsqueda en nombre O descripción (Q permite el OR)
                qs = qs.filter(Q(nombre__icontains=datos["q"]) | Q(descripcion__icontains=datos["q"]))
            if datos["categoria"]:
                qs = qs.filter(categoria__slug=datos["categoria"])
                self.categoria_actual = Categoria.objects.filter(slug=datos["categoria"]).first()
            if datos["orden"]:
                qs = qs.order_by(datos["orden"], "pk")
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Cantidad de productos activos por categoría calculada en la BD (annotate)
        ctx["categorias"] = Categoria.objects.annotate(
            total=Count("productos", filter=Q(productos__activo=True))
        ).filter(total__gt=0)
        ctx["filtros"] = self.filtros
        ctx["categoria_actual"] = self.categoria_actual
        ctx["ordenes"] = FiltroCatalogoForm.ORDENES
        return ctx


class ProductoDetailView(DetailView):
    template_name = "catalogo/producto_detail.html"
    context_object_name = "producto"

    def get_queryset(self):
        # Un producto inactivo devuelve 404 en el catálogo público
        return Producto.objects.activos().con_categoria()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form"] = AgregarAlCarritoForm(stock_maximo=self.object.stock)
        ctx["relacionados"] = (
            Producto.objects.activos().filter(categoria=self.object.categoria)
            .exclude(pk=self.object.pk)[:4]
        )
        return ctx


# ===========================================================================
# GESTIÓN (Administrador y Empleado)
# ===========================================================================
class GestionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Mixin base de las vistas internas: exige login + permiso del modelo."""


class ProductoGestionListView(GestionMixin, ListView):
    permission_required = "catalogo.view_producto"
    template_name = "catalogo/gestion/producto_list.html"
    context_object_name = "productos"
    paginate_by = 15

    def get_queryset(self):
        qs = Producto.objects.con_categoria().order_by("nombre")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(categoria__nombre__icontains=q))
        if self.request.GET.get("stock") == "bajo":
            qs = qs.filter(stock__lte=5)
        return qs


class ProductoCreateView(GestionMixin, SuccessMessageMixin, CreateView):
    permission_required = "catalogo.add_producto"
    model = Producto
    form_class = ProductoForm
    template_name = "catalogo/gestion/producto_form.html"
    success_url = reverse_lazy("catalogo:gestion_productos")
    success_message = "Producto «%(nombre)s» creado."


class ProductoUpdateView(GestionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "catalogo.change_producto"
    model = Producto
    form_class = ProductoForm
    template_name = "catalogo/gestion/producto_form.html"
    success_url = reverse_lazy("catalogo:gestion_productos")
    success_message = "Producto «%(nombre)s» actualizado."


class ProductoDeleteView(GestionMixin, DeleteView):
    permission_required = "catalogo.delete_producto"
    model = Producto
    template_name = "catalogo/gestion/confirmar_borrado.html"
    success_url = reverse_lazy("catalogo:gestion_productos")

    def form_valid(self, form):
        try:
            nombre = self.object.nombre
            self.object.delete()
            messages.success(self.request, f"Producto «{nombre}» eliminado.")
        except ProtectedError:
            # Tiene pedidos asociados: se conserva el historial y se desactiva
            self.object.activo = False
            self.object.save(update_fields=["activo"])
            messages.warning(
                self.request,
                f"«{self.object.nombre}» figura en pedidos, así que no se borró: se DESACTIVÓ.",
            )
        return redirect(self.success_url)


class CategoriaListView(GestionMixin, ListView):
    permission_required = "catalogo.view_categoria"
    template_name = "catalogo/gestion/categoria_list.html"
    context_object_name = "categorias"

    def get_queryset(self):
        return Categoria.objects.annotate(total=Count("productos"))


class CategoriaCreateView(GestionMixin, SuccessMessageMixin, CreateView):
    permission_required = "catalogo.add_categoria"
    model = Categoria
    form_class = CategoriaForm
    template_name = "catalogo/gestion/categoria_form.html"
    success_url = reverse_lazy("catalogo:gestion_categorias")
    success_message = "Categoría «%(nombre)s» creada."


class CategoriaUpdateView(GestionMixin, SuccessMessageMixin, UpdateView):
    permission_required = "catalogo.change_categoria"
    model = Categoria
    form_class = CategoriaForm
    template_name = "catalogo/gestion/categoria_form.html"
    success_url = reverse_lazy("catalogo:gestion_categorias")
    success_message = "Categoría «%(nombre)s» actualizada."


class CategoriaDeleteView(GestionMixin, DeleteView):
    permission_required = "catalogo.delete_categoria"
    model = Categoria
    template_name = "catalogo/gestion/confirmar_borrado.html"
    success_url = reverse_lazy("catalogo:gestion_categorias")

    def form_valid(self, form):
        try:
            nombre = self.object.nombre
            self.object.delete()
            messages.success(self.request, f"Categoría «{nombre}» eliminada.")
        except ProtectedError:
            messages.error(self.request, "No se puede eliminar: la categoría todavía tiene productos.")
        return redirect(self.success_url)
