"""
Matriz de permisos por rol (consigna 5.1).

Cada rol se implementa como un Group de Django con permisos asignados.
Así las vistas solo preguntan "¿tiene el permiso X?" (PermissionRequiredMixin
o @permission_required) y no dependen del nombre del rol.

| Rol            | Permisos                                                          |
|----------------|-------------------------------------------------------------------|
| Administrador  | TODO: usuarios y roles, catálogo, pedidos y reportes.             |
| Empleado       | Productos, categorías y stock; cambiar estado de pedidos.         |
|                | SIN acceso a la administración de usuarios.                       |
| Cliente        | Sin permisos de modelo: navega el catálogo, usa el carrito, compra|
|                | y ve SOLO sus pedidos/perfil (se controla por dueño en las vistas)|
"""
from django.contrib.auth.models import Group, Permission

PERMISOS_POR_GRUPO = {
    "Administrador": [
        # Usuarios
        "usuarios.add_usuario", "usuarios.change_usuario",
        "usuarios.delete_usuario", "usuarios.view_usuario",
        # Catálogo
        "catalogo.add_categoria", "catalogo.change_categoria",
        "catalogo.delete_categoria", "catalogo.view_categoria",
        "catalogo.add_producto", "catalogo.change_producto",
        "catalogo.delete_producto", "catalogo.view_producto",
        # Pedidos
        "pedidos.view_pedido", "pedidos.change_pedido", "pedidos.delete_pedido",
        "pedidos.view_detallepedido", "pedidos.change_detallepedido",
        "pedidos.cambiar_estado_pedido", "pedidos.ver_todos_pedidos",
        "pedidos.ver_reportes",
    ],
    "Empleado": [
        "catalogo.add_categoria", "catalogo.change_categoria",
        "catalogo.delete_categoria", "catalogo.view_categoria",
        "catalogo.add_producto", "catalogo.change_producto",
        "catalogo.delete_producto", "catalogo.view_producto",
        "pedidos.view_pedido", "pedidos.change_pedido", "pedidos.view_detallepedido",
        "pedidos.cambiar_estado_pedido", "pedidos.ver_todos_pedidos",
    ],
    "Cliente": [],
}


def sincronizar_grupos(verbosity=0):
    """Crea (o actualiza) los grupos y les asigna exactamente sus permisos."""
    for nombre_grupo, codigos in PERMISOS_POR_GRUPO.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        permisos = []
        for codigo in codigos:
            app_label, codename = codigo.split(".")
            try:
                permisos.append(
                    Permission.objects.get(content_type__app_label=app_label, codename=codename)
                )
            except Permission.DoesNotExist:
                if verbosity:
                    print(f"  ! Permiso inexistente: {codigo}")
        grupo.permissions.set(permisos)
        if verbosity:
            print(f"  Grupo '{nombre_grupo}': {len(permisos)} permisos")
