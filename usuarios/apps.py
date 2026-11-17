from django.apps import AppConfig, apps as global_apps
from django.db.models.signals import post_migrate


def crear_grupos_y_permisos(sender, **kwargs):
    """
    Se ejecuta automáticamente después de cada `python manage.py migrate`.
    Primero asegura que existan los permisos de TODAS las apps y luego
    crea los grupos Administrador / Empleado / Cliente con sus permisos.
    """
    from django.contrib.auth.management import create_permissions

    from .roles import sincronizar_grupos

    for app_config in global_apps.get_app_configs():
        create_permissions(app_config, verbosity=0)
    sincronizar_grupos()


class UsuariosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "usuarios"
    verbose_name = "Usuarios"

    def ready(self):
        # sender=self -> se ejecuta una sola vez por migrate
        post_migrate.connect(crear_grupos_y_permisos, sender=self)
