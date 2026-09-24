"""Tablero de seguimiento: en qué etapa del flujo va cada solicitud.

Nada de esto se guarda en la base — la etapa se deduce del estado de los
documentos que cuelgan de la solicitud. Así no hay un campo "etapa" que pueda
quedar desincronizado de la realidad.
"""
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from api.permissions import Requiere

from collections import defaultdict
from decimal import Decimal

from api.models import SolicitudCotizacion, Seguimiento, Cotizacion, Pago, DespachoItem
from api.serializers import SeguimientoSerializer

# Cada etapa dice quién tiene la pelota. El orden es el del flujo.
ETAPAS = {
    "pendiente_cotizacion":      ("Pendiente de cotizar",          "comercial"),
    "en_seguimiento":            ("En seguimiento del cliente",    "comercial"),
    "pendiente_aprobacion":      ("Esperando aprobación",          "aprobador"),
    "pendiente_pago":            ("Esperando pago del cliente",    "comercial"),
    "pendiente_aprobacion_pago": ("Esperando visto de financiera", "financiera"),
    "pendiente_orden":           ("Por emitir orden de suministro", "comercial"),
    "pendiente_notificacion":    ("Por notificar a planta",        "comercial"),
    "pendiente_despacho":        ("Por despachar",                 "planta"),
    "despachada":                ("Despachada",                    None),
}

PREFETCH = (
    "cotizaciones__items__planta", "cotizaciones__items__ordenes_items", "cotizaciones__ajustes",
    "cotizaciones__pagos", "cotizaciones__ordenes_suministro__items__cotizacion_item",
    "cotizaciones__ordenes_suministro__despachos__items",
)


def _etapa_de(solicitud):
    """Devuelve (clave_etapa, fecha_en_que_entró_a_esa_etapa).

    Con pagos parciales y órdenes parciales, la solicitud va al ritmo de lo
    más atrasado: mientras haya una orden sin notificar o sin despachar, o
    material cotizado sin ordenar, no está "despachada".
    """
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

    # Cotización aprobada. Sin nada pagado ni orden de compra no se puede ordenar.
    pagos = list(cot.pagos.all())
    if not cot.habilita_ordenes:
        en_revision = [p for p in pagos if p.estado == "pendiente"]
        if en_revision:
            return "pendiente_aprobacion_pago", min(p.created_at for p in en_revision)
        rechazados = [p for p in pagos if p.estado == "rechazado"]
        desde = (
            max((p.fecha_aprobacion or p.created_at) for p in rechazados)
            if rechazados else (cot.fecha_aprobacion or cot.created_at)
        )
        return "pendiente_pago", desde

    ordenes = list(cot.ordenes_suministro.all())
    sin_notificar = [o for o in ordenes if not o.notificada_planta]
    if sin_notificar:
        return "pendiente_notificacion", min(o.created_at for o in sin_notificar)

    sin_despachar = [o for o in ordenes if not o.completamente_despachada]
    if sin_despachar:
        return "pendiente_despacho", min((o.fecha_notificacion or o.created_at) for o in sin_despachar)

    por_ordenar = any(cot.cantidad_ordenada(i) < i.cantidad for i in cot.items.all())
    if por_ordenar or not ordenes:
        desde = max([o.created_at for o in ordenes] + [p.fecha_aprobacion or p.created_at for p in pagos])
        return "pendiente_orden", desde

    ultimo = max((d.created_at for o in ordenes for d in o.despachos.all()), default=cot.created_at)
    return "despachada", ultimo


class TableroView(APIView):
    permission_classes = [Requiere(("tablero",))]
    """Una fila por solicitud, con su etapa actual y cuánto lleva ahí."""

    def get(self, request):
        solicitudes = (
            SolicitudCotizacion.objects
            .select_related("cliente")
            .prefetch_related(*PREFETCH)
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
                "pagado": str(cot.total_pagado) if cot else None,
                "por_confirmar": str(cot.total_por_confirmar) if cot else None,
                "saldo_por_cobrar": str(cot.saldo_por_cobrar) if cot and cot.estado == "aprobada" else None,
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
    permission_classes = [Requiere(("tablero", "solicitudes"))]
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


def _mes(fecha):
    return f"{fecha.year:04d}-{fecha.month:02d}"


def _ultimos_meses(hoy, n):
    """['2026-04', …, '2026-09'] — los n meses que terminan en el actual."""
    meses, y, m = [], hoy.year, hoy.month
    for _ in range(n):
        meses.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(meses))


class TableroResumenView(APIView):
    permission_classes = [Requiere(("tablero",))]
    """Indicadores del negocio para la parte de arriba del tablero.

    Todo se calcula al vuelo desde los documentos: ventas = pagos aprobados
    (es la plata que entró), cotizado = cotizaciones no rechazadas.
    """

    MESES = 6

    def get(self, request):
        hoy = timezone.localdate()
        meses = _ultimos_meses(hoy, self.MESES)
        mes_actual = meses[-1]

        cotizaciones = list(
            Cotizacion.objects
            .select_related("solicitud__cliente", "planta")
            .prefetch_related("items__planta", "items__material", "ajustes", "pagos")
        )
        pagos = list(Pago.objects.filter(estado="aprobado").select_related("cotizacion__solicitud__cliente"))
        aprobadas = [c for c in cotizaciones if c.estado == "aprobada"]
        # Prefetch de pagos ya cargado en `cotizaciones`: se suma en memoria.
        por_cobrar = sum((c.saldo_por_cobrar for c in aprobadas), Decimal("0"))
        por_confirmar = sum((c.total_por_confirmar for c in aprobadas), Decimal("0"))

        ventas_mes = defaultdict(Decimal)
        for p in pagos:
            ventas_mes[_mes(timezone.localtime(p.fecha_aprobacion or p.created_at))] += p.monto

        cotizado_mes = defaultdict(Decimal)
        por_estado = defaultdict(int)
        por_planta = defaultdict(Decimal)
        por_cliente = defaultdict(Decimal)
        por_material = defaultdict(lambda: {"cantidad": Decimal("0"), "unidad": ""})
        for c in cotizaciones:
            por_estado[c.estado] += 1
            if c.estado == "rechazada":
                continue
            cotizado_mes[_mes(timezone.localtime(c.created_at))] += c.total
            if c.estado != "aprobada":
                continue
            por_cliente[c.solicitud.cliente.nombre] += c.total
            for i in c.items.all():
                planta = i.planta_efectiva
                por_planta[planta.nombre if planta else "-"] += i.subtotal
                mat = por_material[i.material.nombre]
                mat["cantidad"] += i.cantidad
                mat["unidad"] = i.material.unidad_medida

        despachado_mes = sum(
            (d.cantidad for d in DespachoItem.objects.filter(
                despacho__fecha__year=hoy.year, despacho__fecha__month=hoy.month,
            )),
            Decimal("0"),
        )

        decididas = por_estado["aprobada"] + por_estado["rechazada"]
        en_curso = sum(
            1 for s in SolicitudCotizacion.objects.prefetch_related(
                "cotizaciones__pagos", "cotizaciones__ordenes_suministro__despachos",
            )
            if s.estado != "cerrada" and _etapa_de(s)[0] != "despachada"
        )

        def top(d, n=5):
            return [{"nombre": k, "valor": str(v)} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]]

        return Response({
            "kpis": {
                "ventas_mes": str(ventas_mes[mes_actual]),
                "cotizado_mes": str(cotizado_mes[mes_actual]),
                "tasa_aprobacion": round(100 * por_estado["aprobada"] / decididas) if decididas else None,
                "pendientes_aprobacion": por_estado["pendiente_aprobacion"],
                "pagos_por_revisar": Pago.objects.filter(estado="pendiente").count(),
                "solicitudes_en_curso": en_curso,
                "despachado_mes": str(despachado_mes),
                "por_cobrar": str(por_cobrar),
                "por_confirmar": str(por_confirmar),
            },
            "por_mes": [
                {"mes": m, "ventas": str(ventas_mes[m]), "cotizado": str(cotizado_mes[m])}
                for m in meses
            ],
            "cotizaciones_por_estado": dict(por_estado),
            "por_planta": top(por_planta, 10),
            "top_clientes": top(por_cliente),
            "top_materiales": [
                {"nombre": k, "cantidad": str(v["cantidad"]), "unidad": v["unidad"]}
                for k, v in sorted(por_material.items(), key=lambda kv: -kv[1]["cantidad"])[:5]
            ],
        })
