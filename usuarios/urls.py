from django.urls import path

from . import views

app_name = "usuarios"

urlpatterns = [
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("ingresar/", views.IngresarView.as_view(), name="login"),
    path("salir/", views.SalirView.as_view(), name="logout"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("perfil/password/", views.CambiarPasswordView.as_view(), name="cambiar_password"),
    # Administración de roles (solo Administrador)
    path("gestion/", views.UsuarioListView.as_view(), name="lista"),
    path("gestion/<int:pk>/rol/", views.UsuarioRolUpdateView.as_view(), name="editar_rol"),
]
