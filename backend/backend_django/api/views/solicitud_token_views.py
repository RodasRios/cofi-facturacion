"""Link de pedidos: el cliente pide cotizaciones sin entrar al sistema.

El comercial genera el link desde la ficha del cliente y se lo pasa una vez;
el cliente lo guarda y lo usa cada vez que necesita material. Cada envío crea
una ``SolicitudCotizacion`` pendiente — el primer paso del flujo comercial,
que en el diagrama arranca precisamente en el cliente.

A diferencia del link de vinculación, este **no es de un solo uso**: es la
puerta permanente de ese cliente. Por eso se puede revocar.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle

from api.models import (
    Cliente, Material, SolicitudCotizacion, SolicitudCotizacionItem, SolicitudToken,
)
from api.permissions import Requiere
from api.serializers import SolicitudCotizacionSerializer, SolicitudTokenSerializer
from api.views.solicitud_views import _numero_solicitud


class SolicitudPublicaThrottle(AnonRateThrottle):
    scope = "solicitud_publica"


class SolicitudTokenListCreateView(APIView):
    permission_classes = [Requiere(("clientes",))]

    def get(self, request):
        tokens = SolicitudToken.objects.select_related("cliente", "creado_por")
        cliente_id = request.query_params.get("cliente")
        if cliente_id:
            tokens = tokens.filter(cliente_id=cliente_id)
        return Response(SolicitudTokenSerializer(tokens, many=True).data)

    def post(self, request):
        cliente = Cliente.objects.filter(id=request.data.get("cliente")).first()
        if not cliente:
            return Response({"detail": "Cliente no encontrado"}, status=404)

        # Un solo link vivo por cliente: si ya tiene uno, se devuelve ese en vez
        # de llenar la lista de links equivalentes.
        existente = next(
            (t for t in cliente.tokens_solicitud.all() if t.utilizable), None,
        )
        if existente:
            return Response(SolicitudTokenSerializer(existente).data, status=200)

        token = SolicitudToken.objects.create(cliente=cliente, creado_por=request.user)
        return Response(SolicitudTokenSerializer(token).data, status=201)


class SolicitudTokenRevocarView(APIView):
    permission_classes = [Requiere(("clientes",))]

    def delete(self, request, token_id):
        token = SolicitudToken.objects.filter(id=token_id).first()
        if not token:
            return Response({"detail": "No encontrado"}, status=404)
        token.activo = False
        token.save(update_fields=["activo"])
        return Response(SolicitudTokenSerializer(token).data)


class SolicitudPublicaView(APIView):
    """Formulario público de pedido. El token del link es la credencial."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [SolicitudPublicaThrottle]

    def get(self, request, token):
        ct = SolicitudToken.objects.filter(token=token).select_related("cliente").first()
        if not ct:
            return Response({"detail": "Este link no existe."}, status=404)
        if not ct.utilizable:
            motivos = {
                "vencido": "Este link venció. Solicita uno nuevo a tu asesor comercial.",
                "revocado": "Este link fue anulado. Solicita uno nuevo a tu asesor comercial.",
            }
            return Response({"detail": motivos[ct.estado], "estado": ct.estado}, status=410)

        # El catálogo va SIN precios: la cotización la arma la empresa después.
        materiales = Material.objects.filter(activo=True).values(
            "id", "nombre", "tipo", "unidad_medida",
        )
        return Response({
            "cliente_nombre": ct.cliente.nombre,
            "materiales": list(materiales),
        })

    def post(self, request, token):
        items = request.data.get("items") or []
        if not items:
            return Response({"detail": "Agrega al menos un material."}, status=400)

        with transaction.atomic():
            ct = (
                SolicitudToken.objects.select_for_update()
                .filter(token=token).select_related("cliente").first()
            )
            if not ct:
                return Response({"detail": "Este link no existe."}, status=404)
            if not ct.utilizable:
                return Response({"detail": "Este link ya no es válido.", "estado": ct.estado}, status=410)

            # Se validan los materiales antes de crear nada, para no dejar una
            # solicitud a medias si el cliente manda un id que no existe.
            lineas = []
            for it in items:
                material = Material.objects.filter(id=it.get("material"), activo=True).first()
                if not material:
                    return Response({"detail": "Uno de los materiales no está disponible."}, status=400)
                try:
                    cantidad = float(it.get("cantidad") or 0)
                except (TypeError, ValueError):
                    return Response({"detail": "Las cantidades deben ser números."}, status=400)
                if cantidad <= 0:
                    return Response({"detail": "Las cantidades deben ser mayores que cero."}, status=400)
                lineas.append((material, cantidad))

            solicitud = SolicitudCotizacion.objects.create(
                numero=_numero_solicitud(),
                cliente=ct.cliente,
                obra=(request.data.get("obra") or "").strip()[:200] or None,
                notas=request.data.get("notas"),
                # La pidió el cliente, no un usuario del sistema. Se atribuye a
                # quien generó el link para que la solicitud tenga dueño.
                creado_por=ct.creado_por,
            )
            for material, cantidad in lineas:
                SolicitudCotizacionItem.objects.create(
                    solicitud=solicitud, material=material, cantidad=cantidad,
                )

            ct.usos += 1
            ct.ultimo_uso_at = timezone.now()
            ct.save(update_fields=["usos", "ultimo_uso_at"])

        return Response({
            "detail": "Recibimos tu solicitud. Un asesor comercial te enviará la cotización.",
            "numero": solicitud.numero,
            "solicitud": SolicitudCotizacionSerializer(solicitud).data,
        }, status=201)
