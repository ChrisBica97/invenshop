"""Formularios de checkout y gestión de pedidos con validaciones personalizadas."""
import re

from django import forms

from usuarios.forms import BootstrapMixin
from usuarios.models import telefono_validator

from .models import Pedido


class DatosEnvioForm(BootstrapMixin, forms.Form):
    """Datos de envío del checkout (5.3), cada uno con su validación propia."""

    direccion = forms.CharField(
        label="Dirección", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ej: Av. Belgrano 1234, piso 2"}),
    )
    ciudad = forms.CharField(label="Ciudad", max_length=80)
    codigo_postal = forms.CharField(
        label="Código postal", max_length=8,
        help_text="4 dígitos (ej: 4000) o formato CPA (ej: T4000ABC).",
    )
    telefono_contacto = forms.CharField(
        label="Teléfono de contacto", max_length=20, validators=[telefono_validator]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_direccion(self):
        direccion = " ".join(self.cleaned_data["direccion"].split())
        if len(direccion) < 5:
            raise forms.ValidationError("La dirección es demasiado corta.")
        if not re.search(r"\d", direccion):
            raise forms.ValidationError("Incluí la altura (número) de la calle.")
        return direccion

    def clean_ciudad(self):
        ciudad = " ".join(self.cleaned_data["ciudad"].split())
        if not re.fullmatch(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'-]{2,80}", ciudad):
            raise forms.ValidationError("La ciudad solo puede contener letras y espacios.")
        return ciudad.title()

    def clean_codigo_postal(self):
        cp = self.cleaned_data["codigo_postal"].strip().upper().replace(" ", "")
        # Argentina: viejo formato de 4 dígitos o CPA (letra + 4 dígitos + 3 letras)
        if not re.fullmatch(r"\d{4}|[A-Z]\d{4}[A-Z]{3}", cp):
            raise forms.ValidationError("Código postal inválido. Usá 4 dígitos (4000) o CPA (T4000ABC).")
        return cp

    def clean_telefono_contacto(self):
        tel = self.cleaned_data["telefono_contacto"]
        if len(re.sub(r"\D", "", tel)) < 8:
            raise forms.ValidationError("El teléfono debe tener al menos 8 dígitos.")
        return tel


class ConfirmarPedidoForm(forms.Form):
    """Confirmación final antes de registrar el pedido."""
    acepto = forms.BooleanField(
        label="Revisé el resumen y confirmo mi pedido",
        error_messages={"required": "Tenés que confirmar el pedido para continuar."},
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class CambiarEstadoForm(forms.Form):
    """Solo ofrece los estados a los que el pedido puede pasar legalmente."""
    estado = forms.ChoiceField(label="Nuevo estado", widget=forms.Select(attrs={"class": "form-select"}))

    def __init__(self, *args, pedido, **kwargs):
        super().__init__(*args, **kwargs)
        self.pedido = pedido
        self.fields["estado"].choices = [(e, Pedido.Estado(e).label) for e in pedido.estados_siguientes()]

    def clean_estado(self):
        estado = self.cleaned_data["estado"]
        if not self.pedido.puede_cambiar_a(estado):
            raise forms.ValidationError("Transición de estado no permitida.")
        return estado
