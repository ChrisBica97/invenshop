"""Context processor: expone {{ carrito_cantidad }} en TODAS las plantillas (badge del navbar)."""
from django.conf import settings


def carrito(request):
    # Solo LEE la sesión (no la crea): un visitante sin carrito no genera escrituras.
    session = getattr(request, "session", None)
    if session is None:
        return {}
    return {"carrito_cantidad": sum(session.get(settings.CARRITO_SESSION_ID, {}).values())}
