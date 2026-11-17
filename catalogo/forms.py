"""Formularios del catálogo con validaciones personalizadas."""
from django import forms
from django.utils.text import slugify

from usuarios.forms import BootstrapMixin

from .models import Categoria, Producto

TAMANIO_MAX_IMAGEN_MB = 2


class CategoriaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        # Evita dos categorías que generen el mismo slug ("Hogar" y "hogar")
        qs = Categoria.objects.filter(slug=slugify(nombre)).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe una categoría con ese nombre.")
        return nombre


class ProductoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "categoria", "descripcion", "precio", "stock", "imagen", "imagen_credito", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()
        self.fields["categoria"].widget.attrs["class"] = "form-select"

    def clean_nombre(self):
        return self.cleaned_data["nombre"].strip()

    def clean_imagen(self):
        imagen = self.cleaned_data.get("imagen")
        if imagen and hasattr(imagen, "size") and imagen.size > TAMANIO_MAX_IMAGEN_MB * 1024 * 1024:
            raise forms.ValidationError(f"La imagen no puede superar los {TAMANIO_MAX_IMAGEN_MB} MB.")
        return imagen

    def clean(self):
        datos = super().clean()
        nombre, categoria = datos.get("nombre"), datos.get("categoria")
        if nombre and categoria:
            existe = (
                Producto.objects.filter(nombre__iexact=nombre, categoria=categoria)
                .exclude(pk=self.instance.pk).exists()
            )
            if existe:
                self.add_error("nombre", "Ya existe un producto con ese nombre en la categoría elegida.")
        # Regla de negocio: no tiene sentido publicar un producto nuevo sin stock
        if not self.instance.pk and datos.get("activo") and datos.get("stock") == 0:
            self.add_error("stock", "Un producto nuevo y activo debe tener al menos 1 unidad de stock.")
        return datos


class FiltroCatalogoForm(forms.Form):
    """Valida los parámetros GET del catálogo (búsqueda, categoría, orden)."""
    ORDENES = [
        ("nombre", "Nombre (A-Z)"),
        ("-nombre", "Nombre (Z-A)"),
        ("precio", "Precio: menor a mayor"),
        ("-precio", "Precio: mayor a menor"),
    ]
    q = forms.CharField(required=False, max_length=100)
    categoria = forms.SlugField(required=False)
    orden = forms.ChoiceField(required=False, choices=ORDENES)


class AgregarAlCarritoForm(forms.Form):
    cantidad = forms.IntegerField(
        min_value=1, initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "style": "max-width:100px"}),
    )

    def __init__(self, *args, stock_maximo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if stock_maximo:
            self.fields["cantidad"].max_value = stock_maximo
            self.fields["cantidad"].widget.attrs["max"] = stock_maximo
