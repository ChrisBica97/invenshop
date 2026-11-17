# InvenShop – Sistema de Gestión e Inventario con Comercio Electrónico

Trabajo Final de Aplicación · Programación IV · Tecnicatura Superior en Desarrollo de Software · 2026

Aplicación web monolítica con Django para administrar productos, controlar el
inventario en tiempo real, procesar pedidos y ofrecer un catálogo con carrito
de compras para clientes.

> 📘 La construcción del proyecto, fase por fase, está explicada en
> [`docs/GUIA_PASO_A_PASO.md`](docs/GUIA_PASO_A_PASO.md).

---

## 1. Puesta en marcha

```bash
# 1. Entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / Mac

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
copy .env.example .env           # Windows   (Linux/Mac: cp .env.example .env)
#   -> abrir .env y reemplazar SECRET_KEY por una clave nueva:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Base de datos (crea tablas + grupos/permisos de cada rol)
python manage.py migrate

# 5. Datos de demostración (usuarios, catálogo, pedidos y FOTOS REALES de Commons)
python manage.py cargar_demo

# 6. Servidor
python manage.py runserver
```

Abrir **http://127.0.0.1:8000/**

### Sin conexión a internet

Bootstrap 5.3.3 y Bootstrap Icons 1.11.3 están en `static/vendor/`, y las fotos de los
productos en `media/`: la aplicación se ve completa sin internet. Sin conexión, cargar los
datos de demo con `python manage.py cargar_demo --sin-internet` (usa las imágenes de
`core/demo_imagenes/` y no intenta descargar nada).

Para una demo local con `DEBUG=False` (páginas de error propias, sin trazas), usar:

```bash
python manage.py runserver --insecure   # --insecure: runserver sirve /static/ aunque DEBUG sea False
```

### Usuarios de prueba (creados por `cargar_demo`)

| Rol | Email | Contraseña | Al ingresar va a… |
|---|---|---|---|
| Administrador | `admin@invenshop.com` | `InvenShop2026!` | Panel de gestión |
| Empleado | `empleado@invenshop.com` | `InvenShop2026!` | Panel de gestión |
| Cliente | `cliente@invenshop.com` | `InvenShop2026!` | Catálogo |
| Cliente | `cliente2@invenshop.com` | `InvenShop2026!` | Catálogo |

También se puede crear un superusuario propio con `python manage.py createsuperuser`
(se le asigna automáticamente el rol Administrador).

### Imágenes de los productos (fotos reales)

`cargar_demo` descarga automáticamente **fotos reales** de cada producto desde
[Wikimedia Commons](https://commons.wikimedia.org), el banco de imágenes libres
de Wikipedia. Necesita internet y tarda menos de un minuto.

```bash
python manage.py descargar_imagenes            # descargar o completar las fotos
python manage.py descargar_imagenes --forzar   # volver a descargar todas
python manage.py descargar_imagenes --todos    # buscar también fotos para productos propios
```

- Todas las fotos de Commons tienen **licencia libre**. Varias exigen citar al
  autor, por eso cada producto guarda el **autor, la licencia y el enlace**, y la
  ficha del producto los muestra debajo de la foto.
- Las fotos se recortan a 800×600 (4:3) para que todas las tarjetas queden iguales.
- **Sin internet**, los productos usan las ilustraciones incluidas en
  `core/demo_imagenes/`, y se puede volver a intentar más tarde.
- Para usar una foto propia: **Gestión → Productos → ✏️ Editar → Imagen** (JPG o
  PNG de hasta 2 MB). Si la foto no es tuya, completá el campo *Crédito de la imagen*.

**¿No se ven las fotos?**

| Causa | Solución |
|---|---|
| No se ejecutó `cargar_demo` | `python manage.py cargar_demo` |
| Se ven ilustraciones (ícono + nombre) en lugar de fotos | No hubo internet al cargar: `python manage.py descargar_imagenes` |
| Error de certificados SSL (común en Mac) | `pip install certifi` y repetir `descargar_imagenes` |
| Se borró la carpeta `media/` | `python manage.py descargar_imagenes --forzar` |
| `SERVIR_MEDIA=False` en el `.env` | Poner `SERVIR_MEDIA=True` y reiniciar `runserver` |
| Productos creados a mano | Subirles la foto desde *Editar producto*, o `descargar_imagenes --todos` |

### Pruebas automáticas

```bash
python manage.py test -v 2      # 35 pruebas
```

---

## 2. Estructura del proyecto

```
invenshop/
├── manage.py
├── requirements.txt          dependencias
├── .env.example              plantilla de variables de entorno (.env NO se sube)
├── .gitignore
├── config/                   PROYECTO (startproject config .)
│   ├── settings.py           lee .env, apps, seguridad, mensajes, media
│   └── urls.py               include() de cada app
├── core/                     inicio, panel de gestión, comando cargar_demo, tests
│   ├── demo_imagenes/        ilustraciones de respaldo (si no hay internet)
│   └── management/commands/  cargar_demo y descargar_imagenes (fotos reales)
├── usuarios/                 usuario personalizado, roles, registro/login/perfil
│   ├── models.py             Usuario (login por email, rol, teléfono)
│   ├── roles.py              matriz de permisos -> Groups de Django
│   └── apps.py               crea los grupos automáticamente tras migrate
├── catalogo/                 Categoria, Producto, catálogo público y gestión
├── pedidos/                  Pedido, DetallePedido, carrito, checkout, reportes
│   ├── carrito.py            carrito en sesión
│   ├── servicios.py          registro transaccional del pedido
│   └── context_processors.py contador del carrito en el navbar
├── templates/                base.html + plantillas por app + 403/404/500
├── static/css/estilos.css
├── media/                    imágenes de productos (las crea cargar_demo / las sube el personal)
└── docs/GUIA_PASO_A_PASO.md
```

---

## 3. Cumplimiento de la consigna

### 3.1 Criterios de evaluación

| Criterio | Cómo se resolvió | Dónde |
|---|---|---|
| **Arquitectura y entorno** | 4 apps con responsabilidades separadas; credenciales en `.env` (python-dotenv), `.env` en `.gitignore`; `requirements.txt` con versiones | `config/settings.py`, `.env.example` |
| **Modelos y BD** | Esquema relacional con FK `PROTECT`/`CASCADE`, restricciones únicas, índices; una migración inicial por app | `*/models.py`, `*/migrations/` |
| **Evitar N+1** | `select_related("categoria")`, `select_related("usuario")`, `prefetch_related("detalles__producto")`, `in_bulk()`, `annotate()`/`aggregate()`, `list_select_related` en el admin. Hay tests que verifican que la cantidad de queries no crece con los datos | `catalogo/models.py` (`con_categoria`), `pedidos/views.py`, `core/tests.py` |
| **Lógica y vistas** | CBV: `ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`, `FormView`, `TemplateView`. ModelForms y Forms con `clean_<campo>()` y `clean()` | `*/views.py`, `*/forms.py` |
| **Autenticación y seguridad** | Roles con Groups/permisos; `LoginRequiredMixin`, `PermissionRequiredMixin`, `UserPassesTestMixin`, `@login_required`, `@permission_required`, `@require_POST`; `{% csrf_token %}` en todo formulario POST; autoescape contra XSS; `sensitive_post_parameters`; `DEBUG=False` + páginas 403/404/500 propias; cookies seguras con HTTPS | `usuarios/roles.py`, vistas, `templates/` |
| **Interfaz y UX** | `base.html` + `{% extends %}` + `{% include %}` reutilizables; Bootstrap 5 responsive; mensajes de éxito, error y advertencia en cada acción | `templates/` |

### 3.2 Modelado de datos (punto 4)

| App | Modelo | Campos pedidos | Extras justificados |
|---|---|---|---|
| usuarios | `Usuario` | email (único), nombre, apellido, rol, telefono | `is_active`, `is_staff` (derivado del rol), `date_joined` |
| catalogo | `Categoria` | nombre, descripcion, slug | slug automático |
| catalogo | `Producto` | nombre, descripcion, precio, stock, categoria (FK), imagen, activo | `creado`, `actualizado`, índices, nombre único por categoría |
| pedidos | `Pedido` | usuario (FK), fecha_creacion, estado, total | datos de envío (dirección, ciudad, CP, teléfono), permisos personalizados |
| pedidos | `DetallePedido` | pedido (FK), producto (FK), cantidad, precio_unitario | producto único por pedido |

### 3.3 Funcionalidades (punto 5)

| Requisito | Implementación |
|---|---|
| **5.1** Registro con email, nombre, apellido, teléfono y contraseña con confirmación; email único; validadores de Django; rol Cliente por defecto | `RegistroForm` (`clean_email` sin distinguir mayúsculas), `AUTH_PASSWORD_VALIDATORS`, `RegistroView` |
| **5.1** Login con email; mensajes claros; redirección por rol | `LoginForm` (mensajes en español), `IngresarView.get_success_url()` |
| **5.1** Perfil propio + cambio de contraseña | `PerfilView.get_object()` devuelve siempre `request.user`; `CambiarPasswordView` |
| **5.1** Control de acceso: decoradores en funciones y mixins en clases; 403 o login | `cambiar_estado_pedido` y `reportes` (decoradores); vistas de gestión (mixins) |
| **5.1** Matriz de permisos | `usuarios/roles.py` (ver tabla abajo) |
| **5.2** Listado: 12 por página, filtro por categoría + búsqueda combinables, solo activos, "Agotado", orden por precio/nombre | `ProductoListView` + `FiltroCatalogoForm` |
| **5.2** Detalle con imagen, descripción, precio, categoría, stock, selector de cantidad | `ProductoDetailView` + `AgregarAlCarritoForm` |
| **5.2** Carrito en sesión: agregar, modificar, quitar, vaciar; subtotales y total; no superar el stock; se vacía al confirmar | `pedidos/carrito.py` + vistas `carrito_*` |
| **5.3** Checkout solo autenticados; resumen; datos de envío validados; confirmación final | `CheckoutView` → `ConfirmarPedidoView`, `DatosEnvioForm`, `ConfirmarPedidoForm` |
| **5.3** Estados Pendiente → Pagado → Enviado / Cancelado; solo el personal los cambia; al cancelar se repone el stock | `Pedido.TRANSICIONES`, `Pedido.cambiar_estado()` |
| **5.3** Historial por cliente; el personal ve todos | `MisPedidosListView`, `PedidoDetailView` (pedido ajeno → 404), `PedidoGestionListView` |
| **5.4** Admin: `search_fields`, `list_filter` (con rango de fechas), `list_display`, `list_editable` (stock y activo), inlines de solo lectura | `*/admin.py` |

### 3.4 Matriz de permisos por rol

| Acción | Anónimo | Cliente | Empleado | Admin |
|---|:-:|:-:|:-:|:-:|
| Ver catálogo y usar el carrito | ✅ | ✅ | ✅ | ✅ |
| Checkout / mis pedidos / perfil | → login | ✅ | ✅ | ✅ |
| Ver pedido ajeno | → login | ❌ 404 | ✅ | ✅ |
| Panel, productos, categorías, stock | → login | ❌ 403 | ✅ | ✅ |
| Gestionar pedidos y cambiar estados | → login | ❌ 403 | ✅ | ✅ |
| Reportes de ventas | → login | ❌ 403 | ❌ 403 | ✅ |
| Usuarios y roles | → login | ❌ 403 | ❌ 403 | ✅ |
| Admin de Django `/admin/` | → login | ❌ | parcial (sin usuarios) | ✅ |

---

## 4. Rutas principales

| URL | Vista | Acceso |
|---|---|---|
| `/` | HomeView | público |
| `/catalogo/` | ProductoListView (`?q=`, `?categoria=`, `?orden=`, `?page=`) | público |
| `/catalogo/producto/<pk>/` | ProductoDetailView | público |
| `/pedidos/carrito/` | carrito_detalle | público |
| `/pedidos/checkout/` → `/pedidos/checkout/confirmar/` | CheckoutView → ConfirmarPedidoView | autenticado |
| `/pedidos/mis-pedidos/`, `/pedidos/<pk>/` | historial y detalle | autenticado (dueño) |
| `/cuenta/registro/`, `/cuenta/ingresar/`, `/cuenta/perfil/` | usuarios | — |
| `/panel/` | PanelView | Admin, Empleado |
| `/catalogo/gestion/productos/`, `/catalogo/gestion/categorias/` | CRUD | Admin, Empleado |
| `/pedidos/gestion/` | PedidoGestionListView | Admin, Empleado |
| `/pedidos/reportes/` | reportes | Admin |
| `/cuenta/gestion/` | usuarios y roles | Admin |
| `/admin/` | Admin de Django personalizado | personal |

---

## 5. Producción

En el `.env` del servidor:

```
DEBUG=False
ALLOWED_HOSTS=midominio.com
HTTPS=True
SERVIR_MEDIA=False     # las imágenes las sirve Nginx/Apache
DB_ENGINE=postgresql   (y los datos DB_*)
```

Luego ejecutar `pip install "psycopg[binary]"`, `python manage.py collectstatic` y
`python manage.py check --deploy`.
