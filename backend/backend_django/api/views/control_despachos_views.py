"""Control de despacho de materiales: el consolidado que se le envía al cliente.

Es la caja "ARCHIVO DATA – CONTROL DESPACHOS" del flujo comercial: todo lo que
un cliente retiró en un período, tiquete por tiquete, valorizado al precio de
su cotización y con el IVA discriminado. No es un formato que se emita una sola
vez — se arma al vuelo con el rango que se pida, así que no se guarda en disco.
"""
from datetime import date
from decimal import Decimal

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from api.permissions import Requiere

from api.models import Cliente, DespachoItem, User
from services.pdf_service import generate_control_despachos


def _fecha(valor):
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def _persona(user):
    if not user:
        return None
    return {"nombre": user.nombre or user.username, "cargo": user.cargo}


def _precio_unitario(despacho_item):
    """Precio sin IVA con el que se cotizó ese material en la planta que despachó."""
    orden = despacho_item.despacho.orden_suministro
    for linea in orden.cotizacion.items.all():
        if linea.material_id == despacho_item.material_id and linea.planta_efectiva \
                and linea.planta_efectiva.id == orden.planta_id:
            return linea.precio_unitario
    return Decimal("0")


def armar_control(cliente, desde=None, hasta=None, obra=None):
    """Filas y totales del control. Separado de la vista para poder probarlo."""
    items = (
        DespachoItem.objects
        .filter(despacho__orden_suministro__cotizacion__solicitud__cliente=cliente)
        .select_related(
            "material", "despacho__orden_suministro__planta",
            "despacho__orden_suministro__cotizacion__solicitud",
            "despacho__orden_suministro__cotizacion__creado_por",
        )
        .prefetch_related(
            "despacho__orden_suministro__cotizacion__items__planta",
            "despacho__orden_suministro__cotizacion__planta",
        )
        .order_by("despacho__fecha", "despacho__consecutivo", "despacho__id")
    )
    if desde:
        items = items.filter(despacho__fecha__gte=desde)
    if hasta:
        items = items.filter(despacho__fecha__lte=hasta)
    if obra:
        items = items.filter(despacho__orden_suministro__cotizacion__solicitud__obra__icontains=obra)

    filas, subtotal, iva, cantidad = [], Decimal("0"), Decimal("0"), Decimal("0")
    comerciales, porcentajes = set(), set()
    for it in items:
        despacho = it.despacho
        orden = despacho.orden_suministro
        cotizacion = orden.cotizacion
        precio = _precio_unitario(it)
        valor = (it.cantidad * precio).quantize(Decimal("1"))
        # El IVA se calcula con el porcentaje de SU cotización, por si cambió
        # entre una y otra.
        iva += valor * cotizacion.iva_porcentaje / Decimal("100")
        subtotal += valor
        cantidad += it.cantidad
        porcentajes.add(cotizacion.iva_porcentaje)
        if cotizacion.creado_por_id:
            comerciales.add(cotizacion.creado_por)
        filas.append({
            "planta": "P. " + orden.planta.nombre.replace("Planta ", ""),
            "fecha": despacho.fecha,
            "consecutivo": despacho.consecutivo or despacho.numero,
            "empresa": cliente.nombre,
            "obra": cotizacion.solicitud.obra,
            "placa": despacho.placa_vehiculo,
            "material": it.material.nombre,
            "cantidad": it.cantidad,
            "valor_unitario": precio,
            "valor_total": valor,
        })

    iva = iva.quantize(Decimal("1"))
    return {
        "filas": filas,
        "total_cantidad": cantidad,
        "subtotal": subtotal,
        "iva": iva,
        "iva_porcentaje": porcentajes.pop() if len(porcentajes) == 1 else Decimal("19"),
        "total": subtotal + iva,
        # Si todo el período lo llevó un solo comercial, él revisa por defecto.
        "comercial": comerciales.pop() if len(comerciales) == 1 else None,
    }


class ControlDespachosPdfView(APIView):
    permission_classes = [Requiere(("despachos", "ordenes", "clientes"))]
    """GET ?cliente=<id>&desde=AAAA-MM-DD&hasta=AAAA-MM-DD&obra=<texto>&reviso=<user_id>"""

    def get(self, request):
        cliente = Cliente.objects.filter(id=request.query_params.get("cliente")).first()
        if not cliente:
            return Response({"detail": "Cliente no encontrado"}, status=404)

        control = armar_control(
            cliente,
            desde=_fecha(request.query_params.get("desde")),
            hasta=_fecha(request.query_params.get("hasta")),
            obra=(request.query_params.get("obra") or "").strip() or None,
        )
        reviso_id = request.query_params.get("reviso")
        reviso = User.objects.filter(id=reviso_id).first() if reviso_id else control["comercial"]

        pdf = generate_control_despachos({
            "cliente": {
                "nombre": cliente.nombre, "nit": cliente.nit,
                "direccion": cliente.direccion, "telefono": cliente.telefono,
            },
            "filas": control["filas"],
            "total_cantidad": control["total_cantidad"],
            "subtotal": control["subtotal"],
            "iva_porcentaje": control["iva_porcentaje"],
            "iva": control["iva"],
            "total": control["total"],
            "elaboro": _persona(request.user),
            "reviso": _persona(reviso),
        })
        respuesta = HttpResponse(pdf, content_type="application/pdf")
        respuesta["Content-Disposition"] = (
            f'attachment; filename="Control despachos {cliente.nombre}.pdf"'
        )
        return respuesta
