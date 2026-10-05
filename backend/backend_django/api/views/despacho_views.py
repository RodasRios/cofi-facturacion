import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import Despacho, DespachoItem, OrdenSuministro, Material
from api.serializers import DespachoSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from api.permissions import Requiere, plantas_de
from api.numeracion import siguiente

LEER_DESPACHOS = ("despachos", "ordenes")
from services.pdf_service import generate_despacho

logger = logging.getLogger(__name__)


def _numero_despacho():
    return siguiente(Despacho, "REM-")


CAMPOS_FORMATO = (
    "consecutivo", "recibido_por", "recibido_cargo", "placa_vehiculo", "notas",
    "despachado_por_nombre", "despachado_por_cargo", "conductor_nombre", "conductor_cedula",
    "temperatura_despacho",
)


def _limpio(v):
    return (str(v).strip() if v is not None else "")


def _hora(v):
    """'06:00' → time; vacío o inválido → None."""
    from datetime import datetime
    v = _limpio(v)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt).time()
        except ValueError:
            pass
    return None


def _generar_pdf(despacho):
    """Calco del talonario de control de despacho. Se regenera al abrirlo, así
    los despachos viejos salen con el formato y los datos al día."""
    orden = despacho.orden_suministro
    sol = orden.cotizacion.solicitud
    pdf_path = settings.GENERATED_PDF_DIR / f"REM_{despacho.id}_{despacho.numero.replace('-', '_')}.pdf"
    try:
        generate_despacho(pdf_path, {
            "numero": despacho.numero,
            "consecutivo": despacho.consecutivo,
            "fecha": despacho.fecha,
            "planta": orden.planta.nombre,
            "cliente": sol.cliente.nombre,
            "obra": orden.obra or sol.obra,
            "orden": orden.numero,
            "despachado_por": {"nombre": despacho.despachado_por_nombre, "cargo": despacho.despachado_por_cargo},
            "items": [
                {"codigo": i.material.codigo, "material": i.material.nombre,
                 "cantidad": i.cantidad, "unidad": i.material.unidad_medida}
                for i in despacho.items.select_related("material")
            ],
            "placa": despacho.placa_vehiculo,
            "conductor": {"nombre": despacho.conductor_nombre, "cedula": despacho.conductor_cedula},
            "hora_despacho": despacho.hora_despacho,
            "temperatura_despacho": despacho.temperatura_despacho,
            "recibido": {"nombre": despacho.recibido_por, "cargo": despacho.recibido_cargo},
            "notas": despacho.notas,
        })
        despacho.pdf_path = str(pdf_path)
        despacho.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF despacho %s: %s", despacho.numero, e)


def _despachos_qs(user):
    qs = Despacho.objects.select_related(
        "orden_suministro__planta", "orden_suministro__cotizacion__solicitud__cliente",
    ).prefetch_related("items__material")
    limitadas = plantas_de(user)
    return qs.filter(orden_suministro__planta_id__in=limitadas) if limitadas is not None else qs


class DespachoListCreateView(APIView):
    permission_classes = [Requiere(LEER_DESPACHOS, ("despachos",))]

    def get(self, request):
        despachos = _despachos_qs(request.user)
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
        limitadas = plantas_de(request.user)
        if not orden or (limitadas is not None and orden.planta_id not in limitadas):
            return Response({"detail": "Orden de suministro no encontrada"}, status=404)
        materiales_orden = {oi.cotizacion_item.material_id for oi in orden.items.select_related("cotizacion_item")}
        validos = [it for it in items if int(it.get("material") or 0) in materiales_orden and float(it.get("cantidad") or 0) > 0]
        if not validos:
            return Response({"detail": "Indica la cantidad despachada de al menos un material de la orden"}, status=400)
        items = validos
        fecha = d.get("fecha")
        if not fecha:
            return Response({"detail": "fecha es requerida"}, status=400)

        campos = {k: _limpio(d.get(k)) for k in CAMPOS_FORMATO}
        # "Despachado por" es quien lo registra, salvo que se escriba otro.
        campos["despachado_por_nombre"] = campos["despachado_por_nombre"] or (request.user.nombre or request.user.username)
        campos["despachado_por_cargo"] = campos["despachado_por_cargo"] or (request.user.cargo or "")
        for k in ("consecutivo", "recibido_por", "placa_vehiculo", "notas"):
            campos[k] = campos[k] or None
        despacho = Despacho.objects.create(
            numero=_numero_despacho(), orden_suministro=orden, fecha=fecha,
            cliente_retira=d.get("cliente_retira", True), hora_despacho=_hora(d.get("hora_despacho")),
            creado_por=request.user, **campos,
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
    permission_classes = [Requiere(LEER_DESPACHOS, ("despachos",))]

    def get(self, request, despacho_id):
        despacho = _despachos_qs(request.user).filter(id=despacho_id).first()
        if not despacho:
            return Response({"detail": "No encontrado"}, status=404)
        return Response(DespachoSerializer(despacho).data)

    def patch(self, request, despacho_id):
        """Completar los datos del formato después (recibido por, conductor…).
        Las cantidades no se tocan aquí."""
        despacho = _despachos_qs(request.user).filter(id=despacho_id).first()
        if not despacho:
            return Response({"detail": "No encontrado"}, status=404)
        d = request.data
        for k in CAMPOS_FORMATO:
            if k in d:
                v = _limpio(d[k])
                setattr(despacho, k, v or (None if k in ("consecutivo", "recibido_por", "placa_vehiculo", "notas") else ""))
        if "hora_despacho" in d:
            despacho.hora_despacho = _hora(d["hora_despacho"])
        if "fecha" in d and d["fecha"]:
            despacho.fecha = d["fecha"]
        despacho.save()
        despacho.refresh_from_db()
        _generar_pdf(despacho)
        return Response(DespachoSerializer(despacho).data)


class DespachoPdfView(APIView):
    permission_classes = [Requiere(LEER_DESPACHOS)]

    def get(self, request, despacho_id):
        despacho = _despachos_qs(request.user).filter(id=despacho_id).first()
        if not despacho:
            return Response({"detail": "PDF no disponible"}, status=404)
        _generar_pdf(despacho)
        if not despacho.pdf_path:
            return Response({"detail": "PDF no disponible"}, status=404)
        path = Path(despacho.pdf_path)
        if not path.exists():
            return Response({"detail": "Archivo no encontrado"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{despacho.numero}.pdf")


class DespachoSoporteView(APIView):
    """Foto o PDF del tiquete/remisión firmado: lo sube la planta."""
    permission_classes = [Requiere(LEER_DESPACHOS, ("despachos",))]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, despacho_id):
        despacho = _despachos_qs(request.user).filter(id=despacho_id).first()
        if not despacho or not despacho.soporte_path or not Path(despacho.soporte_path).exists():
            return Response({"detail": "Sin soporte"}, status=404)
        path = Path(despacho.soporte_path)
        return FileResponse(path.open("rb"), filename=f"{despacho.numero}_soporte{path.suffix}")

    def post(self, request, despacho_id):
        despacho = _despachos_qs(request.user).filter(id=despacho_id).first()
        if not despacho:
            return Response({"detail": "No encontrado"}, status=404)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No se envió archivo"}, status=400)
        ext = Path(file.name).suffix.lower()
        if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
            return Response({"detail": "Solo PDF o imagen (PNG, JPG)"}, status=400)
        dest_dir = settings.UPLOAD_DIR / "soportes_despacho"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"soporte_{despacho.id}{ext}"
        for viejo in dest_dir.glob(f"soporte_{despacho.id}.*"):
            viejo.unlink(missing_ok=True)
        with dest.open("wb") as f:
            for chunk in file.chunks():
                f.write(chunk)
        despacho.soporte_path = str(dest)
        despacho.save(update_fields=["soporte_path"])
        return Response(DespachoSerializer(despacho).data)
