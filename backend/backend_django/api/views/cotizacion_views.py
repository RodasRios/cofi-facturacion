import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import (
    Cotizacion, CotizacionItem, SolicitudCotizacion, Planta, Material, MaterialPlanta,
)
from api.serializers import CotizacionSerializer
from api.permissions import IsAprobador
from services.pdf_service import generate_cotizacion

logger = logging.getLogger(__name__)


def _numero_cotizacion():
    count = Cotizacion.objects.count()
    return f"COT-{count + 1:04d}"


def _pdf_items(cotizacion):
    return [
        {
            "material_nombre": i.material.nombre,
            "cantidad": i.cantidad,
            "unidad_medida": i.material.unidad_medida,
            "precio_unitario": i.precio_unitario,
        }
        for i in cotizacion.items.select_related("material")
    ]


def _generar_pdf(cotizacion, firma_path=None):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"COT_{cotizacion.id}_{cotizacion.numero.replace('-', '_')}.pdf"
    try:
        generate_cotizacion(
            pdf_path, cotizacion.numero, cotizacion.created_at.date(),
            cotizacion.solicitud.cliente.nombre, cotizacion.planta.nombre,
            _pdf_items(cotizacion), cotizacion.total,
            firma_path=firma_path, notas=cotizacion.notas,
        )
        cotizacion.pdf_path = str(pdf_path)
        cotizacion.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF cotización %s: %s", cotizacion.numero, e)


class CotizacionListCreateView(APIView):
    def get(self, request):
        cotizaciones = Cotizacion.objects.select_related("solicitud__cliente", "planta").prefetch_related("items")
        estado = request.query_params.get("estado")
        if estado:
            cotizaciones = cotizaciones.filter(estado=estado)
        return Response(CotizacionSerializer(cotizaciones, many=True).data)

    def post(self, request):
        d = request.data
        solicitud_id = d.get("solicitud")
        planta_id = d.get("planta")
        items = d.get("items") or []
        if not solicitud_id or not planta_id:
            return Response({"detail": "solicitud y planta son requeridos"}, status=400)
        if not items:
            return Response({"detail": "La cotización debe tener al menos un ítem"}, status=400)

        solicitud = SolicitudCotizacion.objects.filter(id=solicitud_id).first()
        if not solicitud:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        if hasattr(solicitud, "cotizacion"):
            return Response({"detail": "Esta solicitud ya tiene una cotización"}, status=400)
        planta = Planta.objects.filter(id=planta_id).first()
        if not planta:
            return Response({"detail": "Planta no encontrada"}, status=404)

        cotizacion = Cotizacion.objects.create(
            numero=_numero_cotizacion(), solicitud=solicitud, planta=planta,
            notas=d.get("notas"), creado_por=request.user,
        )
        for it in items:
            material = Material.objects.filter(id=it.get("material")).first()
            if not material:
                continue
            precio = MaterialPlanta.objects.filter(material=material, planta=planta).first()
            CotizacionItem.objects.create(
                cotizacion=cotizacion, material=material, cantidad=it.get("cantidad") or 0,
                precio_unitario=(precio.precio_unitario if precio else (it.get("precio_unitario") or 0)),
            )

        solicitud.estado = "cotizada"
        solicitud.save(update_fields=["estado"])

        cotizacion.refresh_from_db()
        _generar_pdf(cotizacion)
        cotizacion.refresh_from_db()
        return Response(CotizacionSerializer(cotizacion).data, status=201)


class CotizacionDetailView(APIView):
    def get_object(self, cotizacion_id):
        return Cotizacion.objects.filter(id=cotizacion_id).first()

    def get(self, request, cotizacion_id):
        cotizacion = self.get_object(cotizacion_id)
        if not cotizacion:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(CotizacionSerializer(cotizacion).data)


class CotizacionAprobarView(APIView):
    permission_classes = [IsAprobador]

    def post(self, request, cotizacion_id):
        cotizacion = Cotizacion.objects.filter(id=cotizacion_id).first()
        if not cotizacion:
            return Response({"detail": "No encontrada"}, status=404)
        if cotizacion.estado != "pendiente_aprobacion":
            return Response({"detail": "Esta cotización ya fue procesada"}, status=400)

        aprobar = request.data.get("aprobar", True)
        if aprobar:
            cotizacion.estado = "aprobada"
            cotizacion.aprobado_por = request.user
            cotizacion.fecha_aprobacion = timezone.now()
            cotizacion.save(update_fields=["estado", "aprobado_por", "fecha_aprobacion"])
            _generar_pdf(cotizacion, firma_path=request.user.firma_path)
        else:
            cotizacion.estado = "rechazada"
            cotizacion.motivo_rechazo = request.data.get("motivo", "")
            cotizacion.aprobado_por = request.user
            cotizacion.fecha_aprobacion = timezone.now()
            cotizacion.save(update_fields=["estado", "motivo_rechazo", "aprobado_por", "fecha_aprobacion"])

        cotizacion.refresh_from_db()
        return Response(CotizacionSerializer(cotizacion).data)


class CotizacionPdfView(APIView):
    def get(self, request, cotizacion_id):
        cotizacion = Cotizacion.objects.filter(id=cotizacion_id).first()
        if not cotizacion or not cotizacion.pdf_path:
            return Response({"detail": "PDF no disponible"}, status=404)
        path = Path(cotizacion.pdf_path)
        if not path.exists():
            return Response({"detail": "Archivo no encontrado"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{cotizacion.numero}.pdf")
