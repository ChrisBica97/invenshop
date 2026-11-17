"""
App usuarios - Modelo de usuario personalizado (Custom User Model).

Se reemplaza el usuario de Django para:
  * Iniciar sesión con EMAIL (no con username).
  * Guardar nombre, apellido, teléfono y ROL (Admin / Empleado / Cliente).

IMPORTANTE: AUTH_USER_MODEL = "usuarios.Usuario" se configuró ANTES de la
primera migración, como recomienda Django.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import Group, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# Validador reutilizable para teléfonos: dígitos, espacios, guiones, paréntesis y "+"
telefono_validator = RegexValidator(
    regex=r"^\+?[\d\s\-()]{8,20}$",
    message="Ingresá un teléfono válido (solo números, espacios, guiones o +; entre 8 y 20 caracteres).",
)


class UsuarioManager(BaseUserManager):
    """Manager que crea usuarios usando el email como identificador."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)  # guarda la contraseña HASHEADA, nunca en texto plano
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.CLIENTE)  # rol por defecto: Cliente
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("rol", Usuario.Rol.ADMIN)
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    class Rol(models.TextChoices):
        ADMIN = "Admin", "Administrador"
        EMPLEADO = "Empleado", "Empleado"
        CLIENTE = "Cliente", "Cliente"

    # Nombre del Group de Django asociado a cada rol (ver usuarios/roles.py)
    GRUPO_POR_ROL = {
        Rol.ADMIN: "Administrador",
        Rol.EMPLEADO: "Empleado",
        Rol.CLIENTE: "Cliente",
    }

    email = models.EmailField("email", unique=True)
    nombre = models.CharField("nombre", max_length=60)
    apellido = models.CharField("apellido", max_length=60)
    rol = models.CharField("rol", max_length=10, choices=Rol.choices, default=Rol.CLIENTE)
    telefono = models.CharField("teléfono", max_length=20, blank=True, validators=[telefono_validator])

    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField(
        "acceso al admin", default=False,
        help_text="Se calcula según el rol: Admin y Empleado pueden entrar al panel /admin/.",
    )
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"               # campo usado para el login
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "apellido"]  # pedidos por createsuperuser

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.nombre} {self.apellido}".strip()

    def get_short_name(self):
        return self.nombre

    # --- Atajos para consultar el rol en vistas y plantillas ---
    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.is_superuser

    @property
    def es_empleado(self):
        return self.rol == self.Rol.EMPLEADO

    @property
    def es_cliente(self):
        return self.rol == self.Rol.CLIENTE and not self.is_superuser

    @property
    def es_personal(self):
        """Personal interno (Admin o Empleado): accede al panel de gestión."""
        return self.es_admin or self.es_empleado

    def save(self, *args, **kwargs):
        # Normaliza el email y sincroniza is_staff con el rol
        self.email = self.email.lower()
        self.is_staff = self.rol in (self.Rol.ADMIN, self.Rol.EMPLEADO) or self.is_superuser
        super().save(*args, **kwargs)
        # Cada usuario pertenece SOLO al grupo de su rol; los permisos se heredan del grupo
        grupo, _ = Group.objects.get_or_create(name=self.GRUPO_POR_ROL[self.rol])
        self.groups.set([grupo])
