import logging
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from api.models import Pago, Cotizacion, OrdenSuministro
from api.serializers import PagoSerializer
from api.permissions import IsFinanciera

logger = logging.getLogger(__name__)


def _numero_orden():
    count = OrdenSuministro.objects.count()
    return f"OS-{count + 1:04d}"


class PagoListCreateView(APIView):
    def get(self, request):
        pagos = Pago.objects.select_related("cotizacion")
        estado = request.query_params.get("estado")
        if estado:
            pagos = pagos.filter(estado=estado)
        return Response(PagoSerializer(pagos, many=True).data)

    def post(self, request):
        d = request.data
        cotizacion_id = d.get("cotizacion")
        cotizacion = Cotizacion.objects.filter(id=cotizacion_id).first()
        if not cotizacion:
            return Response({"detail": "Cotización no encontrada"}, status=404)
        if cotizacion.estado != "aprobada":
            return Response({"detail": "La cotización debe estar aprobada antes de registrar el pago"}, status=400)
        if hasattr(cotizacion, "pago"):
            return Response({"detail": "Esta cotización ya tiene un pago registrado"}, status=400)

        pago = Pago.objects.create(
            cotizacion=cotizacion, monto=d.get("monto") or cotizacion.total, creado_por=request.user,
        )
        return Response(PagoSerializer(pago).data, status=201)


class PagoComprobanteUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pago_id):
        pago = Pago.objects.filter(id=pago_id).first()
        if not pago:
            return Response({"detail": "No encontrado"}, status=404)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No se envió archivo"}, status=400)
        ext = Path(file.name).suffix.lower()
        if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
            return Response({"detail": "Solo PDF, PNG o JPG"}, status=400)

        dest_dir = settings.UPLOAD_DIR / "comprobantes"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"comprobante_pago_{pago.id}{ext}"
        with dest.open("wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        pago.comprobante_path = str(dest)
        pago.save(update_fields=["comprobante_path"])
        return Response(PagoSerializer(pago).data)


class PagoAprobarView(APIView):
    permission_classes = [IsFinanciera]

    def post(self, request, pago_id):
        pago = Pago.objects.filter(id=pago_id).first()
        if not pago:
            return Response({"detail": "No encontrado"}, status=404)
        if pago.estado != "pendiente":
            return Response({"detail": "Este pago ya fue procesado"}, status=400)

        aprobar = request.data.get("aprobar", True)
        if aprobar:
            pago.estado = "aprobado"
            pago.aprobado_por = request.user
            pago.fecha_aprobacion = timezone.now()
            pago.save(update_fields=["estado", "aprobado_por", "fecha_aprobacion"])

            if not hasattr(pago.cotizacion, "orden_suministro"):
                OrdenSuministro.objects.create(
                    numero=_numero_orden(), cotizacion=pago.cotizacion,
                    planta=pago.cotizacion.planta, creado_por=request.user,
                )
        else:
            pago.estado = "rechazado"
            pago.motivo_rechazo = request.data.get("motivo", "")
            pago.aprobado_por = request.user
            pago.fecha_aprobacion = timezone.now()
            pago.save(update_fields=["estado", "motivo_rechazo", "aprobado_por", "fecha_aprobacion"])

        pago.refresh_from_db()
        return Response(PagoSerializer(pago).data)
