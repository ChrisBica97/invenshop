"""Admin personalizado del catálogo (5.4)."""
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "slug", "cantidad_productos")
    search_fields = ("nombre",)
    prepopulated_fields = {"slug": ("nombre",)}

    def get_queryset(self, request):
        # annotate: el conteo se hace en la BD, no un query por fila
        return super().get_queryset(request).annotate(_total=Count("productos"))

    @admin.display(description="productos", ordering="_total")
    def cantidad_productos(self, obj):
        return obj._total


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("miniatura", "nombre", "categoria", "precio", "stock", "activo", "estado_stock")
    list_display_links = ("miniatura", "nombre")
    list_editable = ("stock", "activo")                      # edición rápida desde el listado
    list_filter = ("categoria", "activo", ("creado", admin.DateFieldListFilter))
    search_fields = ("nombre", "descripcion")                # búsqueda por nombre
    list_select_related = ("categoria",)                     # evita N+1 en el listado
    list_per_page = 25
    readonly_fields = ("creado", "actualizado")
    fieldsets = (
        (None, {"fields": ("nombre", "categoria", "descripcion", "imagen", "imagen_credito", "imagen_fuente")}),
        ("Venta e inventario", {"fields": ("precio", "stock", "activo")}),
        ("Auditoría", {"fields": ("creado", "actualizado"), "classes": ("collapse",)}),
    )
    actions = ["activar", "desactivar"]

    @admin.display(description="")
    def miniatura(self, obj):
        if obj.imagen_disponible:
            return format_html('<img src="{}" style="height:40px;border-radius:4px">', obj.imagen.url)
        return "—"

    @admin.display(description="estado")
    def estado_stock(self, obj):
        if obj.agotado:
            return format_html('<b style="color:#c00">{}</b>', "Agotado")
        if obj.stock_bajo:
            return format_html('<b style="color:#c80">{}</b>', "Stock bajo")
        return "OK"

    @admin.action(description="Activar productos seleccionados")
    def activar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=True)} producto(s) activados.")

    @admin.action(description="Desactivar productos seleccionados")
    def desactivar(self, request, queryset):
        self.message_user(request, f"{queryset.update(activo=False)} producto(s) desactivados.")
