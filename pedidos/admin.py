"""Admin de pedidos (5.4): búsqueda por número/email, filtros, inlines de solo lectura."""
from django.contrib import admin, messages

from .models import DetallePedido, Pedido


class DetallePedidoInline(admin.TabularInline):
    """Los detalles se ven DENTRO del pedido. Los datos históricos son de solo lectura."""
    model = DetallePedido
    extra = 0
    can_delete = False
    fields = ("producto", "cantidad", "precio_unitario", "subtotal")
    readonly_fields = ("producto", "cantidad", "precio_unitario", "subtotal")

    @admin.display(description="subtotal")
    def subtotal(self, obj):
        return f"$ {obj.subtotal:,.2f}" if obj.pk else "—"

    def has_add_permission(self, request, obj=None):
        return False  # no se agregan productos a un pedido ya registrado


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    inlines = [DetallePedidoInline]
    list_display = ("numero", "usuario", "fecha_creacion", "estado", "total", "ciudad")
    list_filter = ("estado", ("fecha_creacion", admin.DateFieldListFilter))  # rango de fechas
    date_hierarchy = "fecha_creacion"
    # "=id" busca por número exacto de pedido; usuario__email por email del cliente
    search_fields = ("=id", "usuario__email", "usuario__apellido")
    list_select_related = ("usuario",)
    readonly_fields = ("usuario", "fecha_creacion", "fecha_actualizacion", "total",
                       "direccion", "ciudad", "codigo_postal", "telefono_contacto")
    fieldsets = (
        ("Pedido", {"fields": ("usuario", "estado", "total", "fecha_creacion", "fecha_actualizacion")}),
        ("Envío", {"fields": ("direccion", "ciudad", "codigo_postal", "telefono_contacto")}),
    )

    @admin.display(description="número", ordering="id")
    def numero(self, obj):
        return obj.numero

    def has_add_permission(self, request):
        return False  # los pedidos solo se generan desde el checkout

    def save_model(self, request, obj, form, change):
        """Si cambia el estado, se valida la transición y se repone stock al cancelar."""
        if change and "estado" in form.changed_data:
            anterior = Pedido.objects.get(pk=obj.pk)
            nuevo = obj.estado
            if not anterior.puede_cambiar_a(nuevo):
                messages.error(request, f"Transición no permitida: {anterior.estado} → {nuevo}. No se guardó.")
                return
            anterior.cambiar_estado(nuevo)
            return
        super().save_model(request, obj, form, change)
