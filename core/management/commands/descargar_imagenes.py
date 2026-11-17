"""
Comando: python manage.py descargar_imagenes

Descarga FOTOS REALES de los productos desde Wikimedia Commons
(https://commons.wikimedia.org), el banco de imágenes libres de Wikipedia.

  * Todas las imágenes de Commons tienen licencia libre (dominio público,
    CC0, CC BY o CC BY-SA). Varias licencias exigen CITAR AL AUTOR: por eso
    se guardan el autor, la licencia y el enlace en cada producto
    (campos imagen_credito e imagen_fuente) y se muestran en la ficha.
  * Se ejecuta en TU computadora (necesita internet). Si no hay conexión,
    el producto conserva la ilustración incluida en el proyecto.

Opciones:
  --forzar     vuelve a descargar aunque el producto ya tenga una foto real.
  --todos      también busca fotos para productos que NO son de la demo
               (usa el nombre del producto como búsqueda).

Cómo elige la foto de cada producto:
  1) Prueba, en orden, los archivos de Commons elegidos para ese producto.
  2) Si ninguno está disponible, busca en Commons con una frase en inglés.
"""
import io
import json
import ssl
import re
import urllib.error
import urllib.parse
import urllib.request
from html import unescape

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageOps

from catalogo.models import Producto

API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia pide identificar el programa que descarga (política de User-Agent)
USER_AGENT = "InvenShop/1.0 (trabajo practico educativo con Django; python-urllib)"
ANCHO = 960          # ancho pedido a Commons (960 es uno de sus tamaños estándar de miniatura)
TIEMPO_MAX = 20      # segundos de espera por pedido

# Producto de la demo -> (archivos de Commons preferidos, búsqueda de respaldo)
FOTOS = {
    "Auriculares Bluetooth": (["Headphones_1.jpg", "Headphones.jpg", "Philips-headphones.JPG"], "headphones"),
    "Mouse inalámbrico": (["A_wireless_computer_mouse.jpg", "Wireless_mouse.jpg", "A_black_wireless_computer_mouse.jpg"], "wireless computer mouse"),
    "Teclado mecánico": (["Keychron_K8_Non-Backlight_Wireless_Mechanical_Keyboard.jpg", "Mechanical_Logitech_keyboard.jpg", "Keychron_K4_mechanical_keyboard.jpg"], "mechanical keyboard"),
    "Parlante portátil": (["Bluetooth_Speaker.jpg", "Tribit_MaxBoom_Bluetooth_Speaker.jpg", "JBL_Flip_3_bluetooth_speaker_(DSCF2653).jpg"], "bluetooth speaker"),
    "Cargador USB-C 65W": (["Lazos_GaN_Charger_30W_L-AC-G30.jpg", "USB_wall_charger.JPG", "Charger.jpg"], "usb wall charger"),
    "Webcam Full HD": (["Webcam_(Logitech_c922).jpg", "Webcam.JPG", "Microsoft_LifeCam_VX-6000_Webcam_(Gray).jpg"], "webcam"),
    "Lámpara de escritorio LED": (["Concise_bamboo_eye_protection_LED_desk_lamp.jpg", "Battery_powered_LED_desk_lamp-7420.jpg", "Desk_lamp.jpg"], "LED desk lamp"),
    "Juego de sábanas 2 plazas": (["Colorful_Bed_sheets.jpg", "Bed_in_Seattle_hotel.jpg"], "bed sheets bedroom"),
    "Cafetera de filtro": (["Coffee_machine.jpg", "Wigomat-100.jpg"], "drip coffee maker"),
    "Set de ollas antiadherentes": (["Hahn_Stainless_Pan_Range.jpg", "Non-stick_20cm_saucepan.JPG", "Saucepan.jpg"], "cookware pots"),
    "Organizador de cajones": (["PP_box.jpg", "Blue_plastic_storage_organizer_boxes_for_screws.jpg"], "plastic storage box"),
    "Cuaderno universitario A4": (["Notebook.jpg", "Notebooks.jpg", "Blue-book-12-sheet.jpg"], "spiral notebook"),
    "Set de resaltadores": (["Highlighter.jpg", "Artful_highlighter_pens_drawing_on_paper.jpg"], "highlighter pens"),
    "Mochila para notebook": (["Backpack-1.jpg", "Backpack_Wikipedia.JPG", "Laptop_bag.jpg"], "backpack"),
    "Agenda 2027": (["Agenda.jpg"], "planner diary"),
    "Pelota de fútbol N°5": (["Soccerball.jpg", "Football_(Soccer).JPG", "Bola_de_futebol.jpg"], "soccer ball"),
    "Mat de yoga": (["Yoga_mat.jpg", "Coir_yoga_mat.jpg", "Gaim_Yoga_Mat_1_2019-05-15.jpg"], "yoga mat"),
    "Botella térmica 1L": (["Stainless_steel_water_bottle.jpg", "Niksun_stainless_steel_water_bottle.jpg"], "stainless steel water bottle"),
    "Banda elástica de resistencia": ([], "resistance band exercise"),
}


class SinConexion(Exception):
    """No se pudo llegar a Wikimedia Commons."""


def _contexto_ssl():
    """Usa los certificados de certifi si está instalado (evita errores SSL en algunos Mac)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get(url, params=None):
    """GET con User-Agent; devuelve bytes. Convierte fallas de red en SinConexion."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(pedido, timeout=TIEMPO_MAX, context=_contexto_ssl()) as respuesta:
            return respuesta.read()
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SinConexion(str(getattr(e, "reason", e))) from e


def _texto_plano(html):
    """El autor viene en HTML (<a href=...>Nombre</a>): se deja solo el texto."""
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())


def _info_de(paginas):
    """Del JSON de la API devuelve la primera imagen JPG/PNG utilizable."""
    for pagina in paginas:
        info = (pagina.get("imageinfo") or [None])[0]
        if not info or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        meta = info.get("extmetadata", {})
        autor = _texto_plano(meta.get("Artist", {}).get("value")) or "Autor desconocido"
        licencia = _texto_plano(meta.get("LicenseShortName", {}).get("value")) or "Licencia libre"
        return {
            "url": info.get("thumburl") or info["url"],
            "credito": f"{autor[:150]} · {licencia} · Wikimedia Commons",
            "fuente": info.get("descriptionurl", ""),
        }
    return None


def buscar_foto(archivos, busqueda):
    """Prueba los archivos indicados y, si no hay ninguno, busca en Commons."""
    comunes = {"action": "query", "format": "json", "prop": "imageinfo",
               "iiprop": "url|mime|extmetadata", "iiurlwidth": ANCHO}
    for archivo in archivos:
        datos = json.loads(_get(API, {**comunes, "titles": f"File:{archivo}"}))
        encontrada = _info_de(datos.get("query", {}).get("pages", {}).values())
        if encontrada:
            return encontrada
    if busqueda:
        datos = json.loads(_get(API, {
            **comunes, "generator": "search", "gsrnamespace": 6, "gsrlimit": 8,
            "gsrsearch": f"filetype:bitmap {busqueda}",
        }))
        paginas = sorted(datos.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
        return _info_de(paginas)
    return None


def a_jpeg(contenido):
    """Valida que sea una imagen real y la normaliza a JPEG 800x600 (4:3), como las tarjetas."""
    img = Image.open(io.BytesIO(contenido))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (800, 600), method=Image.LANCZOS)
    salida = io.BytesIO()
    img.save(salida, "JPEG", quality=85, optimize=True)
    return salida.getvalue()


class Command(BaseCommand):
    help = "Descarga fotos reales de los productos desde Wikimedia Commons (requiere internet)."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Volver a descargar aunque ya tenga foto real.")
        parser.add_argument("--todos", action="store_true", help="Incluir productos que no son de la demo.")

    def handle(self, *args, forzar=False, todos=False, **options):
        productos = Producto.objects.all()
        if not todos:
            productos = productos.filter(nombre__in=FOTOS.keys())

        ok = omitidos = fallidos = 0
        for producto in productos:
            # imagen_fuente con valor = ya tiene una foto real descargada
            if producto.imagen_fuente and producto.imagen_disponible and not forzar:
                omitidos += 1
                continue
            archivos, busqueda = FOTOS.get(producto.nombre, ([], producto.nombre))
            try:
                foto = buscar_foto(archivos, busqueda)
                if not foto:
                    self.stdout.write(self.style.WARNING(f"  ✗ {producto.nombre}: sin resultados en Commons"))
                    fallidos += 1
                    continue
                contenido = a_jpeg(_get(foto["url"]))
            except SinConexion as e:
                ayuda = ""
                if "CERTIFICATE" in str(e).upper():
                    ayuda = ("\nEs un problema de certificados SSL de Python. Solución: "
                             "pip install certifi  (en Mac también: abrir 'Install Certificates.command' "
                             "en la carpeta de Python de Aplicaciones).")
                self.stdout.write(self.style.ERROR(
                    f"\nNo hay conexión con Wikimedia Commons ({e}).{ayuda}\n"
                    "Los productos conservan las ilustraciones incluidas. Cuando tengas internet, "
                    "ejecutá:  python manage.py descargar_imagenes"
                ))
                break
            except Exception as e:  # imagen dañada, respuesta inesperada, etc.: se sigue con el resto
                self.stdout.write(self.style.WARNING(f"  ✗ {producto.nombre}: {e}"))
                fallidos += 1
                continue

            producto.imagen.save(f"{slugify(producto.nombre)}-foto.jpg", ContentFile(contenido), save=False)
            producto.imagen_credito = foto["credito"]
            producto.imagen_fuente = foto["fuente"]
            producto.save(update_fields=["imagen", "imagen_credito", "imagen_fuente"])
            ok += 1
            self.stdout.write(f"  ✓ {producto.nombre}  ←  {foto['credito']}")

        self.stdout.write(self.style.SUCCESS(
            f"Fotos reales: {ok} descargadas, {omitidos} ya estaban, {fallidos} sin foto."
        ))
