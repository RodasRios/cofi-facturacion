"""Gestión de usuarios (Configuración → Usuarios).

Dos niveles:
- admin: crea y edita usuarios normales (comercial, aprobador, financiera, planta).
- superusuario: además crea, edita y elimina administradores y otros
  superusuarios. Es la cuenta del dueño del sistema.

Nadie puede quitarse a sí mismo el acceso (desactivarse, bajarse de admin o
eliminarse), y siempre queda al menos un superusuario activo.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import User
from api.serializers import UserOutSerializer, UserWriteSerializer
from api.permissions import IsAdmin

CAMPOS_PRIVILEGIO = ("is_admin", "is_superadmin")


def _puede_gestionar(actor, objetivo):
    """Un admin no toca cuentas de administradores; el superusuario toca todas."""
    return actor.is_superadmin or not (objetivo.is_admin or objetivo.is_superadmin)


def _pide_privilegio(data):
    return any(str(data.get(c, "")).lower() in ("true", "1") for c in CAMPOS_PRIVILEGIO)


def _otros_superusuarios(user):
    return User.objects.filter(is_superadmin=True, is_active=True).exclude(id=user.id).exists()


class UserListCreateView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        usuarios = User.objects.order_by("-is_active", "-is_superadmin", "-is_admin", "username")
        return Response(UserOutSerializer(usuarios, many=True).data)

    def post(self, request):
        if _pide_privilegio(request.data) and not request.user.is_superadmin:
            return Response({"detail": "Solo el superusuario puede crear administradores."}, status=403)
        ser = UserWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        if User.objects.filter(username__iexact=ser.validated_data["username"]).exists():
            return Response({"username": ["Ya existe un usuario con ese nombre."]}, status=400)
        user = ser.save()
        return Response(UserOutSerializer(user).data, status=201)


class UserDetailView(APIView):
    permission_classes = [IsAdmin]

    def _objetivo(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return None, Response({"detail": "No encontrado"}, status=404)
        if not _puede_gestionar(request.user, user):
            return None, Response(
                {"detail": "Solo el superusuario puede modificar a un administrador."}, status=403,
            )
        return user, None

    def patch(self, request, user_id):
        user, error = self._objetivo(request, user_id)
        if error:
            return error
        data = request.data
        if _pide_privilegio(data) and not request.user.is_superadmin:
            return Response({"detail": "Solo el superusuario puede dar permisos de administrador."}, status=403)

        es_yo = user.id == request.user.id
        quita = lambda campo: campo in data and str(data[campo]).lower() in ("false", "0")
        if es_yo and (quita("is_active") or quita("is_admin") or quita("is_superadmin")):
            return Response({"detail": "No puedes quitarte tu propio acceso."}, status=400)
        if user.is_superadmin and (quita("is_superadmin") or quita("is_active")) and not _otros_superusuarios(user):
            return Response({"detail": "Debe quedar al menos un superusuario activo."}, status=400)

        if "username" in data and User.objects.filter(
            username__iexact=str(data["username"]).strip(),
        ).exclude(id=user.id).exists():
            return Response({"username": ["Ya existe un usuario con ese nombre."]}, status=400)

        ser = UserWriteSerializer(user, data=data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        # Quitar el superusuario también baja de admin, salvo que se pida lo contrario.
        if quita("is_superadmin") and "is_admin" not in data:
            ser.validated_data["is_admin"] = False
        ser.save()
        # Si alguien restablece su propia contraseña desde aquí, no hay por qué obligarlo a cambiarla.
        if es_yo and user.debe_cambiar_password:
            user.debe_cambiar_password = False
            user.save(update_fields=["debe_cambiar_password"])
        return Response(UserOutSerializer(user).data)

    def delete(self, request, user_id):
        """Borra de verdad solo si el usuario no tiene documentos; si los tiene,
        hay que desactivarlo, para no dejar cotizaciones sin firmante."""
        user, error = self._objetivo(request, user_id)
        if error:
            return error
        if user.id == request.user.id:
            return Response({"detail": "No puedes eliminar tu propio usuario."}, status=400)
        if user.is_superadmin and not _otros_superusuarios(user):
            return Response({"detail": "Debe quedar al menos un superusuario activo."}, status=400)
        if user.tiene_documentos():
            return Response({
                "detail": f"{user.username} ya creó o aprobó documentos. Desactívalo en vez de "
                          "eliminarlo: así no podrá entrar y sus documentos conservan su nombre.",
                "tiene_documentos": True,
            }, status=409)
        user.delete()
        return Response(status=204)
