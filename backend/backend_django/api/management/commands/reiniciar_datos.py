"""Borra todo el movimiento (clientes, solicitudes, cotizaciones, pagos,
órdenes, despachos y sus PDF) y deja lo de configuración: usuarios, firmas,
plantas, materiales, precios y disponibilidad.

    python manage.py reiniciar_datos          # pregunta antes de borrar
    python manage.py reiniciar_datos --si     # sin preguntar

Los consecutivos (SC-, OS-, REM-, VIN-, COT) vuelven a empezar porque se
calculan contando filas.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    Cliente, ClienteToken, SolicitudToken, SolicitudCotizacion, Seguimiento,
    Cotizacion, Pago, OrdenSuministro, Despacho,
)


class Command(BaseCommand):
    help = "Borra clientes, solicitudes, cotizaciones, pagos, órdenes y despachos. Conserva usuarios y catálogo."

    def add_arguments(self, parser):
        parser.add_argument("--si", action="store_true", help="No pedir confirmación")

    def handle(self, si, **opts):
        conteo = {
            "clientes": Cliente.objects.count(),
            "solicitudes": SolicitudCotizacion.objects.count(),
            "cotizaciones": Cotizacion.objects.count(),
            "pagos": Pago.objects.count(),
            "órdenes de suministro": OrdenSuministro.objects.count(),
            "despachos": Despacho.objects.count(),
        }
        self.stdout.write("Se va a borrar:")
        for k, v in conteo.items():
            self.stdout.write(f"  {v:>5}  {k}")
        self.stdout.write("Se conservan usuarios, firmas, plantas, materiales, precios y disponibilidad.")
        if not si and input("Escribe BORRAR para continuar: ").strip() != "BORRAR":
            self.stdout.write("Cancelado.")
            return

        with transaction.atomic():
            # De las hojas hacia la raíz: los PROTECT de materiales/plantas no estorban.
            Despacho.objects.all().delete()
            OrdenSuministro.objects.all().delete()
            Pago.objects.all().delete()
            Cotizacion.objects.all().delete()
            Seguimiento.objects.all().delete()
            SolicitudCotizacion.objects.all().delete()
            SolicitudToken.objects.all().delete()
            ClienteToken.objects.all().delete()
            Cliente.objects.all().delete()

        # Solo los archivos de movimiento; las firmas (uploads/firmas) se quedan.
        for carpeta in (settings.GENERATED_PDF_DIR, settings.UPLOAD_DIR / "comprobantes",
                        settings.UPLOAD_DIR / "soportes_despacho"):
            if not carpeta.exists():
                continue
            for archivo in carpeta.iterdir():
                if archivo.is_file() and not archivo.name.startswith("."):
                    archivo.unlink()

        self.stdout.write(self.style.SUCCESS("Listo: datos de movimiento borrados."))
