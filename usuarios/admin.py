"""Admin del usuario personalizado (5.4: búsqueda por email, filtros por rol)."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, BaseUserCreationForm

from .models import Usuario


class UsuarioCreationAdminForm(BaseUserCreationForm):
    class Meta:
        model = Usuario
        fields = ("email", "nombre", "apellido", "telefono", "rol")


class UsuarioChangeAdminForm(UserChangeForm):
    class Meta:
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeAdminForm
    add_form = UsuarioCreationAdminForm

    list_display = ("email", "nombre", "apellido", "rol", "telefono", "is_active", "date_joined")
    list_filter = ("rol", "is_active", ("date_joined", admin.DateFieldListFilter))
    list_editable = ("rol", "is_active")
    search_fields = ("email", "nombre", "apellido")   # búsqueda rápida por email
    ordering = ("email",)
    readonly_fields = ("is_staff", "last_login", "date_joined")

    # El rol define los grupos/permisos automáticamente (ver Usuario.save),
    # por eso no se muestran "groups" ni "user_permissions" para evitar inconsistencias.
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "apellido", "telefono")}),
        ("Rol y acceso", {"fields": ("rol", "is_active", "is_staff", "is_superuser")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre", "apellido", "telefono", "rol", "password1", "password2"),
        }),
    )
    filter_horizontal = ()
