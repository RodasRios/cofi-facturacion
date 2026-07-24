import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Despacho, DespachoItem, OrdenSuministro, Material
from api.serializers import DespachoSerializer
from api.permissions import IsPlanta
from services.pdf_service import generate_despacho

logger = logging.getLogger(__name__)


def _numero_despacho():
    count = Despacho.objects.count()
    return f"REM-{count + 1:04d}"


def _pdf_items(despacho):
    return [
        {
            "material_nombre": i.material.nombre,
            "cantidad": i.cantidad,
            "unidad_medida": i.material.unidad_medida,
        }
        for i in despacho.items.select_related("material")
    ]


def _generar_pdf(despacho):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"REM_{despacho.id}_{despacho.numero.replace('-', '_')}.pdf"
    try:
        generate_despacho(
            pdf_path, despacho.numero, despacho.fecha,
            despacho.orden_suministro.cotizacion.solicitud.cliente.nombre,
            despacho.orden_suministro.planta.nombre,
            _pdf_items(despacho), recibido_por=despacho.recibido_por,
            placa_vehiculo=despacho.placa_vehiculo, cliente_retira=despacho.cliente_retira,
            notas=despacho.notas,
        )
        despacho.pdf_path = str(pdf_path)
        despacho.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF despacho %s: %s", despacho.numero, e)


class DespachoListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsPlanta()]
        return super().get_permissions()

    def get(self, request):
        despachos = Despacho.objects.select_related("orden_suministro__planta", "orden_suministro__cotizacion__solicitud__cliente")
        orden_id = request.query_params.get("orden_suministro")
        if orden_id:
            despachos = despachos.filter(orden_suministro_id=orden_id)
        return Response(DespachoSerializer(despachos, many=True).data)

    def post(self, request):
        d = request.data
        orden_id = d.get("orden_suministro")
        items = d.get("items") or []
        if not orden_id:
            return Response({"detail": "orden_suministro es requerido"}, status=400)
        if not items:
            return Response({"detail": "El despacho debe tener al menos un ítem"}, status=400)
        orden = OrdenSuministro.objects.filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "Orden de suministro no encontrada"}, status=404)
        fecha = d.get("fecha")
        if not fecha:
            return Response({"detail": "fecha es requerida"}, status=400)

        despacho = Despacho.objects.create(
            numero=_numero_despacho(), orden_suministro=orden, fecha=fecha,
            recibido_por=d.get("recibido_por"), cliente_retira=d.get("cliente_retira", True),
            placa_vehiculo=d.get("placa_vehiculo"), notas=d.get("notas"), creado_por=request.user,
        )
        for it in items:
            material = Material.objects.filter(id=it.get("material")).first()
            if not material:
                continue
            DespachoItem.objects.create(despacho=despacho, material=material, cantidad=it.get("cantidad") or 0)

        despacho.refresh_from_db()
        _generar_pdf(despacho)
        despacho.refresh_from_db()
        return Response(DespachoSerializer(despacho).data, status=201)


class DespachoDetailView(APIView):
    def get(self, request, despacho_id):
        despacho = Despacho.objects.filter(id=despacho_id).first()
        if not despacho:
            return Response({"detail": "No encontrado"}, status=404)
        return Response(DespachoSerializer(despacho).data)


class DespachoPdfView(APIView):
    def get(self, request, despacho_id):
        despacho = Despacho.objects.filter(id=despacho_id).first()
        if not despacho or not despacho.pdf_path:
            return Response({"detail": "PDF no disponible"}, status=404)
        path = Path(despacho.pdf_path)
        if not path.exists():
            return Response({"detail": "Archivo no encontrado"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{despacho.numero}.pdf")
