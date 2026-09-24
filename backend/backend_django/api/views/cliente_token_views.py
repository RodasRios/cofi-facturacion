"""Links de vinculación para que el cliente llene sus propios datos.

El comercial genera un token, copia el link y se lo manda al cliente (WhatsApp,
correo, lo que sea). El cliente lo abre sin tener usuario en el sistema, llena
los mismos campos que pediría "Nuevo cliente", y al enviarlo se crea el
``Cliente`` con su ``numero_vinculacion`` y su PDF de vinculación, exactamente
como si lo hubiera cargado el comercial.

El link sirve una sola vez y vence a los ``VINCULACION_TOKEN_DIAS`` días.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle

from api.models import Cliente, ClienteToken, VINCULACION_TOKEN_DIAS
from api.permissions import Requiere
from api.serializers import (
    ClienteSerializer, ClienteTokenSerializer, VinculacionPublicaSerializer,
)
from api.views.cliente_views import _numero_vinculacion, _generar_pdf


class VinculacionPublicaThrottle(AnonRateThrottle):
    """El formulario público no pide login, así que se limita por IP."""
    scope = "vinculacion_publica"


class ClienteTokenListCreateView(APIView):
    permission_classes = [Requiere(("clientes",))]

    def get(self, request):
        tokens = ClienteToken.objects.select_related("cliente", "creado_por")
        return Response(ClienteTokenSerializer(tokens, many=True).data)

    def post(self, request):
        ser = ClienteTokenSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        token = ser.save(creado_por=request.user)
        return Response(
            {**ClienteTokenSerializer(token).data, "dias_validez": VINCULACION_TOKEN_DIAS},
            status=201,
        )


class ClienteTokenRevocarView(APIView):
    """Anula un link ya enviado (se mandó a quien no era, se repitió, etc.)."""
    permission_classes = [Requiere(("clientes",))]

    def delete(self, request, token_id):
        token = ClienteToken.objects.filter(id=token_id).first()
        if not token:
            return Response({"detail": "No encontrado"}, status=404)
        if token.usado_at:
            return Response({"detail": "Ese link ya fue usado, no se puede revocar."}, status=400)
        token.revocado = True
        token.save(update_fields=["revocado"])
        return Response(ClienteTokenSerializer(token).data)


class VinculacionPublicaView(APIView):
    """Formulario público. Sin autenticación: el token ES la credencial."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [VinculacionPublicaThrottle]

    def _get_token(self, token):
        return ClienteToken.objects.filter(token=token).first()

    def get(self, request, token):
        """El formulario consulta esto al abrirse para saber si el link sirve."""
        ct = self._get_token(token)
        if not ct:
            return Response({"detail": "Este link no existe."}, status=404)
        if not ct.utilizable:
            # Se distingue el motivo para que el cliente sepa qué pedir.
            motivos = {
                "usado": "Este link ya fue utilizado.",
                "vencido": "Este link venció. Solicita uno nuevo.",
                "revocado": "Este link fue anulado. Solicita uno nuevo.",
            }
            return Response({"detail": motivos[ct.estado], "estado": ct.estado}, status=410)
        return Response({"estado": ct.estado, "expira_at": ct.expira_at, "etiqueta": ct.etiqueta})

    def post(self, request, token):
        ser = VinculacionPublicaSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)

        # El token se bloquea y se revalida dentro de la transacción: sin esto,
        # dos envíos simultáneos del mismo link crearían dos clientes.
        with transaction.atomic():
            ct = ClienteToken.objects.select_for_update().filter(token=token).first()
            if not ct:
                return Response({"detail": "Este link no existe."}, status=404)
            if not ct.utilizable:
                return Response({"detail": "Este link ya no es válido.", "estado": ct.estado}, status=410)

            cliente = Cliente(**ser.validated_data)
            cliente.numero_vinculacion = _numero_vinculacion()
            cliente.creado_por = ct.creado_por
            cliente.save()

            ct.cliente = cliente
            ct.usado_at = timezone.now()
            ct.save(update_fields=["cliente", "usado_at"])

        # Fuera de la transacción: el PDF es un archivo en disco, y si falla no
        # debe tumbar la creación del cliente (_generar_pdf ya loguea el error).
        _generar_pdf(cliente)
        cliente.refresh_from_db()

        return Response(
            {
                "detail": "Datos recibidos. Tu formato de vinculación quedó generado.",
                "numero_vinculacion": cliente.numero_vinculacion,
                "cliente": ClienteSerializer(cliente).data,
            },
            status=201,
        )
