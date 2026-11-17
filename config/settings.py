"""
Configuración del proyecto InvenShop.

CRITERIO "Arquitectura y Entorno":
  * Las credenciales y valores sensibles (SECRET_KEY, DEBUG, base de datos)
    NO están escritos en el código: se leen del archivo .env con python-dotenv.
  * El archivo .env NO se sube al repositorio (.gitignore). Se entrega un
    .env.example como plantilla.
"""
import os
from pathlib import Path

from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga las variables definidas en BASE_DIR/.env dentro de os.environ
load_dotenv(BASE_DIR / ".env")


def env_bool(nombre, por_defecto=False):
    """Convierte 'True'/'1'/'si' del .env en un booleano de Python."""
    return os.getenv(nombre, str(por_defecto)).strip().lower() in ("1", "true", "si", "sí", "yes")


def env_list(nombre, por_defecto=""):
    """Convierte 'a,b,c' del .env en ['a', 'b', 'c']."""
    return [x.strip() for x in os.getenv(nombre, por_defecto).split(",") if x.strip()]


# ---------------------------------------------------------------------------
# Seguridad básica
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # Falla de forma explícita en lugar de usar una clave insegura por defecto
    raise ImproperlyConfigured(
        "Falta SECRET_KEY. Copiá .env.example como .env y completá los valores."
    )

# En producción DEBUG debe ser False: así Django NO muestra trazas de error
# con información sensible (variables, rutas, configuración) al usuario.
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",   # necesaria para el carrito en sesión
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",   # filtros como intcomma para precios
    # Apps propias (organización modular)
    "core.apps.CoreConfig",          # inicio, panel de gestión, páginas de error
    "usuarios.apps.UsuariosConfig",  # usuario personalizado, roles, auth
    "catalogo.apps.CatalogoConfig",  # categorías y productos
    "pedidos.apps.PedidosConfig",    # carrito, checkout, pedidos, reportes
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",            # protección CSRF
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",  # anti clickjacking
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # plantillas globales del proyecto
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Propio: deja disponible el carrito en todas las plantillas
                "pedidos.context_processors.carrito",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Base de datos: SQLite por defecto; PostgreSQL si DB_ENGINE=postgresql en .env
# ---------------------------------------------------------------------------
if os.getenv("DB_ENGINE", "sqlite").lower() == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "invenshop"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------------
# Autenticación con modelo de usuario personalizado (login por email)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "usuarios.Usuario"
LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "catalogo:lista"  # se redefine por rol en la vista de login
LOGOUT_REDIRECT_URL = "core:home"

# Validadores de contraseña de Django (pedidos explícitamente en 5.1)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y de medios (imágenes de productos)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Si Django debe servir las imágenes subidas (media/). True para usar el proyecto
# localmente con runserver, aunque DEBUG sea False. En un servidor real se pone
# False y las sirve el servidor web (Nginx, Apache, etc.).
SERVIR_MEDIA = env_bool("SERVIR_MEDIA", True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Mensajes: se mapean a las clases de alerta de Bootstrap
# ---------------------------------------------------------------------------
MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# ---------------------------------------------------------------------------
# Sesiones / carrito
# ---------------------------------------------------------------------------
CARRITO_SESSION_ID = "carrito"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # una semana
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # el token debe poder leerse desde el formulario

# ---------------------------------------------------------------------------
# Endurecimiento extra cuando NO estamos en desarrollo
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SESSION_COOKIE_SECURE = env_bool("HTTPS", False)
    CSRF_COOKIE_SECURE = env_bool("HTTPS", False)
    SECURE_SSL_REDIRECT = env_bool("HTTPS", False)
    if env_bool("HTTPS", False):
        SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # el navegador solo usará HTTPS por 30 días

# Los errores se registran en consola (y en el servidor), nunca se muestran al usuario.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    # Los 403/404 son esperables (accesos no autorizados): solo se registran errores 5xx
    "loggers": {"django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}
