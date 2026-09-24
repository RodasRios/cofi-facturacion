import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import (
    Cotizacion, CotizacionItem, SolicitudCotizacion, Planta, Material, MaterialPlanta,
    Seguimiento,
)
from api.serializers import CotizacionSerializer
from api.permissions import IsAprobador
from services.pdf_service import generate_cotizacion

logger = logging.getLogger(__name__)


def _numero_cotizacion():
    """Consecutivo por año, como el formato FR-GC-08 de la empresa: 160-2026.

    COTIZACION_CONSECUTIVO_INICIAL es el último número emitido fuera del
    sistema, para seguir la numeración real sin saltos (si la última cotización
    hecha a mano fue la 159, se pone 159 y la primera del sistema sale 160).
    Las cotizaciones viejas con formato COT-0001 no entran en la cuenta.
    """
    anio = timezone.localdate().year
    del_anio = Cotizacion.objects.filter(numero__endswith=f"-{anio}").count()
    return f"{settings.COTIZACION_CONSECUTIVO_INICIAL + del_anio + 1}-{anio}"


def _datos_pdf(cotizacion):
    """Arma los datos del formato FR-GC-08 a partir de la cotización."""
    cliente = cotizacion.solicitud.cliente

    # Una sección de la tabla por planta, en el orden en que aparecen.
    grupos, por_planta = [], {}
    for i in cotizacion.items.select_related("material", "planta"):
        planta = i.planta_efectiva
        nombre = planta.nombre if planta else "-"
        if nombre not in por_planta:
            por_planta[nombre] = {"planta": nombre, "items": []}
            grupos.append(por_planta[nombre])
        por_planta[nombre]["items"].append({
            "descripcion": i.material.nombre, "unidad": i.material.unidad_medida,
            "cantidad": i.cantidad, "precio": i.precio_unitario, "subtotal": i.subtotal,
        })

    # Firma el comercial que armó la cotización, como en el formato en papel.
    firmante = cotizacion.creado_por
    return {
        "numero": cotizacion.numero,
        "fecha": timezone.localtime(cotizacion.created_at).date(),
        "cliente": {
            "nombre": cliente.nombre, "nit": cliente.nit,
            "telefono": cliente.telefono, "email": cliente.email,
        },
        "grupos": grupos,
        "subtotal": cotizacion.subtotal,
        "iva": cotizacion.iva,
        "iva_porcentaje": cotizacion.iva_porcentaje,
        "total": cotizacion.total,
        "plantas": [(p.nombre, p.ubicacion) for p in cotizacion.plantas],
        "firmante": {
            "nombre": (firmante.nombre or firmante.username) if firmante else "",
            "cargo": firmante.cargo if firmante else None,
            "telefono": firmante.telefono if firmante else None,
            "email": firmante.email if firmante else None,
            "firma_path": firmante.firma_path if firmante else None,
        },
        "notas": cotizacion.notas,
    }


def _generar_pdf(cotizacion):
    pdf_dir = settings.GENERATED_PDF_DIR
    pdf_path = pdf_dir / f"COT_{cotizacion.id}_{cotizacion.numero.replace('-', '_')}.pdf"
    try:
        generate_cotizacion(pdf_path, _datos_pdf(cotizacion))
        cotizacion.pdf_path = str(pdf_path)
        cotizacion.save(update_fields=["pdf_path"])
    except Exception as e:
        logger.error("Error generando PDF cotización %s: %s", cotizacion.numero, e)


class CotizacionListCreateView(APIView):
    def get(self, request):
        cotizaciones = Cotizacion.objects.select_related("solicitud__cliente", "planta").prefetch_related("items")
        estado = request.query_params.get("estado")
        if estado:
            cotizaciones = cotizaciones.filter(estado=estado)
        return Response(CotizacionSerializer(cotizaciones, many=True).data)

    def post(self, request):
        d = request.data
        solicitud_id = d.get("solicitud")
        planta_id = d.get("planta")
        items = d.get("items") or []
        if not solicitud_id or not planta_id:
            return Response({"detail": "solicitud y planta son requeridos"}, status=400)
        if not items:
            return Response({"detail": "La cotización debe tener al menos un ítem"}, status=400)

        solicitud = SolicitudCotizacion.objects.filter(id=solicitud_id).first()
        if not solicitud:
            return Response({"detail": "Solicitud no encontrada"}, status=404)

        # Las rechazadas no cuentan: la gracia es poder volver a cotizar.
        vigente = solicitud.cotizacion_vigente
        if vigente:
            return Response(
                {"detail": f"Esta solicitud ya tiene la cotización {vigente.numero} en curso"},
                status=400,
            )
        es_reintento = solicitud.cotizaciones.exists()
        planta = Planta.objects.filter(id=planta_id).first()
        if not planta:
            return Response({"detail": "Planta no encontrada"}, status=404)

        # La tarifa viene del cliente, salvo que se pida otra explícitamente.
        tipo_precio = d.get("tipo_precio") or solicitud.cliente.tipo_precio

        cotizacion = Cotizacion.objects.create(
            numero=_numero_cotizacion(), solicitud=solicitud, planta=planta,
            tipo_precio=tipo_precio, notas=d.get("notas"), creado_por=request.user,
        )
        for it in items:
            material = Material.objects.filter(id=it.get("material")).first()
            if not material:
                continue
            # Cada línea puede salir de una planta distinta; sin "planta" en el
            # ítem se usa la de la cotización (comportamiento de siempre).
            planta_item = planta
            if it.get("planta"):
                p = Planta.objects.filter(id=it["planta"]).first()
                if not p:
                    return Response({"detail": f"Planta {it['planta']} no encontrada"}, status=404)
                planta_item = p
            # El precio es el de ESA planta: repartir entre plantas con precios
            # distintos tiene que dar el precio correcto en cada línea.
            mp = MaterialPlanta.objects.filter(material=material, planta=planta_item).first()
            CotizacionItem.objects.create(
                cotizacion=cotizacion, material=material, planta=planta_item,
                cantidad=it.get("cantidad") or 0,
                precio_unitario=(
                    mp.precio(tipo_precio) if mp else (it.get("precio_unitario") or 0)
                ),
            )

        solicitud.estado = "cotizada"
        solicitud.save(update_fields=["estado"])

        if es_reintento:
            Seguimiento.objects.create(
                solicitud=solicitud, tipo="cotizacion_nueva", usuario=request.user,
                texto=f"Se armó la cotización {cotizacion.numero} tras el rechazo anterior.",
            )

        cotizacion.refresh_from_db()
        _generar_pdf(cotizacion)
        cotizacion.refresh_from_db()
        return Response(CotizacionSerializer(cotizacion).data, status=201)


class CotizacionDetailView(APIView):
    def get_object(self, cotizacion_id):
        return Cotizacion.objects.filter(id=cotizacion_id).first()

    def get(self, request, cotizacion_id):
        cotizacion = self.get_object(cotizacion_id)
        if not cotizacion:
            return Response({"detail": "No encontrada"}, status=404)
        return Response(CotizacionSerializer(cotizacion).data)


class CotizacionAprobarView(APIView):
    permission_classes = [IsAprobador]

    def post(self, request, cotizacion_id):
        cotizacion = Cotizacion.objects.filter(id=cotizacion_id).first()
        if not cotizacion:
            return Response({"detail": "No encontrada"}, status=404)
        if cotizacion.estado != "pendiente_aprobacion":
            return Response({"detail": "Esta cotización ya fue procesada"}, status=400)

        aprobar = request.data.get("aprobar", True)
        if aprobar:
            cotizacion.estado = "aprobada"
            cotizacion.aprobado_por = request.user
            cotizacion.fecha_aprobacion = timezone.now()
            cotizacion.save(update_fields=["estado", "aprobado_por", "fecha_aprobacion"])
            Seguimiento.objects.create(
                solicitud=cotizacion.solicitud, tipo="cotizacion_aprobada", usuario=request.user,
                texto=f"{cotizacion.numero} aprobada.",
            )
        else:
            motivo = request.data.get("motivo", "")
            cotizacion.estado = "rechazada"
            cotizacion.motivo_rechazo = motivo
            cotizacion.aprobado_por = request.user
            cotizacion.fecha_aprobacion = timezone.now()
            cotizacion.save(update_fields=["estado", "motivo_rechazo", "aprobado_por", "fecha_aprobacion"])

            # La solicitud vuelve a manos del comercial para que arme otra
            # cotización: es la flecha "No → SEGUIMIENTO CLIENTE" del flujo.
            solicitud = cotizacion.solicitud
            solicitud.estado = "en_seguimiento"
            solicitud.save(update_fields=["estado"])
            Seguimiento.objects.create(
                solicitud=solicitud, tipo="cotizacion_rechazada", usuario=request.user,
                texto=f"{cotizacion.numero} rechazada." + (f" Motivo: {motivo}" if motivo else ""),
            )

        cotizacion.refresh_from_db()
        return Response(CotizacionSerializer(cotizacion).data)


class CotizacionPdfView(APIView):
    def get(self, request, cotizacion_id):
        cotizacion = Cotizacion.objects.filter(id=cotizacion_id).first()
        if not cotizacion:
            return Response({"detail": "No encontrada"}, status=404)
        # Se regenera al abrirlo: así las cotizaciones emitidas antes del
        # formato FR-GC-08 también salen con él. Los valores no cambian porque
        # los precios de cada línea son una foto tomada al crearla.
        _generar_pdf(cotizacion)
        cotizacion.refresh_from_db()
        if not cotizacion.pdf_path:
            return Response({"detail": "PDF no disponible"}, status=404)
        path = Path(cotizacion.pdf_path)
        if not path.exists():
            return Response({"detail": "Archivo no encontrado"}, status=404)
        return FileResponse(path.open("rb"), content_type="application/pdf", as_attachment=True, filename=f"COT {cotizacion.numero}.pdf")
