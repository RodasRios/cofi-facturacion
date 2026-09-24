"""Órdenes de suministro.

Ya no se crean solas al aprobar el pago: las emite a mano quien tenga el
permiso "ordenes", eligiendo planta, cantidades (pueden ser parciales),
fecha de suministro y placas. Una cotización puede tener varias órdenes por
planta; lo que no se ha ordenado queda como saldo.

Notificar a planta: el navegador abre WhatsApp Web con el mensaje armado
(`whatsapp_url`), y el servidor manda el correo con el PDF adjunto si hay
SMTP configurado. El mensaje lleva un link público al PDF (token), para que
la planta lo abra sin usuario.
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response

from api.models import OrdenSuministro, OrdenSuministroItem, Cotizacion, CotizacionItem, Planta, Seguimiento
from api.serializers import OrdenSuministroSerializer, CotizacionSerializer
from api.permissions import Requiere, plantas_de, tiene
from services.pdf_service import generate_orden_suministro

logger = logging.getLogger(__name__)

# La planta que despacha necesita leer sus órdenes.
LEER_ORDENES = ("ordenes", "despachos")


def _numero_orden():
    return f"OS-{OrdenSuministro.objects.count() + 1:04d}"


def _placas(texto):
    """"SPT880, WMB006" → ["SPT880", "WMB006"]. Acepta comas, punto y coma o saltos de línea."""
    if not texto:
        return []
    return [p.strip().upper() for p in re.split(r"[,;\n]+", texto) if p.strip()]


def _cantidad(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")


def _datos_pdf(orden):
    cotizacion = orden.cotizacion
    items = [
        {"material": oi.cotizacion_item.material.nombre, "cantidad": oi.cantidad,
         "unidad": oi.cotizacion_item.material.unidad_medida}
        for oi in orden.items.select_related("cotizacion_item__material")
    ]
    # Autoriza el comercial que llevó la negociación, como en el formato en papel.
    comercial = cotizacion.creado_por
    return {
        "numero": orden.numero,
        "fecha": timezone.localtime(orden.created_at).date(),
        "cliente": cotizacion.solicitud.cliente.nombre,
        "obra": orden.obra_efectiva,
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
    pdf_path = settings.GENERATED_PDF_DIR / f"OS_{orden.id}_{orden.numero.replace('-', '_')}.pdf"
    try:
        generate_orden_suministro(pdf_path, _datos_pdf(orden))
        orden.pdf_path = str(pdf_path)
        orden.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF orden de suministro %s: %s", orden.numero, e)


def _base_url(request):
    return settings.PUBLIC_URL or request.build_absolute_uri("/").rstrip("/")


def link_publico_pdf(orden, request):
    return f"{_base_url(request)}/api/v1/publico/ordenes/{orden.token_publico}/pdf/"


def mensaje_planta(orden, request):
    """Texto del aviso a planta (WhatsApp y cuerpo del correo)."""
    lineas = [
        f"*Orden de suministro {orden.numero}* — Triturados y Concretos",
        f"Planta: {orden.planta.nombre}",
        f"Cliente: {orden.cotizacion.solicitud.cliente.nombre}",
    ]
    if orden.obra_efectiva:
        lineas.append(f"Obra: {orden.obra_efectiva}")
    if orden.fecha_suministro:
        lineas.append(f"Fecha de suministro: {orden.fecha_suministro:%d/%m/%Y}")
    lineas.append("")
    lineas.append("Material:")
    for oi in orden.items.select_related("cotizacion_item__material"):
        m = oi.cotizacion_item.material
        lineas.append(f"• {m.nombre}: {_cantidad(oi.cantidad)} {m.unidad_medida}")
    placas = _placas(orden.placas_empresa) + _placas(orden.placas_cliente)
    if placas:
        lineas.append("")
        lineas.append(f"Placas autorizadas: {', '.join(placas)}")
    if orden.notas:
        lineas.append(f"Observación: {orden.notas}")
    lineas.append("")
    lineas.append(f"Formato PDF: {link_publico_pdf(orden, request)}")
    return "\n".join(lineas)


def numero_whatsapp(numero):
    """"312 834 2898" → "573128342898". Un celular colombiano de 10 dígitos lleva el 57."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) == 10 and digitos.startswith("3"):
        digitos = "57" + digitos
    return digitos


def _con_extras(orden, request):
    data = OrdenSuministroSerializer(orden).data
    num = numero_whatsapp(orden.planta.whatsapp)
    texto = quote(mensaje_planta(orden, request))
    # Sin número configurado igual se arma: WhatsApp deja elegir el contacto.
    data["whatsapp_url"] = f"https://wa.me/{num}?text={texto}" if num else f"https://wa.me/?text={texto}"
    data["link_pdf_publico"] = link_publico_pdf(orden, request)
    data["email_configurado"] = settings.EMAIL_CONFIGURADO
    return data


def _ordenes_qs(user):
    qs = (
        OrdenSuministro.objects
        .select_related("planta", "cotizacion__solicitud__cliente", "notificada_por", "creado_por")
        .prefetch_related("items__cotizacion_item__material", "despachos__items")
    )
    limitadas = plantas_de(user)
    return qs.filter(planta_id__in=limitadas) if limitadas is not None else qs


def _validar_items(cotizacion, planta, items):
    """[(cotizacion_item, cantidad)] validados contra el saldo por ordenar."""
    if not items:
        raise ValueError("La orden debe tener al menos un material.")
    lineas = {i.id: i for i in cotizacion.items.select_related("material", "planta")}
    salida = []
    for it in items:
        ci = lineas.get(int(it.get("cotizacion_item") or 0))
        if not ci:
            raise ValueError("Un material no pertenece a esta cotización.")
        if not ci.planta_efectiva or ci.planta_efectiva.id != planta.id:
            raise ValueError(f"{ci.material.nombre} no se cotizó en {planta.nombre}.")
        try:
            cantidad = Decimal(str(it.get("cantidad")))
        except (InvalidOperation, TypeError):
            raise ValueError(f"La cantidad de {ci.material.nombre} no es un número.")
        if cantidad <= 0:
            continue
        saldo = ci.cantidad - sum((oi.cantidad for oi in ci.ordenes_items.all()), Decimal("0"))
        if cantidad > saldo:
            raise ValueError(
                f"De {ci.material.nombre} quedan {_cantidad(saldo)} {ci.material.unidad_medida} por ordenar."
            )
        salida.append((ci, cantidad))
    if not salida:
        raise ValueError("Indica cuánto se entrega de al menos un material.")
    return salida


class OrdenSuministroListView(APIView):
    permission_classes = [Requiere(LEER_ORDENES, ("ordenes",))]

    def get(self, request):
        ordenes = _ordenes_qs(request.user)
        for campo in ("planta", "cotizacion"):
            valor = request.query_params.get(campo)
            if valor:
                ordenes = ordenes.filter(**{f"{campo}_id": valor})
        # Con el link de WhatsApp ya armado: el navegador tiene que abrirlo en
        # el mismo clic, sin esperar otra respuesta, o lo bloquea.
        return Response([_con_extras(o, request) for o in ordenes])

    def post(self, request):
        d = request.data
        cotizacion = Cotizacion.objects.filter(id=d.get("cotizacion")).first()
        if not cotizacion:
            return Response({"detail": "Cotización no encontrada"}, status=404)
        if not cotizacion.habilita_ordenes:
            return Response({
                "detail": "La cotización necesita estar aprobada y tener un pago aprobado "
                          "o una orden de compra del cliente.",
            }, status=400)
        planta = Planta.objects.filter(id=d.get("planta")).first()
        if not planta:
            return Response({"detail": "Planta no encontrada"}, status=404)

        with transaction.atomic():
            # Bloquea la cotización: dos órdenes simultáneas no pueden pasarse del saldo.
            Cotizacion.objects.select_for_update().filter(id=cotizacion.id).first()
            try:
                lineas = _validar_items(cotizacion, planta, d.get("items") or [])
            except ValueError as e:
                return Response({"detail": str(e)}, status=400)
            orden = OrdenSuministro.objects.create(
                numero=_numero_orden(), cotizacion=cotizacion, planta=planta,
                obra=(d.get("obra") or "").strip() or None,
                fecha_suministro=d.get("fecha_suministro") or None,
                placas_empresa=(d.get("placas_empresa") or "").strip() or None,
                placas_cliente=(d.get("placas_cliente") or "").strip() or None,
                notas=(d.get("notas") or "").strip() or None,
                creado_por=request.user,
            )
            OrdenSuministroItem.objects.bulk_create([
                OrdenSuministroItem(orden=orden, cotizacion_item=ci, cantidad=c) for ci, c in lineas
            ])
        Seguimiento.objects.create(
            solicitud=cotizacion.solicitud, tipo="nota", usuario=request.user,
            texto=f"Orden de suministro {orden.numero} emitida para {planta.nombre}.",
        )
        # Recargada: las fechas llegaron como texto y el PDF las necesita como fecha.
        orden = _ordenes_qs(request.user).get(id=orden.id)
        _generar_pdf(orden)
        return Response(_con_extras(orden, request), status=201)


class CotizacionesPorOrdenarView(APIView):
    """Cotizaciones con las que se puede emitir orden: aprobadas, con algo
    pagado o con orden de compra, y con material pendiente por ordenar."""
    permission_classes = [Requiere(("ordenes",))]

    def get(self, request):
        cotizaciones = (
            Cotizacion.objects.filter(estado="aprobada")
            .select_related("solicitud__cliente", "planta", "creado_por", "aprobado_por")
            .prefetch_related("items__material", "items__planta", "items__ordenes_items",
                              "ajustes", "pagos", "ordenes_suministro__items__cotizacion_item")
        )
        salida = []
        for c in cotizaciones:
            if not c.habilita_ordenes:
                continue
            if all(sum((oi.cantidad for oi in i.ordenes_items.all()), Decimal("0")) >= i.cantidad for i in c.items.all()):
                continue
            data = CotizacionSerializer(c).data
            data["obra"] = c.solicitud.obra
            salida.append(data)
        return Response(salida)


# Lo que se completa después de emitida la orden: cuándo retira el cliente,
# con qué vehículos y cualquier observación para la planta.
CAMPOS_EDITABLES = ("fecha_suministro", "placas_empresa", "placas_cliente", "notas", "obra")


class OrdenSuministroDetailView(APIView):
    # Las placas también las corrige la planta en portería.
    permission_classes = [Requiere(LEER_ORDENES, ("ordenes", "despachos"))]

    def get(self, request, orden_id):
        orden = _ordenes_qs(request.user).filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(_con_extras(orden, request))

    def patch(self, request, orden_id):
        orden = _ordenes_qs(request.user).filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        for k in CAMPOS_EDITABLES:
            if k in request.data:
                v = request.data[k]
                setattr(orden, k, (v.strip() if isinstance(v, str) else v) or None)
        orden.save()
        orden = _ordenes_qs(request.user).get(id=orden.id)
        _generar_pdf(orden)
        return Response(_con_extras(orden, request))

    def delete(self, request, orden_id):
        """Anular una orden mal emitida, mientras no tenga despachos."""
        if not tiene(request.user, "ordenes"):
            return Response({"detail": "No tienes permiso para anular órdenes."}, status=403)
        orden = _ordenes_qs(request.user).filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        if orden.despachos.exists():
            return Response({"detail": "La orden ya tiene despachos; no se puede anular."}, status=400)
        Seguimiento.objects.create(
            solicitud=orden.cotizacion.solicitud, tipo="nota", usuario=request.user,
            texto=f"Orden de suministro {orden.numero} anulada.",
        )
        orden.delete()
        return Response(status=204)


class OrdenSuministroNotificarView(APIView):
    """Registra el aviso a planta y, si se pide, manda el correo.

    WhatsApp lo abre el navegador con `whatsapp_url` (tiene que ser en el
    mismo clic, o el navegador bloquea la ventana); aquí solo se registra.
    """
    permission_classes = [Requiere(("ordenes",))]

    def post(self, request, orden_id):
        orden = _ordenes_qs(request.user).filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        canales = [c for c in (request.data.get("canales") or []) if c in ("whatsapp", "email", "manual")]
        if not canales:
            return Response({"detail": "Indica por dónde se notificó"}, status=400)

        if "email" in canales:
            if not settings.EMAIL_CONFIGURADO:
                return Response({"detail": "El correo no está configurado en el servidor (EMAIL_HOST)."}, status=400)
            if not orden.planta.email:
                return Response({"detail": f"{orden.planta.nombre} no tiene correo configurado."}, status=400)
            if not orden.pdf_path or not Path(orden.pdf_path).exists():
                _generar_pdf(orden)
            correo = EmailMessage(
                subject=f"Orden de suministro {orden.numero} — {orden.cotizacion.solicitud.cliente.nombre}",
                body=mensaje_planta(orden, request).replace("*", ""),
                to=[orden.planta.email],
                reply_to=[request.user.email] if request.user.email else None,
            )
            if orden.pdf_path and Path(orden.pdf_path).exists():
                correo.attach_file(orden.pdf_path, mimetype="application/pdf")
            try:
                correo.send()
            except Exception as e:
                logger.error("No se pudo enviar el correo de la orden %s: %s", orden.numero, e)
                return Response({"detail": f"No se pudo enviar el correo: {e}"}, status=502)

        orden.notificada_planta = True
        orden.fecha_notificacion = timezone.now()
        orden.notificada_por = request.user
        orden.canales_notificacion = sorted(set((orden.canales_notificacion or []) + canales))
        orden.save(update_fields=["notificada_planta", "fecha_notificacion", "notificada_por", "canales_notificacion"])
        return Response(_con_extras(orden, request))


class OrdenSuministroPdfView(APIView):
    permission_classes = [Requiere(LEER_ORDENES)]

    def get(self, request, orden_id):
        orden = _ordenes_qs(request.user).filter(id=orden_id).first()
        if not orden:
            return Response({"detail": "No encontrada"}, status=404)
        # Siempre fresco: refleja placas y fechas recién cargadas.
        _generar_pdf(orden)
        path = Path(orden.pdf_path) if orden.pdf_path else None
        if not path or not path.exists():
            return Response({"detail": "PDF no disponible"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"{orden.numero}.pdf")


class OrdenSuministroPdfPublicoView(APIView):
    """El PDF por el link que va en el WhatsApp/correo: el token es la credencial."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, token):
        orden = OrdenSuministro.objects.filter(token_publico=token).first()
        if not orden:
            return Response({"detail": "Link no válido"}, status=404)
        _generar_pdf(orden)
        path = Path(orden.pdf_path) if orden.pdf_path else None
        if not path or not path.exists():
            return Response({"detail": "PDF no disponible"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", filename=f"{orden.numero}.pdf")
