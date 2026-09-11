"""Tablero de seguimiento: en qué etapa del flujo va cada solicitud.

Nada de esto se guarda en la base — la etapa se deduce del estado de los
documentos que cuelgan de la solicitud. Así no hay un campo "etapa" que pueda
quedar desincronizado de la realidad.
"""
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from api.models import SolicitudCotizacion, Seguimiento
from api.serializers import SeguimientoSerializer

# Cada etapa dice quién tiene la pelota. El orden es el del flujo.
ETAPAS = {
    "pendiente_cotizacion":      ("Pendiente de cotizar",        "comercial"),
    "en_seguimiento":            ("En seguimiento del cliente",  "comercial"),
    "pendiente_aprobacion":      ("Esperando aprobación",        "aprobador"),
    "pendiente_pago":            ("Esperando pago del cliente",  "comercial"),
    "pendiente_aprobacion_pago": ("Esperando visto de financiera", "financiera"),
    "pendiente_notificacion":    ("Por notificar a planta",      "planta"),
    "pendiente_despacho":        ("Por despachar",               "planta"),
    "despachada":                ("Despachada",                  None),
}


def _etapa_de(solicitud):
    """Devuelve (clave_etapa, fecha_en_que_entró_a_esa_etapa)."""
    cot = solicitud.cotizacion_vigente

    if cot is None:
        # Sin cotización viva. Si hubo rechazos, está en seguimiento; si no,
        # es una solicitud recién creada que nadie ha cotizado.
        rechazadas = [c for c in solicitud.cotizaciones.all() if c.estado == "rechazada"]
        if rechazadas:
            ultima = max(rechazadas, key=lambda c: c.fecha_aprobacion or c.created_at)
            return "en_seguimiento", (ultima.fecha_aprobacion or ultima.created_at)
        return "pendiente_cotizacion", solicitud.created_at

    if cot.estado == "pendiente_aprobacion":
        return "pendiente_aprobacion", cot.created_at

    # De aquí en adelante la cotización está aprobada.
    pago = cot.pago_vigente
    if pago is None:
        rechazados = [p for p in cot.pagos.all() if p.estado == "rechazado"]
        desde = (
            max((p.fecha_aprobacion or p.created_at) for p in rechazados)
            if rechazados else (cot.fecha_aprobacion or cot.created_at)
        )
        return "pendiente_pago", desde

    if pago.estado == "pendiente":
        return "pendiente_aprobacion_pago", pago.created_at

    # Pago aprobado: ya existen las órdenes de suministro (una por planta si la
    # cotización se repartió). La solicitud avanza al ritmo de la más atrasada.
    ordenes = list(cot.ordenes_suministro.all())
    if not ordenes:
        return "pendiente_aprobacion_pago", pago.created_at

    sin_notificar = [o for o in ordenes if not o.notificada_planta]
    if sin_notificar:
        return "pendiente_notificacion", min(o.created_at for o in sin_notificar)

    sin_despachar = [o for o in ordenes if not o.despachos.all()]
    if sin_despachar:
        return "pendiente_despacho", min(
            (o.fecha_notificacion or o.created_at) for o in sin_despachar
        )

    ultimo = max(d.created_at for o in ordenes for d in o.despachos.all())
    return "despachada", ultimo


class TableroView(APIView):
    """Una fila por solicitud, con su etapa actual y cuánto lleva ahí."""

    def get(self, request):
        solicitudes = (
            SolicitudCotizacion.objects
            .select_related("cliente")
            .prefetch_related(
                "cotizaciones__items__planta",
                "cotizaciones__pagos",
                "cotizaciones__ordenes_suministro__despachos",
            )
        )

        ahora = timezone.now()
        filas = []
        for s in solicitudes:
            etapa, desde = _etapa_de(s)
            titulo, responsable = ETAPAS[etapa]
            cot = s.cotizacion_vigente
            filas.append({
                "solicitud_id": s.id,
                "numero": s.numero,
                "cliente_nombre": s.cliente.nombre,
                "etapa": etapa,
                "etapa_titulo": titulo,
                "responsable": responsable,
                "desde": desde,
                "dias_en_etapa": (ahora - desde).days,
                "cotizacion_numero": cot.numero if cot else None,
                "total": str(cot.total) if cot else None,
                "cotizaciones_rechazadas": sum(
                    1 for c in s.cotizaciones.all() if c.estado == "rechazada"
                ),
                "pagos_rechazados": sum(
                    1 for c in s.cotizaciones.all() for p in c.pagos.all()
                    if p.estado == "rechazado"
                ),
                "created_at": s.created_at,
            })

        # Lo más atascado primero: es lo que hay que mirar.
        filas.sort(key=lambda f: (f["etapa"] == "despachada", -f["dias_en_etapa"]))
        return Response(filas)


class SeguimientoListCreateView(APIView):
    """Bitácora de una solicitud. Las notas las escribe el comercial."""

    def get(self, request, solicitud_id):
        solicitud = SolicitudCotizacion.objects.filter(id=solicitud_id).first()
        if not solicitud:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        seguimientos = solicitud.seguimientos.select_related("usuario")
        return Response(SeguimientoSerializer(seguimientos, many=True).data)

    def post(self, request, solicitud_id):
        solicitud = SolicitudCotizacion.objects.filter(id=solicitud_id).first()
        if not solicitud:
            return Response({"detail": "Solicitud no encontrada"}, status=404)
        texto = str(request.data.get("texto", "")).strip()
        if not texto:
            return Response({"detail": "La nota no puede estar vacía"}, status=400)
        seg = Seguimiento.objects.create(
            solicitud=solicitud, tipo="nota", texto=texto, usuario=request.user,
        )
        return Response(SeguimientoSerializer(seg).data, status=201)
