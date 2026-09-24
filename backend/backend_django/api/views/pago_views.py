"""Pagos: abonos parciales y órdenes de compra del cliente.

Una cotización aprobada se cubre con uno o varios registros:
- transferencia/consignación → "pendiente" hasta que financiera la revisa.
- orden de compra del cliente → "por_confirmar": respalda el despacho, pero la
  plata aún no entra. Financiera la confirma cuando llega el pago.

La suma de lo registrado (sin contar rechazados) no puede pasar del total.
Las órdenes de suministro ya no se crean aquí: las emite a mano quien tenga
el permiso "ordenes" (ver orden_suministro_views).
"""
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from api.models import Pago, Cotizacion, Seguimiento
from api.serializers import PagoSerializer
from api.permissions import Requiere

logger = logging.getLogger(__name__)

LEER_PAGOS = ("pagos", "aprobar_pagos", "tablero")


def _guardar_archivo(pago, file):
    ext = Path(file.name).suffix.lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg"]:
        return "Solo PDF, PNG o JPG"
    dest_dir = settings.UPLOAD_DIR / "comprobantes"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"comprobante_pago_{pago.id}{ext}"
    with dest.open("wb") as f:
        for chunk in file.chunks():
            f.write(chunk)
    pago.comprobante_path = str(dest)
    pago.save(update_fields=["comprobante_path"])
    return None


def _pesos(v):
    return f"${v:,.0f}".replace(",", ".")


class PagoListCreateView(APIView):
    permission_classes = [Requiere(LEER_PAGOS, ("pagos",))]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        pagos = Pago.objects.select_related("cotizacion__solicitud__cliente", "aprobado_por", "creado_por")
        estado = request.query_params.get("estado")
        if estado:
            pagos = pagos.filter(estado=estado)
        cotizacion = request.query_params.get("cotizacion")
        if cotizacion:
            pagos = pagos.filter(cotizacion_id=cotizacion)
        return Response(PagoSerializer(pagos, many=True).data)

    def post(self, request):
        d = request.data
        tipo = d.get("tipo") or "transferencia"
        if tipo not in ("transferencia", "orden_compra"):
            return Response({"detail": "Tipo de pago no válido"}, status=400)
        try:
            monto = Decimal(str(d.get("monto") or "0"))
        except InvalidOperation:
            return Response({"detail": "El monto no es un número"}, status=400)
        if monto <= 0:
            return Response({"detail": "El monto debe ser mayor que cero"}, status=400)

        with transaction.atomic():
            cotizacion = (
                Cotizacion.objects.select_for_update()
                .filter(id=d.get("cotizacion")).first()
            )
            if not cotizacion:
                return Response({"detail": "Cotización no encontrada"}, status=404)
            if cotizacion.estado != "aprobada":
                return Response({"detail": "La cotización debe estar aprobada antes de registrar pagos"}, status=400)
            disponible = cotizacion.saldo_sin_registrar
            if monto > disponible + Decimal("1"):
                return Response({
                    "detail": f"El monto supera lo que falta por cubrir ({_pesos(disponible)}).",
                }, status=400)

            pago = Pago.objects.create(
                cotizacion=cotizacion, tipo=tipo, monto=monto,
                referencia=(d.get("referencia") or "").strip() or None,
                fecha_pago=d.get("fecha_pago") or None,
                notas=(d.get("notas") or "").strip() or None,
                estado="por_confirmar" if tipo == "orden_compra" else "pendiente",
                creado_por=request.user,
            )
        archivo = request.FILES.get("file")
        if archivo:
            error = _guardar_archivo(pago, archivo)
            if error:
                return Response({"detail": error}, status=400)

        que = "Orden de compra" if tipo == "orden_compra" else "Pago"
        Seguimiento.objects.create(
            solicitud=cotizacion.solicitud, tipo="nota", usuario=request.user,
            texto=f"{que} registrado por {_pesos(monto)} sobre {cotizacion.numero}"
                  + (f" (ref. {pago.referencia})" if pago.referencia else "") + ".",
        )
        return Response(PagoSerializer(pago).data, status=201)


class PagoComprobanteUploadView(APIView):
    permission_classes = [Requiere(LEER_PAGOS, ("pagos", "aprobar_pagos"))]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pago_id):
        pago = Pago.objects.filter(id=pago_id).first()
        if not pago or not pago.comprobante_path or not Path(pago.comprobante_path).exists():
            return Response({"detail": "Sin comprobante"}, status=404)
        return FileResponse(open(pago.comprobante_path, "rb"), filename=Path(pago.comprobante_path).name)

    def post(self, request, pago_id):
        pago = Pago.objects.filter(id=pago_id).first()
        if not pago:
            return Response({"detail": "No encontrado"}, status=404)
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No se envió archivo"}, status=400)
        error = _guardar_archivo(pago, file)
        if error:
            return Response({"detail": error}, status=400)
        return Response(PagoSerializer(pago).data)


class PagoAprobarView(APIView):
    """Revisión de financiera.

    - Transferencia pendiente → aprobar o rechazar.
    - Orden de compra por confirmar → confirmar (llegó la plata; se puede
      corregir el monto recibido) o anular.
    """
    permission_classes = [Requiere(("aprobar_pagos",))]

    def post(self, request, pago_id):
        pago = Pago.objects.select_related("cotizacion__solicitud").filter(id=pago_id).first()
        if not pago:
            return Response({"detail": "No encontrado"}, status=404)
        if pago.estado not in ("pendiente", "por_confirmar"):
            return Response({"detail": "Este pago ya fue procesado"}, status=400)

        aprobar = request.data.get("aprobar", True)
        if isinstance(aprobar, str):
            aprobar = aprobar.lower() in ("true", "1")
        era_oc = pago.estado == "por_confirmar"
        cot = pago.cotizacion
        campos = ["estado", "aprobado_por", "fecha_aprobacion"]

        if aprobar:
            monto = request.data.get("monto")
            if monto not in (None, ""):
                try:
                    monto = Decimal(str(monto))
                except InvalidOperation:
                    return Response({"detail": "El monto no es un número"}, status=400)
                if monto <= 0:
                    return Response({"detail": "El monto debe ser mayor que cero"}, status=400)
                pago.monto = monto
                campos.append("monto")
            if request.data.get("referencia"):
                pago.referencia = str(request.data["referencia"]).strip()
                campos.append("referencia")
            pago.estado = "aprobado"
            texto = (f"Orden de compra de {cot.numero} confirmada: ingresaron {_pesos(pago.monto)}."
                     if era_oc else f"Pago de {_pesos(pago.monto)} sobre {cot.numero} aprobado.")
            tipo_seg = "pago_aprobado"
        else:
            motivo = request.data.get("motivo", "")
            pago.estado = "rechazado"
            pago.motivo_rechazo = motivo
            campos.append("motivo_rechazo")
            texto = (f"Orden de compra de {cot.numero} anulada." if era_oc
                     else f"Pago de {cot.numero} rechazado.") + (f" Motivo: {motivo}" if motivo else "")
            tipo_seg = "pago_rechazado"

        pago.aprobado_por = request.user
        pago.fecha_aprobacion = timezone.now()
        pago.save(update_fields=campos)
        Seguimiento.objects.create(solicitud=cot.solicitud, tipo=tipo_seg, usuario=request.user, texto=texto)
        return Response(PagoSerializer(pago).data)


class CarteraView(APIView):
    """Cotizaciones aprobadas con plata pendiente: lo que falta por cobrar,
    cuánto está respaldado por orden de compra y cuánto no tiene nada."""
    permission_classes = [Requiere(("tablero", "pagos", "aprobar_pagos"))]

    def get(self, request):
        cotizaciones = (
            Cotizacion.objects.filter(estado="aprobada")
            .select_related("solicitud__cliente")
            .prefetch_related("items", "ajustes", "pagos")
        )
        filas = []
        for c in cotizaciones:
            if c.saldo_por_cobrar <= 0:
                continue
            filas.append({
                "cotizacion_id": c.id,
                "cotizacion_numero": c.numero,
                "cliente_nombre": c.solicitud.cliente.nombre,
                "total": str(c.total),
                "pagado": str(c.total_pagado),
                "en_revision": str(c.total_en_revision),
                "por_confirmar": str(c.total_por_confirmar),
                "saldo_por_cobrar": str(c.saldo_por_cobrar),
                "sin_respaldo": str(c.saldo_sin_registrar),
                "fecha_aprobacion": c.fecha_aprobacion,
            })
        filas.sort(key=lambda f: -Decimal(f["saldo_por_cobrar"]))
        return Response(filas)
