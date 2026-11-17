from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    # Carrito
    path("carrito/", views.carrito_detalle, name="carrito"),
    path("carrito/agregar/<int:producto_id>/", views.carrito_agregar, name="carrito_agregar"),
    path("carrito/actualizar/<int:producto_id>/", views.carrito_actualizar, name="carrito_actualizar"),
    path("carrito/quitar/<int:producto_id>/", views.carrito_quitar, name="carrito_quitar"),
    path("carrito/vaciar/", views.carrito_vaciar, name="carrito_vaciar"),
    # Checkout
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("checkout/confirmar/", views.ConfirmarPedidoView.as_view(), name="confirmar"),
    # Historial y detalle
    path("mis-pedidos/", views.MisPedidosListView.as_view(), name="mis_pedidos"),
    path("<int:pk>/", views.PedidoDetailView.as_view(), name="detalle"),
    # Gestión
    path("gestion/", views.PedidoGestionListView.as_view(), name="gestion"),
    path("<int:pk>/estado/", views.cambiar_estado_pedido, name="cambiar_estado"),
    path("reportes/", views.reportes, name="reportes"),
]
