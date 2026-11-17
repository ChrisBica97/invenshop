# Guía paso a paso – Construcción de InvenShop

Esta guía sigue las fases del punto 6 del enunciado ("Pasos para la Ejecución del
Trabajo"). En cada paso se indica **qué se hizo**, **con qué comando o archivo** y
**por qué**. Al final hay una lista de verificación manual.

---

## FASE 1 – Configuración del entorno

### Paso 1. Crear la carpeta y el entorno virtual

```bash
mkdir invenshop
cd invenshop
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/Mac: source venv/bin/activate)
```

**Por qué:** el entorno virtual aísla las librerías de este proyecto de las del
sistema y de otros proyectos.

### Paso 2. Instalar dependencias y registrarlas

```bash
pip install "Django>=5.2" Pillow python-dotenv
```

Se crea `requirements.txt` con las versiones mínimas:

| Paquete | Para qué |
|---|---|
| Django | el framework |
| Pillow | obligatorio para usar `ImageField` (imagen del producto) |
| python-dotenv | leer el archivo `.env` |

### Paso 3. Crear el proyecto

```bash
django-admin startproject config .
```

El punto final hace que `manage.py` quede en la raíz y la configuración en la
carpeta `config/`, tal como pide el enunciado.

### Paso 4. Variables de entorno (`.env`)

1. Se crea `.env.example` con todas las variables, sin valores secretos reales.
2. Cada desarrollador lo copia como `.env` y pone su propia `SECRET_KEY`.
3. `.env` se agrega a `.gitignore` para que **nunca** llegue al repositorio.
4. En `config/settings.py`:

```python
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Falta SECRET_KEY ...")
DEBUG = env_bool("DEBUG", False)
```

**Por qué:** la clave secreta y las credenciales de la base no deben estar escritas
en el código. Si falta la clave, el proyecto falla a propósito en lugar de usar
una clave insegura.

---

## FASE 2 – Desarrollo del backend

### Paso 5. Crear las apps

```bash
python manage.py startapp core
python manage.py startapp usuarios
python manage.py startapp catalogo
python manage.py startapp pedidos
```

Se registran en `INSTALLED_APPS`. Cada app tiene una responsabilidad:

| App | Responsabilidad |
|---|---|
| `usuarios` | usuario personalizado, roles, registro, login, perfil |
| `catalogo` | categorías, productos, catálogo público y su gestión |
| `pedidos` | carrito, checkout, pedidos, cambios de estado, reportes |
| `core` | página de inicio, panel de gestión, datos de demo y tests |

### Paso 6. Modelo de usuario personalizado (ANTES de la primera migración)

En `usuarios/models.py` se define `Usuario(AbstractBaseUser, PermissionsMixin)`:

- `USERNAME_FIELD = "email"`: el login se hace con el email.
- Campos `nombre`, `apellido`, `telefono` (con `RegexValidator`) y `rol` (`TextChoices`).
- `UsuarioManager` con `create_user` (rol Cliente por defecto) y `create_superuser`
  (rol Admin).
- `save()` sincroniza `is_staff` y el **grupo** del usuario según su rol.

En `settings.py`:

```python
AUTH_USER_MODEL = "usuarios.Usuario"
```

> ⚠️ Esto debe configurarse **antes** del primer `migrate`. Cambiar el modelo de
> usuario después obliga a borrar la base de datos.

### Paso 7. Roles como grupos con permisos

`usuarios/roles.py` define la matriz de permisos del enunciado como un
diccionario `{grupo: [permisos]}`. En `usuarios/apps.py` se conecta la señal
`post_migrate` para que, **después de cada `migrate`**, se creen o actualicen
automáticamente los grupos *Administrador*, *Empleado* y *Cliente*.

**Por qué grupos y no `if user.rol == ...`:** las vistas solo preguntan
"¿tiene el permiso X?". Si mañana se quiere que un Empleado vea los reportes,
alcanza con cambiar `roles.py`, sin tocar ninguna vista.

Además de los permisos automáticos (`add_`, `change_`, `delete_`, `view_`), se
crearon permisos personalizados en `Pedido.Meta.permissions`:
`cambiar_estado_pedido`, `ver_todos_pedidos` y `ver_reportes`.

### Paso 8. Modelos del catálogo

`catalogo/models.py`:

- `Categoria`: `nombre` (único), `descripcion`, `slug` (generado en `save()`).
- `Producto`: `precio` (`DecimalField` con mínimo 0,01), `stock`
  (`PositiveIntegerField`), `categoria` (FK con `PROTECT`), `imagen`, `activo`.
- `ProductoQuerySet` con `.activos()` y `.con_categoria()`. Este último usa
  `select_related` para evitar el problema N+1.
- Propiedades `agotado` y `stock_bajo` para usar en las plantillas.
- Índices en `(activo, categoria)` y `precio`; restricción de nombre único por
  categoría.

### Paso 9. Modelos de pedidos

`pedidos/models.py`:

- `Pedido`: `usuario` (FK `PROTECT`), `fecha_creacion`, `estado`, `total` y los
  datos de envío.
- `TRANSICIONES` define la máquina de estados:
  `Pendiente → Pagado → Enviado`, y `Cancelado` desde Pendiente o Pagado.
- `cambiar_estado()` valida la transición y, si se cancela, **repone el stock** con
  `F("stock") + cantidad` dentro de `transaction.atomic`.
- `DetallePedido` guarda `precio_unitario`: el precio **del momento de la compra**,
  así el historial no cambia si después cambia el precio del producto.

### Paso 10. Migraciones

```bash
python manage.py makemigrations usuarios
python manage.py makemigrations catalogo
python manage.py makemigrations pedidos
python manage.py migrate
```

Se generan en ese orden (de la app de la que dependen las demás hacia afuera)
para obtener **una sola migración inicial por app**: un historial limpio.

### Paso 11. Carrito en sesión

`pedidos/carrito.py`, clase `Carrito`:

- Guarda en `request.session["carrito"]` solo `{id_producto: cantidad}`.
  **Nunca el precio**, que se lee siempre de la base y por eso no se puede
  manipular desde el navegador.
- `agregar()` valida que el producto esté activo, no esté agotado y que la
  cantidad no supere el stock (lanza `StockInsuficiente`).
- `items()` trae todos los productos en **un solo query** (`in_bulk`).

### Paso 12. Registro del pedido (transacción)

`pedidos/servicios.py` → `crear_pedido()` con `@transaction.atomic`:

1. Bloquea las filas de los productos (`select_for_update`).
2. Revalida el stock con datos frescos.
3. Crea el `Pedido` y los `DetallePedido` (`bulk_create`).
4. Descuenta el stock con `F()`.
5. Vacía el carrito.

Si cualquier paso falla, **no queda nada a medias**.

### Paso 13. Vistas basadas en clases y control de acceso

| Tipo | Vistas | Protección |
|---|---|---|
| Públicas | `ProductoListView`, `ProductoDetailView`, `HomeView` | — |
| Cliente | `PerfilView`, `CheckoutView`, `ConfirmarPedidoView`, `MisPedidosListView`, `PedidoDetailView` | `LoginRequiredMixin` + filtro por dueño |
| Personal | CRUD de productos y categorías, `PedidoGestionListView` | `LoginRequiredMixin` + `PermissionRequiredMixin` |
| Panel | `PanelView` | `UserPassesTestMixin` (`es_personal`) |
| Funciones | `cambiar_estado_pedido`, `reportes` | `@login_required` + `@permission_required(..., raise_exception=True)` |

Comportamiento: un **anónimo** es redirigido al login y un **usuario logueado sin
permiso** recibe **403**.

### Paso 14. Panel de administración (`admin.py`)

- **Producto:** `list_display` con miniatura y estado del stock; `list_editable =
  ("stock", "activo")`; `list_filter` por categoría, activo y fecha;
  `search_fields`; `list_select_related`; acciones para activar y desactivar.
- **Pedido:** `DetallePedidoInline` de solo lectura; `search_fields = ("=id",
  "usuario__email")` (número exacto o email); `list_filter` por estado y rango de
  fechas; `date_hierarchy`; no se pueden crear pedidos desde el admin; al
  cambiar el estado se valida la transición.
- **Usuario:** búsqueda por email; filtro por rol; edición rápida de rol y activo.

---

## FASE 3 – Frontend y formularios

### Paso 15. Plantillas con herencia

- `templates/base.html`: navbar (el menú cambia según el rol y los permisos),
  mensajes, footer y Bootstrap 5 por CDN.
- Todas las páginas empiezan con `{% extends "base.html" %}`.
- Fragmentos reutilizables con `{% include %}`: `includes/campo.html`,
  `includes/form.html`, `includes/paginacion.html` y `includes/producto_card.html`.
- La paginación usa `{% querystring page=... %}` (Django 5.1+) para **conservar la
  búsqueda, la categoría y el orden** al cambiar de página.
- `403.html`, `404.html` y `500.html` propias. La 500 no extiende la base a
  propósito, para que no pueda volver a fallar.

### Paso 16. Formularios con validaciones personalizadas

| Formulario | Validaciones |
|---|---|
| `RegistroForm` | email único sin distinguir mayúsculas, validadores de contraseña, nombre y apellido normalizados, rol forzado a Cliente |
| `LoginForm` | mensajes de error claros en español |
| `PerfilForm` | solo nombre, apellido y teléfono (no puede tocar email ni rol) |
| `ProductoForm` | precio > 0, nombre único por categoría, imagen ≤ 2 MB, un producto nuevo y activo con stock ≥ 1 |
| `CategoriaForm` | evita dos categorías con el mismo slug |
| `DatosEnvioForm` | dirección con número, ciudad solo letras, CP argentino (`4000` o `T4000ABC`), teléfono con ≥ 8 dígitos |
| `ConfirmarPedidoForm` | casilla obligatoria de confirmación |
| `CambiarEstadoForm` | solo ofrece los estados a los que se puede pasar |

### Paso 17. Imágenes de productos

- `Producto.imagen` es un `ImageField(upload_to="productos/")` y por eso requiere
  **Pillow**. Las imágenes subidas se guardan en `MEDIA_ROOT/productos/`.
- El formulario de producto usa `enctype="multipart/form-data"` (sin eso, el archivo
  no llega al servidor) y `ProductoForm.clean_imagen()` limita el tamaño a 2 MB.
- En `config/urls.py` se sirve `media/` con `django.views.static.serve`, controlado
  por `SERVIR_MEDIA` en el `.env`. **No** se usa el atajo `static()`, porque deja de
  funcionar cuando `DEBUG=False` y las imágenes desaparecerían.
- `Producto.imagen_disponible` comprueba que el archivo exista. La plantilla
  `includes/producto_imagen.html` muestra la foto o, si falta, un recuadro con las
  iniciales: nunca una imagen rota.
- **Fotos reales:** el comando `descargar_imagenes` usa la API pública de
  Wikimedia Commons con `urllib` (biblioteca estándar, sin dependencias nuevas):
  1. Para cada producto prueba una lista de archivos de Commons elegidos a mano y,
     si ninguno existe, hace una búsqueda (`generator=search`).
  2. Pide la miniatura de 960 px y, con un `User-Agent` propio, como exige la
     política de Wikimedia.
  3. Con Pillow verifica que sea una imagen válida y la recorta a 800×600
     (`ImageOps.fit`).
  4. Guarda autor y licencia en `imagen_credito` y el enlace en `imagen_fuente`
     (migración `0002_credito_imagen`). La ficha del producto muestra el crédito,
     como exigen las licencias CC BY / CC BY-SA.
  5. Si no hay internet, informa el problema y deja las ilustraciones de
     `core/demo_imagenes/`.
- Las pruebas de este comando **simulan la red** con `unittest.mock`, así corren
  sin internet y siempre dan el mismo resultado.

### Paso 18. Mensajes de retroalimentación

Cada acción muestra un mensaje con `django.contrib.messages`. Los niveles se
mapean a las alertas de Bootstrap en `MESSAGE_TAGS` (`error` → `danger`).

---

## Verificación

### Automática

```bash
python manage.py test -v 2     # 35 pruebas
```

| Grupo | Qué prueba |
|---|---|
| `UsuariosTests` | registro, email duplicado, contraseña débil, redirección por rol, perfil propio |
| `PermisosTests` | anónimo → login, Cliente → 403, Empleado sin usuarios ni reportes, Admin cambia roles |
| `CatalogoTests` | solo activos, búsqueda y categoría combinadas, orden, paginación de 12, inactivo → 404, **sin N+1** |
| `CarritoTests` | agregar, modificar, quitar, vaciar, total, no superar el stock, solo POST |
| `DescargarImagenesTests` | descarga simulada de Commons: crédito sin HTML, segundo archivo si el primero no existe, búsqueda de respaldo, sin internet, no repite descargas |
| `ImagenesTests` | `cargar_demo` asigna imagen a todos los productos, las imágenes cargan aunque `DEBUG=False`, un archivo faltante no rompe la página |
| `PedidosTests` | checkout completo, validaciones de envío, confirmación obligatoria, stock que cambia a mitad de compra, pedidos ajenos, transiciones, reposición de stock, producto vendido que se desactiva, reportes |

### Manual (después de `python manage.py cargar_demo` y `runserver`)

1. **Anónimo:** recorrer el catálogo, buscar "mouse", filtrar por Electrónica y
   ordenar por precio. Los productos agotados aparecen marcados y no se pueden
   agregar; el producto inactivo ("Organizador de cajones") no aparece.
2. Agregar 2 productos al carrito, cambiar cantidades y pedir más que el stock:
   aparece un mensaje de error. Ir a *Continuar compra*: pide iniciar sesión.
3. **Registrarse** con un email nuevo: queda como Cliente y vuelve al catálogo.
4. **Checkout:** probar un CP inválido (`12`) y una dirección sin número para ver
   los errores. Completar bien, confirmar sin tildar la casilla (error) y luego
   tildarla. Se ve el pedido con el mensaje de éxito y el stock descontado.
5. Como Cliente, entrar a `/panel/` o `/pedidos/reportes/`: **403**.
6. **Empleado:** al ingresar va al panel. Cambiar un pedido a *Pagado* y después a
   *Cancelado*: el stock se repone. Entrar a `/cuenta/gestion/`: **403**.
7. **Administrador:** *Reportes*; *Usuarios y roles* (convertir un cliente en
   Empleado); en `/admin/` editar el stock desde el listado de productos y buscar
   el pedido `1`.
8. Poner `DEBUG=False` en `.env`, reiniciar con `python manage.py runserver
   --insecure` y abrir `/catalogo/producto/9999/`: se ve la página 404 propia,
   sin información técnica.
