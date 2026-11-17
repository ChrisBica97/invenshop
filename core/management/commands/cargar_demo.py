"""
Comando: python manage.py cargar_demo

Carga datos de ejemplo para probar el sistema:
  * 3 usuarios (uno por rol) con contraseña conocida.
  * Categorías y productos, con imágenes incluidas en core/demo_imagenes/.
  * Algunos pedidos en distintos estados.

Al final intenta descargar FOTOS REALES de Wikimedia Commons (comando
descargar_imagenes). Sin internet, quedan las ilustraciones incluidas.

Opciones:
  --imagenes       vuelve a copiar las ilustraciones aunque el producto ya
                   tenga imagen (útil si se borró la carpeta media/).
  --sin-internet   no intenta descargar las fotos reales.
Se puede ejecutar varias veces: no duplica datos.
"""
from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalogo.models import Categoria, Producto
from pedidos.models import DetallePedido, Pedido
from usuarios.models import Usuario
from usuarios.roles import sincronizar_grupos

PASSWORD_DEMO = "InvenShop2026!"

USUARIOS = [
    ("admin@invenshop.com", "Ana", "Administradora", Usuario.Rol.ADMIN),
    ("empleado@invenshop.com", "Esteban", "Empleado", Usuario.Rol.EMPLEADO),
    ("cliente@invenshop.com", "Carla", "Cliente", Usuario.Rol.CLIENTE),
    ("cliente2@invenshop.com", "Diego", "Comprador", Usuario.Rol.CLIENTE),
]

CATALOGO = {
    ("Electrónica", "#2563eb"): [
        ("Auriculares Bluetooth", "Auriculares inalámbricos con cancelación de ruido y 30 h de batería.", "45999", 25),
        ("Mouse inalámbrico", "Mouse ergonómico 2.4 GHz, 1600 DPI, silencioso.", "12500", 40),
        ("Teclado mecánico", "Teclado mecánico con switches rojos y retroiluminación RGB.", "68900", 8),
        ("Parlante portátil", "Parlante resistente al agua IPX7, 12 h de autonomía.", "38750", 3),
        ("Cargador USB-C 65W", "Cargador rápido GaN compatible con notebooks y celulares.", "21999", 0),
        ("Webcam Full HD", "Cámara 1080p con micrófono incorporado para videollamadas.", "29990", 15),
    ],
    ("Hogar", "#16a34a"): [
        ("Lámpara de escritorio LED", "Lámpara regulable con 3 temperaturas de color.", "18900", 20),
        ("Juego de sábanas 2 plazas", "100% algodón, 180 hilos.", "32000", 12),
        ("Cafetera de filtro", "Cafetera de 1,2 L con jarra de vidrio y función mantener caliente.", "41500", 6),
        ("Set de ollas antiadherentes", "5 piezas con tapas de vidrio templado.", "89900", 4),
        ("Organizador de cajones", "Set de 6 cajas plásticas apilables.", "8500", 50),
    ],
    ("Librería", "#ea580c"): [
        ("Cuaderno universitario A4", "84 hojas rayadas, tapa dura.", "3200", 100),
        ("Set de resaltadores", "6 colores pastel, punta biselada.", "4800", 60),
        ("Mochila para notebook", "Hasta 15,6\", con puerto USB y compartimento acolchado.", "54000", 10),
        ("Agenda 2027", "Agenda semanal con tapa de cuero sintético.", "11900", 30),
    ],
    ("Deportes", "#9333ea"): [
        ("Pelota de fútbol N°5", "Pelota cosida a mano, apta para césped.", "24500", 18),
        ("Mat de yoga", "Colchoneta antideslizante de 6 mm.", "15990", 22),
        ("Botella térmica 1L", "Acero inoxidable, mantiene 24 h frío / 12 h caliente.", "19900", 0),
        ("Banda elástica de resistencia", "Set de 5 bandas con distintas resistencias.", "9900", 35),
    ],
}


# Imágenes de los productos de demo (una por producto, nombre = slug del producto)
CARPETA_IMAGENES = Path(__file__).resolve().parents[2] / "demo_imagenes"


def asignar_imagen(producto, forzar=False):
    """
    Copia la imagen de demo correspondiente a media/productos/.
    Se asigna si el producto no tiene imagen, si el archivo se perdió
    (por ejemplo, se borró la carpeta media/) o si se pidió --imagenes.
    """
    origen = CARPETA_IMAGENES / f"{slugify(producto.nombre)}.jpg"
    if not origen.exists():
        return False
    if producto.imagen_fuente and not forzar:
        return False  # ya tiene una foto real descargada
    archivo_falta = bool(producto.imagen) and not producto.imagen.storage.exists(producto.imagen.name)
    if producto.imagen and not archivo_falta and not forzar:
        return False
    with origen.open("rb") as f:
        producto.imagen.save(origen.name, File(f), save=False)
    producto.imagen_credito = producto.imagen_fuente = ""  # ilustración propia: sin créditos
    producto.save()
    return True


class Command(BaseCommand):
    help = "Carga usuarios, catálogo y pedidos de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--imagenes", action="store_true", help="Vuelve a copiar las ilustraciones de demo.")
        parser.add_argument("--sin-internet", action="store_true", help="No descargar fotos reales de Commons.")

    def handle(self, *args, **options):
        self.cargar_datos(options)  # usuarios, catálogo y pedidos (en una transacción)

        # 4) Fotos reales desde Wikimedia Commons. Va FUERA de la transacción:
        #    la descarga puede tardar y, si falla la red, los datos ya quedan cargados.
        if not options["sin_internet"]:
            self.stdout.write("Descargando fotos reales desde Wikimedia Commons...")
            call_command("descargar_imagenes", forzar=options["imagenes"], stdout=self.stdout)

    @transaction.atomic
    def cargar_datos(self, options):
        sincronizar_grupos()

        # 1) Usuarios
        usuarios = {}
        for email, nombre, apellido, rol in USUARIOS:
            u, creado = Usuario.objects.get_or_create(
                email=email, defaults={"nombre": nombre, "apellido": apellido, "rol": rol, "telefono": "381 555-1234"}
            )
            if creado:
                u.set_password(PASSWORD_DEMO)
                u.save()
            usuarios[email] = u
        self.stdout.write(self.style.SUCCESS(f"Usuarios listos (contraseña: {PASSWORD_DEMO})"))

        # 2) Catálogo
        productos, imagenes = {}, 0
        for (nombre_cat, _color), items in CATALOGO.items():
            cat, _ = Categoria.objects.get_or_create(
                nombre=nombre_cat, defaults={"descripcion": f"Productos de {nombre_cat.lower()}."}
            )
            for nombre, desc, precio, stock in items:
                p, creado = Producto.objects.get_or_create(
                    nombre=nombre, categoria=cat,
                    defaults={"descripcion": desc, "precio": Decimal(precio), "stock": stock},
                )
                imagenes += asignar_imagen(p, forzar=options["imagenes"])
                productos[nombre] = p
        # Un producto inactivo, para verificar que NO aparece en el catálogo
        Producto.objects.filter(nombre="Organizador de cajones").update(activo=False)
        self.stdout.write(self.style.SUCCESS(
            f"Catálogo listo: {Producto.objects.count()} productos ({imagenes} imágenes copiadas a media/productos/)"
        ))

        # 3) Pedidos de ejemplo (solo si todavía no hay)
        if not Pedido.objects.exists():
            cliente = usuarios["cliente@invenshop.com"]
            cliente2 = usuarios["cliente2@invenshop.com"]
            ejemplos = [
                (cliente, Pedido.Estado.ENVIADO, [("Mouse inalámbrico", 2), ("Cuaderno universitario A4", 5)]),
                (cliente, Pedido.Estado.PAGADO, [("Auriculares Bluetooth", 1)]),
                (cliente, Pedido.Estado.PENDIENTE, [("Mat de yoga", 1), ("Banda elástica de resistencia", 2)]),
                (cliente2, Pedido.Estado.PENDIENTE, [("Lámpara de escritorio LED", 1)]),
                (cliente2, Pedido.Estado.CANCELADO, [("Pelota de fútbol N°5", 1)]),
            ]
            for usuario, estado, lineas in ejemplos:
                pedido = Pedido.objects.create(
                    usuario=usuario, estado=estado, direccion="San Martín 123",
                    ciudad="San Miguel De Tucumán", codigo_postal="4000", telefono_contacto="381 555-1234",
                )
                total = Decimal("0")
                for nombre, cant in lineas:
                    p = productos[nombre]
                    DetallePedido.objects.create(pedido=pedido, producto=p, cantidad=cant, precio_unitario=p.precio)
                    total += p.precio * cant
                pedido.total = total
                pedido.save(update_fields=["total"])
            self.stdout.write(self.style.SUCCESS(f"Pedidos de ejemplo: {Pedido.objects.count()}"))
