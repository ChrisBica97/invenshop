"""
Pruebas automáticas de InvenShop.  Ejecutar:  python manage.py test -v 2

Cubren las reglas de negocio de la consigna: registro, login por rol,
permisos (403 / login), catálogo (filtros, agotados, inactivos), carrito
(validación de stock), checkout (transacción y descuento de stock),
estados del pedido (reposición al cancelar) y consultas sin N+1.
"""
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from catalogo.models import Categoria, Producto
from pedidos.models import DetallePedido, Pedido
from usuarios.models import Usuario

PWD = "ClaveSegura2026!"


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user("admin@t.com", PWD, nombre="Ana", apellido="Admin", rol="Admin")
        cls.empleado = Usuario.objects.create_user("emp@t.com", PWD, nombre="Eva", apellido="Emp", rol="Empleado")
        cls.cliente = Usuario.objects.create_user("cli@t.com", PWD, nombre="Carlos", apellido="Cli")
        cls.otro = Usuario.objects.create_user("otro@t.com", PWD, nombre="Otro", apellido="Cli")
        cls.cat = Categoria.objects.create(nombre="Electrónica")
        cls.cat2 = Categoria.objects.create(nombre="Hogar")
        cls.mouse = Producto.objects.create(nombre="Mouse", descripcion="inalámbrico", precio=Decimal("100"), stock=5, categoria=cls.cat)
        cls.teclado = Producto.objects.create(nombre="Teclado", descripcion="mecánico", precio=Decimal("300"), stock=2, categoria=cls.cat)
        cls.agotado = Producto.objects.create(nombre="Cargador", descripcion="usb", precio=Decimal("50"), stock=0, categoria=cls.cat)
        cls.inactivo = Producto.objects.create(nombre="Oculto", descripcion="x", precio=Decimal("10"), stock=9, categoria=cls.cat2, activo=False)
        cls.lampara = Producto.objects.create(nombre="Lámpara", descripcion="mouse pad incluido", precio=Decimal("200"), stock=9, categoria=cls.cat2)

    def entrar(self, user):
        self.client.force_login(user)


# ---------------------------------------------------------------------------
# 5.1 Usuarios y autenticación
# ---------------------------------------------------------------------------
class UsuariosTests(BaseTest):
    def test_registro_crea_cliente_y_loguea(self):
        r = self.client.post(reverse("usuarios:registro"), {
            "email": "Nuevo@Mail.com", "nombre": "juan", "apellido": "pérez", "telefono": "381 4567890",
            "password1": PWD, "password2": PWD,
        })
        self.assertRedirects(r, reverse("catalogo:lista"))
        u = Usuario.objects.get(email="nuevo@mail.com")
        self.assertEqual(u.rol, Usuario.Rol.CLIENTE)
        self.assertEqual(u.nombre, "Juan")
        self.assertTrue(u.groups.filter(name="Cliente").exists())
        self.assertEqual(int(self.client.session["_auth_user_id"]), u.pk)

    def test_registro_email_duplicado_y_password_debil(self):
        r = self.client.post(reverse("usuarios:registro"), {
            "email": "CLI@t.com", "nombre": "a", "apellido": "b", "telefono": "381 4567890",
            "password1": "12345678", "password2": "12345678",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("email", r.context["form"].errors)
        self.assertIn("password2", r.context["form"].errors)  # validadores de Django

    def test_login_redirige_segun_rol(self):
        r = self.client.post(reverse("usuarios:login"), {"username": "CLI@t.com", "password": PWD})
        self.assertRedirects(r, reverse("catalogo:lista"))
        self.client.logout()
        r = self.client.post(reverse("usuarios:login"), {"username": "emp@t.com", "password": PWD})
        self.assertRedirects(r, reverse("core:panel"))

    def test_login_credenciales_invalidas(self):
        r = self.client.post(reverse("usuarios:login"), {"username": "cli@t.com", "password": "mal"})
        self.assertContains(r, "Email o contraseña incorrectos")

    def test_perfil_solo_edita_el_propio_y_no_el_rol(self):
        self.entrar(self.cliente)
        r = self.client.post(reverse("usuarios:perfil"), {"nombre": "Carlitos", "apellido": "Cli", "telefono": "381 1111111", "rol": "Admin"})
        self.assertRedirects(r, reverse("usuarios:perfil"))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nombre, "Carlitos")
        self.assertEqual(self.cliente.rol, "Cliente")  # el campo rol se ignora

    def test_roles_sincronizan_grupo_y_staff(self):
        self.assertTrue(self.empleado.is_staff)
        self.assertFalse(self.cliente.is_staff)
        self.assertTrue(self.empleado.has_perm("catalogo.change_producto"))
        self.assertFalse(self.empleado.has_perm("usuarios.change_usuario"))
        self.assertTrue(self.admin.has_perm("pedidos.ver_reportes"))


class PermisosTests(BaseTest):
    def test_anonimo_va_al_login(self):
        for nombre in ["core:panel", "catalogo:gestion_productos", "pedidos:checkout", "pedidos:mis_pedidos", "pedidos:reportes"]:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn(reverse("usuarios:login"), r["Location"])

    def test_cliente_recibe_403_en_gestion(self):
        self.entrar(self.cliente)
        for nombre in ["core:panel", "catalogo:gestion_productos", "catalogo:producto_crear", "pedidos:gestion", "pedidos:reportes", "usuarios:lista"]:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_empleado_sin_acceso_a_usuarios_ni_reportes(self):
        self.entrar(self.empleado)
        self.assertEqual(self.client.get(reverse("catalogo:gestion_productos")).status_code, 200)
        self.assertEqual(self.client.get(reverse("usuarios:lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("pedidos:reportes")).status_code, 403)

    def test_admin_cambia_rol(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("usuarios:editar_rol", args=[self.otro.pk]), {"rol": "Empleado", "is_active": "on"})
        self.assertRedirects(r, reverse("usuarios:lista"))
        self.otro.refresh_from_db()
        self.assertTrue(self.otro.has_perm("catalogo.add_producto"))


# ---------------------------------------------------------------------------
# 5.2 Catálogo
# ---------------------------------------------------------------------------
class CatalogoTests(BaseTest):
    def test_solo_activos_y_busqueda_combinada(self):
        r = self.client.get(reverse("catalogo:lista"))
        nombres = {p.nombre for p in r.context["productos"]}
        self.assertNotIn("Oculto", nombres)
        self.assertIn("Cargador", nombres)  # agotado SÍ se muestra (señalado)
        # "mouse" está en el nombre de Mouse y en la descripción de Lámpara
        r = self.client.get(reverse("catalogo:lista"), {"q": "mouse"})
        self.assertEqual({p.nombre for p in r.context["productos"]}, {"Mouse", "Lámpara"})
        # combinada con la categoría
        r = self.client.get(reverse("catalogo:lista"), {"q": "mouse", "categoria": self.cat2.slug})
        self.assertEqual([p.nombre for p in r.context["productos"]], ["Lámpara"])

    def test_ordenamiento_por_precio(self):
        r = self.client.get(reverse("catalogo:lista"), {"orden": "-precio"})
        precios = [p.precio for p in r.context["productos"]]
        self.assertEqual(precios, sorted(precios, reverse=True))

    def test_paginacion_12(self):
        for i in range(15):
            Producto.objects.create(nombre=f"P{i}", descripcion="x", precio=1, stock=1, categoria=self.cat)
        r = self.client.get(reverse("catalogo:lista"))
        self.assertEqual(len(r.context["productos"]), 12)

    def test_detalle_de_inactivo_da_404(self):
        self.assertEqual(self.client.get(reverse("catalogo:detalle", args=[self.inactivo.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse("catalogo:detalle", args=[self.agotado.pk])), "Agotado")

    def test_listado_sin_n_mas_1(self):
        """Con 5 o con 25 productos, la cantidad de queries es la misma (select_related)."""
        with self.assertNumQueries(3):  # count de paginación + productos + categorías
            self.client.get(reverse("catalogo:lista"))
        for i in range(20):
            Producto.objects.create(nombre=f"X{i}", descripcion="x", precio=1, stock=1, categoria=self.cat2)
        with self.assertNumQueries(3):
            self.client.get(reverse("catalogo:lista"))

    def test_empleado_crea_producto_con_validaciones(self):
        self.entrar(self.empleado)
        datos = {"nombre": "mouse", "categoria": self.cat.pk, "descripcion": "dup", "precio": "0", "stock": "0", "activo": "on"}
        r = self.client.post(reverse("catalogo:producto_crear"), datos)
        errores = r.context["form"].errors
        self.assertIn("nombre", errores)   # duplicado en la categoría (sin importar mayúsculas)
        self.assertIn("precio", errores)   # debe ser > 0
        self.assertIn("stock", errores)    # nuevo activo sin stock
        datos.update(nombre="Pad", precio="10", stock="3")
        self.assertRedirects(self.client.post(reverse("catalogo:producto_crear"), datos), reverse("catalogo:gestion_productos"))


# ---------------------------------------------------------------------------
# 5.2 Carrito en sesión
# ---------------------------------------------------------------------------
class CarritoTests(BaseTest):
    def agregar(self, producto, cantidad):
        return self.client.post(reverse("pedidos:carrito_agregar", args=[producto.pk]), {"cantidad": cantidad})

    def test_agregar_modificar_quitar_vaciar(self):
        self.agregar(self.mouse, 2)
        self.agregar(self.mouse, 1)
        self.agregar(self.teclado, 1)
        self.assertEqual(self.client.session["carrito"], {str(self.mouse.pk): 3, str(self.teclado.pk): 1})
        r = self.client.get(reverse("pedidos:carrito"))
        self.assertEqual(r.context["total"], Decimal("600"))  # 3*100 + 1*300
        self.client.post(reverse("pedidos:carrito_actualizar", args=[self.mouse.pk]), {"cantidad": 1})
        self.client.post(reverse("pedidos:carrito_quitar", args=[self.teclado.pk]))
        self.assertEqual(self.client.session["carrito"], {str(self.mouse.pk): 1})
        self.client.post(reverse("pedidos:carrito_vaciar"))
        self.assertEqual(self.client.session["carrito"], {})

    def test_no_supera_stock_ni_agrega_agotados(self):
        self.agregar(self.teclado, 3)  # stock 2
        self.agregar(self.agotado, 1)
        self.assertEqual(self.client.session.get("carrito", {}), {})
        r = self.client.get(reverse("pedidos:carrito"))
        self.assertEqual(len(r.context["items"]), 0)

    def test_carrito_no_acepta_get(self):
        r = self.client.get(reverse("pedidos:carrito_agregar", args=[self.mouse.pk]))
        self.assertEqual(r.status_code, 405)  # @require_POST


# ---------------------------------------------------------------------------
# 5.3 Checkout y pedidos
# ---------------------------------------------------------------------------
ENVIO = {"direccion": "San Martín 123", "ciudad": "tucumán", "codigo_postal": "t4000abc", "telefono_contacto": "381 4567890"}


class PedidosTests(BaseTest):
    def comprar(self):
        self.entrar(self.cliente)
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.mouse.pk]), {"cantidad": 2})
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.teclado.pk]), {"cantidad": 1})
        r = self.client.post(reverse("pedidos:checkout"), ENVIO)
        self.assertRedirects(r, reverse("pedidos:confirmar"))
        return self.client.post(reverse("pedidos:confirmar"), {"acepto": "on"})

    def test_checkout_completo(self):
        r = self.comprar()
        pedido = Pedido.objects.get()
        self.assertRedirects(r, pedido.get_absolute_url())
        self.assertEqual(pedido.total, Decimal("500"))
        self.assertEqual(pedido.estado, "Pendiente")
        self.assertEqual(pedido.codigo_postal, "T4000ABC")
        self.assertEqual(pedido.ciudad, "Tucumán")
        self.mouse.refresh_from_db()
        self.teclado.refresh_from_db()
        self.assertEqual((self.mouse.stock, self.teclado.stock), (3, 1))  # stock descontado
        self.assertEqual(self.client.session["carrito"], {})               # carrito vaciado

    def test_validaciones_de_envio(self):
        self.entrar(self.cliente)
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.mouse.pk]), {"cantidad": 1})
        r = self.client.post(reverse("pedidos:checkout"), {"direccion": "Calle sin numero", "ciudad": "123", "codigo_postal": "12", "telefono_contacto": "abc"})
        self.assertEqual(set(r.context["form"].errors), {"direccion", "ciudad", "codigo_postal", "telefono_contacto"})

    def test_confirmacion_obligatoria(self):
        self.entrar(self.cliente)
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.mouse.pk]), {"cantidad": 1})
        self.client.post(reverse("pedidos:checkout"), ENVIO)
        r = self.client.post(reverse("pedidos:confirmar"), {})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Pedido.objects.exists())

    def test_stock_cambia_entre_carrito_y_confirmacion(self):
        """Si otro compra antes, la transacción se aborta sin dejar nada a medias."""
        self.entrar(self.cliente)
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.teclado.pk]), {"cantidad": 2})
        self.client.post(reverse("pedidos:checkout"), ENVIO)
        Producto.objects.filter(pk=self.teclado.pk).update(stock=1)
        r = self.client.post(reverse("pedidos:confirmar"), {"acepto": "on"})
        self.assertRedirects(r, reverse("pedidos:carrito"))
        self.assertFalse(Pedido.objects.exists())

    def test_choque_de_compras_no_rompe_el_checkout(self):
        """La base rechaza stock negativo y la vista lo informa como falta de stock (sin error 500)."""
        # 1) Última barrera: el CHECK stock >= 0 de PositiveIntegerField
        with self.assertRaises(IntegrityError), transaction.atomic():
            Producto.objects.filter(pk=self.teclado.pk).update(stock=F("stock") - 100)
        # 2) Si ese error ocurre al confirmar, el cliente vuelve al carrito con un mensaje
        self.entrar(self.cliente)
        self.client.post(reverse("pedidos:carrito_agregar", args=[self.teclado.pk]), {"cantidad": 1})
        self.client.post(reverse("pedidos:checkout"), ENVIO)
        with mock.patch("pedidos.views.crear_pedido", side_effect=IntegrityError):
            r = self.client.post(reverse("pedidos:confirmar"), {"acepto": "on"}, follow=True)
        self.assertRedirects(r, reverse("pedidos:carrito"))
        self.assertContains(r, "otro cliente compró las últimas unidades")
        self.assertFalse(Pedido.objects.exists())

    def test_cliente_solo_ve_sus_pedidos(self):
        self.comprar()
        pedido = Pedido.objects.get()
        self.entrar(self.otro)
        self.assertEqual(self.client.get(pedido.get_absolute_url()).status_code, 404)
        self.assertEqual(len(self.client.get(reverse("pedidos:mis_pedidos")).context["pedidos"]), 0)
        self.entrar(self.empleado)
        self.assertEqual(self.client.get(pedido.get_absolute_url()).status_code, 200)

    def test_detalle_pedido_sin_n_mas_1(self):
        """La cantidad de queries NO crece con la cantidad de productos del pedido."""
        self.comprar()  # pedido con 2 productos
        chico = Pedido.objects.get()
        grande = Pedido.objects.create(usuario=self.cliente, **ENVIO)
        for p in Producto.objects.all():  # pedido con 5 productos
            DetallePedido.objects.create(pedido=grande, producto=p, cantidad=1, precio_unitario=p.precio)

        def contar(pedido):
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(pedido.get_absolute_url())
            return len(ctx.captured_queries)

        self.assertEqual(contar(chico), contar(grande))

    def test_estados_y_reposicion_de_stock(self):
        self.comprar()
        pedido = Pedido.objects.get()
        url = reverse("pedidos:cambiar_estado", args=[pedido.pk])
        # Cliente no puede cambiar estados
        self.assertEqual(self.client.post(url, {"estado": "Pagado"}).status_code, 403)
        self.entrar(self.empleado)
        self.client.post(url, {"estado": "Pagado"})
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "Pagado")
        # Transición inválida: Pagado -> Pendiente
        self.client.post(url, {"estado": "Pendiente"})
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, "Pagado")
        # Cancelar repone el stock
        self.client.post(url, {"estado": "Cancelado"})
        self.mouse.refresh_from_db()
        self.teclado.refresh_from_db()
        self.assertEqual((self.mouse.stock, self.teclado.stock), (5, 2))

    def test_producto_vendido_no_se_borra_se_desactiva(self):
        self.comprar()
        self.entrar(self.admin)
        self.client.post(reverse("catalogo:producto_eliminar", args=[self.mouse.pk]))
        self.mouse.refresh_from_db()
        self.assertFalse(self.mouse.activo)
        self.assertTrue(DetallePedido.objects.filter(producto=self.mouse).exists())

    def test_reportes_admin(self):
        self.comprar()
        self.entrar(self.admin)
        r = self.client.get(reverse("pedidos:reportes"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["mas_vendidos"][0]["producto__nombre"], "Mouse")


# ---------------------------------------------------------------------------
# Imágenes de productos
# ---------------------------------------------------------------------------
import io
import shutil
import tempfile

from django.core.management import call_command
from django.test import override_settings

MEDIA_TEMPORAL = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class ImagenesTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)
        super().tearDownClass()

    def test_cargar_demo_asigna_imagen_a_todos_los_productos(self):
        call_command("cargar_demo", sin_internet=True, stdout=io.StringIO())
        sin_imagen = [p.nombre for p in Producto.objects.all() if not p.imagen_disponible]
        self.assertEqual(sin_imagen, [])

    @override_settings(DEBUG=False)
    def test_imagenes_se_sirven_aunque_debug_sea_false(self):
        call_command("cargar_demo", sin_internet=True, stdout=io.StringIO())
        p = Producto.objects.first()
        r = self.client.get(p.imagen.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/jpeg")

    def test_sin_archivo_muestra_reemplazo_y_no_imagen_rota(self):
        cat = Categoria.objects.create(nombre="Varios")
        Producto.objects.create(nombre="Sin foto", descripcion="x", precio=1, stock=1, categoria=cat,
                                imagen="productos/no-existe.jpg")
        html = self.client.get(reverse("catalogo:lista")).content.decode()
        self.assertNotIn("no-existe.jpg", html)
        self.assertIn("SF", html)  # iniciales en el reemplazo



# ---------------------------------------------------------------------------
# Descarga de fotos reales desde Wikimedia Commons (red SIMULADA con mock)
# ---------------------------------------------------------------------------
import json
from unittest import mock

from PIL import Image

from core.management.commands import descargar_imagenes as cmd


def _jpeg_falso(ancho=1200, alto=900):
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), "red").save(buf, "JPEG")
    return buf.getvalue()


def _respuesta_api(titulo, existe=True):
    """Imita el JSON real de action=query&prop=imageinfo de la API de Commons."""
    if not existe:
        return json.dumps({"query": {"pages": {"-1": {"ns": 6, "title": titulo, "missing": ""}}}}).encode()
    return json.dumps({"query": {"pages": {"123": {"title": titulo, "index": 1, "imageinfo": [{
        "url": "https://upload.wikimedia.org/original.jpg",
        "thumburl": "https://upload.wikimedia.org/thumb/800px.jpg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/" + titulo.replace(" ", "_"),
        "mime": "image/jpeg",
        "extmetadata": {
            "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:Ana">Ana &amp; Co</a>'},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
        },
    }]}}}}).encode()


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class DescargarImagenesTests(TestCase):
    def setUp(self):
        cat = Categoria.objects.create(nombre="Electrónica")
        self.mouse = Producto.objects.create(nombre="Mouse inalámbrico", descripcion="x", precio=1, stock=1, categoria=cat)
        self.banda = Producto.objects.create(nombre="Banda elástica de resistencia", descripcion="x", precio=1, stock=1, categoria=cat)

    def red_simulada(self, url, params=None):
        if "upload.wikimedia.org" in url:
            return _jpeg_falso()
        if params and "titles" in params:
            # El primer archivo preferido "no existe": obliga a probar el siguiente
            return _respuesta_api(params["titles"], existe=params["titles"] != "File:A_wireless_computer_mouse.jpg")
        return _respuesta_api("File:Resistance band.jpg")  # búsqueda de respaldo

    def test_descarga_foto_con_credito(self):
        with mock.patch.object(cmd, "_get", side_effect=self.red_simulada):
            call_command("descargar_imagenes", stdout=io.StringIO())
        self.mouse.refresh_from_db()
        self.assertTrue(self.mouse.imagen_disponible)
        self.assertEqual(self.mouse.imagen_credito, "Ana & Co · CC BY-SA 4.0 · Wikimedia Commons")  # sin HTML
        self.assertIn("Wireless_mouse.jpg", self.mouse.imagen_fuente)  # usó el 2° archivo
        with Image.open(self.mouse.imagen.path) as img:
            self.assertEqual(img.size, (800, 600))  # normalizada a 4:3
        # La banda no tiene archivos preferidos: usa la búsqueda de respaldo
        self.banda.refresh_from_db()
        self.assertIn("Resistance_band.jpg", self.banda.imagen_fuente)
        # El crédito se muestra en la ficha del producto
        self.assertContains(self.client.get(self.mouse.get_absolute_url()), "Ana &amp; Co · CC BY-SA 4.0")

    def test_sin_internet_no_rompe(self):
        with mock.patch.object(cmd, "_get", side_effect=cmd.SinConexion("sin red")):
            salida = io.StringIO()
            call_command("descargar_imagenes", stdout=salida)
        self.assertIn("No hay conexión", salida.getvalue())
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.imagen_fuente, "")

    def test_no_vuelve_a_descargar_si_ya_tiene_foto(self):
        with mock.patch.object(cmd, "_get", side_effect=self.red_simulada):
            call_command("descargar_imagenes", stdout=io.StringIO())
        with mock.patch.object(cmd, "_get", side_effect=AssertionError("no debería usar la red")):
            salida = io.StringIO()
            call_command("descargar_imagenes", stdout=salida)
        self.assertIn("0 descargadas, 2 ya estaban", salida.getvalue())
