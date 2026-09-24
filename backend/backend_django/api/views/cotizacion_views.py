import logging
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from decimal import Decimal, InvalidOperation
from django.db import transaction
from api.models import (
    Cotizacion, CotizacionItem, CotizacionAjuste, SolicitudCotizacion, Planta, Material,
    MaterialPlanta, Seguimiento,
)
from services.notas_cotizacion import NOTAS_ACLARATORIAS, CLAVES as CLAVES_NOTAS
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


def _etiqueta_ajuste(ajuste):
    """"Descuento comercial (5%)" / "Flete" — el % se ve en el documento."""
    if ajuste.modo == "porcentaje":
        return f"{ajuste.descripcion} ({ajuste.valor.normalize():f}%)"
    return ajuste.descripcion


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
        "subtotal_materiales": cotizacion.subtotal_materiales,
        "ajustes": [
            {"descripcion": _etiqueta_ajuste(aj), "valor": valor}
            for aj, valor in cotizacion.ajustes_calculados
        ],
        "notas_aclaratorias": cotizacion.notas_aclaratorias,
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


def _validar_lineas(items, planta_defecto, tipo_precio):
    """Líneas listas para crear, con su precio resuelto. Lanza ValueError.

    Cada línea elige de dónde sale su precio (`origen_precio`): la tarifa
    especial o detal de SU planta, o uno escrito a mano. Con tarifa, la planta
    TIENE que tener precio para ese material: antes caía a $0 en silencio y
    salían cotizaciones sin valores.
    """
    lineas = []
    for it in items:
        material = Material.objects.filter(id=it.get("material")).first()
        if not material:
            raise ValueError("Uno de los materiales no existe.")
        planta = planta_defecto
        if it.get("planta"):
            planta = Planta.objects.filter(id=it["planta"]).first()
            if not planta:
                raise ValueError(f"La planta {it['planta']} no existe.")
        try:
            cantidad = Decimal(str(it.get("cantidad") or 0))
        except InvalidOperation:
            raise ValueError(f"La cantidad de {material.nombre} no es un número.")
        if cantidad <= 0:
            raise ValueError(f"La cantidad de {material.nombre} debe ser mayor que cero.")

        origen = it.get("origen_precio") or tipo_precio
        if origen == "manual":
            try:
                precio = Decimal(str(it.get("precio_unitario")))
            except (InvalidOperation, TypeError):
                raise ValueError(f"Escribe el precio de {material.nombre} en {planta.nombre}.")
            if precio <= 0:
                raise ValueError(f"El precio de {material.nombre} debe ser mayor que cero.")
        elif origen in ("especial", "detal"):
            mp = MaterialPlanta.objects.filter(material=material, planta=planta).first()
            if not mp:
                raise ValueError(
                    f"{planta.nombre} no tiene precio para {material.nombre}. "
                    "Elige otra planta o escribe el precio a mano."
                )
            # El precio de tarifa lo pone el servidor: el que mande el navegador
            # se ignora, para que "especial" siempre sea el de la lista.
            precio = mp.precio(origen)
            # Sin tarifa detal en esa planta, precio() cae a la especial.
            if origen == "detal" and mp.precio_detal is None:
                origen = "especial"
        else:
            raise ValueError(f"Origen de precio desconocido: {origen}.")

        lineas.append({
            "material": material, "planta": planta, "cantidad": cantidad,
            "precio_unitario": precio, "origen_precio": origen,
        })
    return lineas


def _validar_ajustes(ajustes):
    """Cargos (flete…) y descuentos, validados. Lanza ValueError."""
    limpios = []
    for aj in ajustes:
        tipo, modo = aj.get("tipo"), aj.get("modo")
        descripcion = str(aj.get("descripcion") or "").strip()
        if tipo not in ("cargo", "descuento") or modo not in ("monto", "porcentaje"):
            raise ValueError("Ajuste inválido.")
        if not descripcion:
            raise ValueError("Cada cargo o descuento necesita una descripción.")
        try:
            valor = Decimal(str(aj.get("valor")))
        except (InvalidOperation, TypeError):
            raise ValueError(f"El valor de '{descripcion}' no es un número.")
        if valor <= 0:
            raise ValueError(f"El valor de '{descripcion}' debe ser mayor que cero.")
        if modo == "porcentaje" and valor > 100:
            raise ValueError(f"'{descripcion}' no puede superar el 100%.")
        limpios.append({
            "tipo": tipo, "modo": modo, "descripcion": descripcion[:200], "valor": valor,
            "aplica_iva": bool(aj.get("aplica_iva", True)),
        })
    return limpios


class NotasAclaratoriasView(APIView):
    """Catálogo de notas aclaratorias para las casillas de la cotización."""

    def get(self, request):
        return Response(NOTAS_ACLARATORIAS)


class CotizacionListCreateView(APIView):
    def get(self, request):
        cotizaciones = (
            Cotizacion.objects.select_related("solicitud__cliente", "planta", "creado_por")
            .prefetch_related("items__material", "items__planta", "ajustes", "pagos", "ordenes_suministro")
        )
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

        # Todo se valida ANTES de crear nada: una línea sin precio o un ajuste
        # mal formado no debe dejar una cotización a medias (ni en $0).
        try:
            lineas = _validar_lineas(items, planta, tipo_precio)
            ajustes = _validar_ajustes(d.get("ajustes") or [])
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        notas_elegidas = d.get("notas_aclaratorias")
        if notas_elegidas is not None:
            notas_elegidas = [c for c in notas_elegidas if c in CLAVES_NOTAS]

        with transaction.atomic():
            cotizacion = Cotizacion.objects.create(
                numero=_numero_cotizacion(), solicitud=solicitud, planta=planta,
                tipo_precio=tipo_precio, notas=(d.get("notas") or "").strip() or None,
                notas_aclaratorias=notas_elegidas, creado_por=request.user,
            )
            for ln in lineas:
                CotizacionItem.objects.create(cotizacion=cotizacion, **ln)
            for orden, aj in enumerate(ajustes):
                CotizacionAjuste.objects.create(cotizacion=cotizacion, orden=orden, **aj)

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
