"""
Vistas de usuarios (5.1): registro, login/logout, perfil, cambio de contraseña
y administración de roles (solo Administrador).
"""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView, ListView, UpdateView

from .forms import LoginForm, PerfilForm, RegistroForm, RolForm
from .models import Usuario


def url_inicio_segun_rol(user):
    """Clientes -> catálogo. Empleados y administradores -> panel de gestión."""
    return reverse("core:panel") if user.es_personal else reverse("catalogo:lista")


# sensitive_post_parameters: si ocurre un error, las contraseñas NO aparecen
# en los reportes/logs de error de Django.
@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")
class RegistroView(CreateView):
    form_class = RegistroForm
    template_name = "usuarios/registro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:  # un usuario logueado no necesita registrarse
            return redirect(url_inicio_segun_rol(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)  # inicia sesión automáticamente tras registrarse
        messages.success(self.request, f"¡Bienvenido/a, {user.nombre}! Tu cuenta fue creada.")
        return redirect("catalogo:lista")


class IngresarView(auth_views.LoginView):
    """LoginView de Django + redirección según el rol."""
    form_class = LoginForm
    template_name = "usuarios/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        # Si venía de una página protegida (?next=...), se respeta ese destino
        destino = self.get_redirect_url()
        return destino or url_inicio_segun_rol(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, f"Hola, {form.get_user().nombre}. Iniciaste sesión.")
        return super().form_valid(form)


class SalirView(auth_views.LogoutView):
    """Logout: solo por POST (protección CSRF de Django 5+)."""

    def post(self, request, *args, **kwargs):
        messages.info(request, "Cerraste sesión correctamente.")
        return super().post(request, *args, **kwargs)


class PerfilView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Edición del perfil propio. get_object() devuelve SIEMPRE request.user:
    no hay pk en la URL, por lo tanto es imposible editar el perfil de otro.
    """
    form_class = PerfilForm
    template_name = "usuarios/perfil.html"
    success_url = reverse_lazy("usuarios:perfil")
    success_message = "Tus datos se actualizaron correctamente."

    def get_object(self, queryset=None):
        return self.request.user


class CambiarPasswordView(LoginRequiredMixin, SuccessMessageMixin, auth_views.PasswordChangeView):
    """Cambio de contraseña (pide la actual y valida la nueva). Mantiene la sesión abierta."""
    template_name = "usuarios/cambiar_password.html"
    success_url = reverse_lazy("usuarios:perfil")
    success_message = "Tu contraseña se cambió correctamente."

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs["class"] = "form-control"
        return form


# ---------------------------------------------------------------------------
# Administración de usuarios y roles: SOLO Administrador (usuarios.change_usuario)
# Un Empleado logueado que entra acá recibe 403; un anónimo va al login.
# ---------------------------------------------------------------------------
class UsuarioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = "usuarios.view_usuario"
    model = Usuario
    template_name = "usuarios/usuario_list.html"
    context_object_name = "usuarios"
    paginate_by = 20

    def get_queryset(self):
        qs = Usuario.objects.all().order_by("rol", "apellido")
        rol = self.request.GET.get("rol")
        if rol in Usuario.Rol.values:
            qs = qs.filter(rol=rol)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["roles"] = Usuario.Rol.choices
        ctx["rol_actual"] = self.request.GET.get("rol", "")
        return ctx


class UsuarioRolUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = "usuarios.change_usuario"
    model = Usuario
    form_class = RolForm
    template_name = "usuarios/usuario_rol_form.html"
    success_url = reverse_lazy("usuarios:lista")
    success_message = "Rol de %(email)s actualizado."

    def form_valid(self, form):
        # Un administrador no puede quitarse a sí mismo el rol (evita quedarse sin acceso)
        if form.instance.pk == self.request.user.pk and form.cleaned_data["rol"] != Usuario.Rol.ADMIN:
            form.add_error("rol", "No podés quitarte tu propio rol de Administrador.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_message(self, cleaned_data):
        return self.success_message % {"email": self.object.email}
