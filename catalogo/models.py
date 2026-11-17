"""App catalogo - Categorías y productos."""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Categoria(models.Model):
    nombre = models.CharField("nombre", max_length=80, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    slug = models.SlugField("slug", max_length=90, unique=True, blank=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if not self.slug:  # slug automático a partir del nombre
            self.slug = slugify(self.nombre)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        # El catálogo filtrado por esta categoría
        return f"{reverse('catalogo:lista')}?categoria={self.slug}"


class ProductoQuerySet(models.QuerySet):
    """Consultas reutilizables: Producto.objects.activos().con_categoria()"""

    def activos(self):
        return self.filter(activo=True)

    def con_categoria(self):
        # select_related -> trae la categoría en el MISMO query (evita N+1)
        return self.select_related("categoria")


class Producto(models.Model):
    nombre = models.CharField("nombre", max_length=120)
    descripcion = models.TextField("descripción")
    precio = models.DecimalField(
        "precio", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"), "El precio debe ser mayor a 0.")],
    )
    stock = models.PositiveIntegerField("stock", default=0)
    # PROTECT: no se puede borrar una categoría que todavía tiene productos
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="productos", verbose_name="categoría"
    )
    imagen = models.ImageField("imagen", upload_to="productos/", blank=True)
    # Atribución de la foto (obligatoria en licencias CC BY / CC BY-SA)
    imagen_credito = models.CharField(
        "crédito de la imagen", max_length=255, blank=True,
        help_text="Autor y licencia, si la foto no es propia. Ej: Juan Pérez · CC BY-SA 4.0",
    )
    imagen_fuente = models.URLField("fuente de la imagen", blank=True)
    activo = models.BooleanField("activo", default=True, help_text="Solo los activos se ven en el catálogo.")
    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["nombre"]
        # Índices para las consultas más frecuentes del catálogo
        indexes = [
            models.Index(fields=["activo", "categoria"]),
            models.Index(fields=["precio"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["nombre", "categoria"], name="producto_unico_por_categoria"),
        ]

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse("catalogo:detalle", kwargs={"pk": self.pk})

    @property
    def imagen_disponible(self):
        """True si el producto tiene imagen Y el archivo existe en disco
        (evita mostrar una imagen rota si se borró la carpeta media/)."""
        return bool(self.imagen) and self.imagen.storage.exists(self.imagen.name)

    @property
    def iniciales(self):
        """Usadas en el reemplazo visual cuando no hay imagen."""
        return "".join(p[0] for p in self.nombre.split()[:2]).upper()

    @property
    def agotado(self):
        return self.stock == 0

    @property
    def stock_bajo(self):
        return 0 < self.stock <= 5
