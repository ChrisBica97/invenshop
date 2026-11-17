from django.urls import path

from . import views

app_name = "catalogo"

urlpatterns = [
    # Público
    path("", views.ProductoListView.as_view(), name="lista"),
    path("producto/<int:pk>/", views.ProductoDetailView.as_view(), name="detalle"),
    # Gestión de productos
    path("gestion/productos/", views.ProductoGestionListView.as_view(), name="gestion_productos"),
    path("gestion/productos/nuevo/", views.ProductoCreateView.as_view(), name="producto_crear"),
    path("gestion/productos/<int:pk>/editar/", views.ProductoUpdateView.as_view(), name="producto_editar"),
    path("gestion/productos/<int:pk>/eliminar/", views.ProductoDeleteView.as_view(), name="producto_eliminar"),
    # Gestión de categorías
    path("gestion/categorias/", views.CategoriaListView.as_view(), name="gestion_categorias"),
    path("gestion/categorias/nueva/", views.CategoriaCreateView.as_view(), name="categoria_crear"),
    path("gestion/categorias/<int:pk>/editar/", views.CategoriaUpdateView.as_view(), name="categoria_editar"),
    path("gestion/categorias/<int:pk>/eliminar/", views.CategoriaDeleteView.as_view(), name="categoria_eliminar"),
]
