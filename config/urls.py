"""
URLs principales de InvenShop. Cada app es dueña de sus rutas (include()).

    /                 -> core      (inicio, panel)
    /cuenta/...       -> usuarios  (registro, login, perfil, roles)
    /catalogo/...     -> catalogo  (catálogo público y gestión)
    /pedidos/...      -> pedidos   (carrito, checkout, historial, gestión, reportes)
    /admin/           -> panel de administración de Django personalizado
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

# Textos del sitio de administración
admin.site.site_header = "InvenShop · Administración"
admin.site.site_title = "InvenShop Admin"
admin.site.index_title = "Gestión de la tienda"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("cuenta/", include("usuarios.urls")),
    path("catalogo/", include("catalogo.urls")),
    path("pedidos/", include("pedidos.urls")),
]

# Imágenes subidas (media/). Se usa la vista serve() directamente y no el atajo
# static(), porque static() no hace nada cuando DEBUG=False y las imágenes
# dejarían de verse. Se controla con SERVIR_MEDIA en el .env.
def servir_media(request, path):
    """Sirve un archivo de MEDIA_ROOT (leído en cada request, no al arrancar)."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


if settings.SERVIR_MEDIA:
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", servir_media)]
