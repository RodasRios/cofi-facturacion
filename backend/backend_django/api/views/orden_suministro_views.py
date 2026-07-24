import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import OrdenSuministro
from api.serializers import OrdenSuministroSerializer
from api.permissions import IsPlanta
from services.pdf_service import generate_orden_suministro

logger = logging.getLogger(__name__)


def _pdf_items(orden):
    return [
        {
            "material_nombre": i.material.nombre,
            "cantidad": i.cantidad,
            "unidad_medida": i.material.unidad_medida,
        }
        for i in orden.cotizacion.items.select_related("material")
    ]


def _generar_pdf(orden):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"OS_{orden.id}_{orden.numero.replace('-', '_')}.pdf"
    try:
        generate_orden_suministro(
            pdf_path, orden.numero, orden.created_at.date(),
            orden.cotizacion.solicitud.cliente.nombre, orden.planta.nombre,
            _pdf_items(orden), notas=orden.notas,
        )
        orden.pdf_path = str(pdf_path)
        orden.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF orden de suministro %s: %s", orden.numero, e)


class OrdenSuministroListView(APIView):
    def get(self, request):
        ordenes = OrdenSuministro.objects.select_related("planta", "cotizacion__solicitud__cliente")
        planta_id = request.query_params.get("planta")
        if planta_id:
            ordenes = ordenes.filter(planta_id=planta_id)
        return Response(OrdenSuministroSerializer(ordenes, many=True).data)


class OrdenSuministroDetailView(APIView):
    def get(self, request, orden_id):
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        if not orden.pdf_path:
            _generar_pdf(orden)
            orden.refresh_from_db()
        return Response(OrdenSuministroSerializer(orden).data)


class OrdenSuministroNotificarView(APIView):
    """Marca la notificación a planta — el paso 'Notificación a Planta' del flujo."""
    permission_classes = [IsPlanta]

    def post(self, request, orden_id):
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        orden.notificada_planta = True
        orden.fecha_notificacion = timezone.now()
        orden.save(update_fields=["notificada_planta", "fecha_notificacion"])
        return Response(OrdenSuministroSerializer(orden).data)


class OrdenSuministroPdfView(APIView):
    def get(self, request, orden_id):
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        if not orden.pdf_path:
            _generar_pdf(orden)
            orden.refresh_from_db()
        path = Path(orden.pdf_path) if orden.pdf_path else None
        if not path or not path.exists():
            return Response({"detail": "PDF no disponible"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{orden.numero}.pdf")
