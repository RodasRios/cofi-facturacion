import logging
import re
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import OrdenSuministro
from api.serializers import OrdenSuministroSerializer
from api.permissions import IsPlanta, _has_rol
from rest_framework.permissions import BasePermission


class PuedeEditarOrden(BasePermission):
    def has_permission(self, request, view):
        return _has_rol(request.user, "comercial", "planta")
from services.pdf_service import generate_orden_suministro

logger = logging.getLogger(__name__)


def _placas(texto):
    """"SPT880, WMB006" → ["SPT880", "WMB006"]. Acepta comas, punto y coma o saltos de línea."""
    if not texto:
        return []
    return [p.strip().upper() for p in re.split(r"[,;\n]+", texto) if p.strip()]


def _datos_pdf(orden):
    cotizacion = orden.cotizacion
    solicitud = cotizacion.solicitud
    # Solo lo que despacha ESTA planta: si la cotización se repartió entre
    # varias, cada orden lleva únicamente su parte.
    items = [
        {"material": i.material.nombre, "cantidad": i.cantidad, "unidad": i.material.unidad_medida}
        for i in cotizacion.items.select_related("material", "planta")
        if i.planta_efectiva and i.planta_efectiva.id == orden.planta_id
    ]
    # Autoriza el comercial que llevó la negociación, como en el formato en papel.
    comercial = cotizacion.creado_por
    return {
        "numero": orden.numero,
        "fecha": timezone.localtime(orden.created_at).date(),
        "cliente": solicitud.cliente.nombre,
        "obra": solicitud.obra,
        "planta": orden.planta.nombre,
        "items": items,
        "fecha_suministro": orden.fecha_suministro,
        "placas_empresa": _placas(orden.placas_empresa),
        "placas_cliente": _placas(orden.placas_cliente),
        "observacion": orden.notas,
        "autoriza": {
            "nombre": (comercial.nombre or comercial.username) if comercial else "",
            "area": "ÁREA COMERCIAL",
        },
    }


def _generar_pdf(orden):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"OS_{orden.id}_{orden.numero.replace('-', '_')}.pdf"
    try:
        generate_orden_suministro(pdf_path, _datos_pdf(orden))
        orden.pdf_path = str(pdf_path)
        orden.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF orden de suministro %s: %s", orden.numero, e)


class OrdenSuministroListView(APIView):
    def get(self, request):
        ordenes = (
            OrdenSuministro.objects
            .select_related("planta", "cotizacion__planta", "cotizacion__solicitud__cliente")
            # get_items recorre los ítems de la cotización para quedarse con los
            # de esta planta; sin esto sería una consulta por orden.
            .prefetch_related("cotizacion__items__material", "cotizacion__items__planta")
        )
        planta_id = request.query_params.get("planta")
        if planta_id:
            ordenes = ordenes.filter(planta_id=planta_id)
        return Response(OrdenSuministroSerializer(ordenes, many=True).data)


# Lo que se completa después de emitida la orden: cuándo retira el cliente,
# con qué vehículos y cualquier observación para la planta.
CAMPOS_EDITABLES = ("fecha_suministro", "placas_empresa", "placas_cliente", "notas")


class OrdenSuministroDetailView(APIView):
    def get_permissions(self):
        # Las placas las recibe el comercial del cliente; la planta también
        # puede corregirlas en portería. Ver la orden, cualquiera.
        if self.request.method == "PATCH":
            return [PuedeEditarOrden()]
        return super().get_permissions()

    def get(self, request, orden_id):
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        if not orden.pdf_path:
            _generar_pdf(orden)
            orden.refresh_from_db()
        return Response(OrdenSuministroSerializer(orden).data)

    def patch(self, request, orden_id):
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        datos = {k: request.data[k] for k in CAMPOS_EDITABLES if k in request.data}
        ser = OrdenSuministroSerializer(orden, data=datos, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        ser.save()
        # El formato impreso debe reflejar las placas nuevas: la planta lo usa
        # para dejar entrar los vehículos.
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
        # Siempre fresco: las órdenes emitidas antes del formato nuevo también
        # salen con él, y cualquier cambio de placas queda reflejado.
        _generar_pdf(orden)
        orden.refresh_from_db()
        path = Path(orden.pdf_path) if orden.pdf_path else None
        if not path or not path.exists():
            return Response({"detail": "PDF no disponible"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{orden.numero}.pdf")
