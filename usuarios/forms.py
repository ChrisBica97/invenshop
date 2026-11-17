"""Formularios de usuarios: registro, login por email y edición de perfil."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm

from .models import Usuario


class BootstrapMixin:
    """Agrega la clase CSS de Bootstrap a todos los campos del formulario."""

    def _aplicar_bootstrap(self):
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs.setdefault("class", css)


class RegistroForm(BootstrapMixin, BaseUserCreationForm):
    """
    Registro (5.1): email, nombre, apellido, teléfono, contraseña y confirmación.
    BaseUserCreationForm ya aporta password1/password2, verifica que coincidan
    y aplica AUTH_PASSWORD_VALIDATORS.
    """

    class Meta:
        model = Usuario
        fields = ["email", "nombre", "apellido", "telefono"]
        widgets = {"email": forms.EmailInput(attrs={"autofocus": True})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Contraseña"
        self.fields["password2"].label = "Confirmar contraseña"
        self.fields["telefono"].required = True
        self._aplicar_bootstrap()

    def clean_email(self):
        """Email único sin importar mayúsculas (Juan@x.com == juan@x.com)."""
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta registrada con ese email.")
        return email

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip().title()

    def clean_apellido(self):
        return self.cleaned_data["apellido"].strip().title()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.rol = Usuario.Rol.CLIENTE  # todo usuario nuevo es Cliente (no se puede elegir)
        if commit:
            user.save()
        return user


class LoginForm(BootstrapMixin, AuthenticationForm):
    """Login con email + contraseña y mensajes de error claros en español."""

    error_messages = {
        "invalid_login": "Email o contraseña incorrectos. Verificá los datos e intentá de nuevo.",
        "inactive": "Esta cuenta está desactivada. Contactá al administrador.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget = forms.EmailInput(attrs={"autofocus": True})
        self._aplicar_bootstrap()

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class PerfilForm(BootstrapMixin, forms.ModelForm):
    """Edición de perfil: SOLO datos personales (no email, ni rol, ni permisos)."""

    class Meta:
        model = Usuario
        fields = ["nombre", "apellido", "telefono"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()


class RolForm(BootstrapMixin, forms.ModelForm):
    """Usado por el Administrador para cambiar el rol de un usuario."""

    class Meta:
        model = Usuario
        fields = ["rol", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()
        self.fields["rol"].widget.attrs["class"] = "form-select"
