from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework_simplejwt.tokens import AccessToken

from api.models import User
from django.http import FileResponse
from django.utils import timezone

from api.serializers import LoginSerializer, UserOutSerializer, PerfilSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request):
        data = request.data
        if hasattr(data, "dict"):
            data = data.dict()

        ser = LoginSerializer(data=data)
        if not ser.is_valid():
            return Response({"detail": "Datos inválidos"}, status=400)

        username = ser.validated_data["username"]
        password = ser.validated_data["password"]

        try:
            user = User.objects.get(username__iexact=username.strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return Response({"detail": "Credenciales inválidas"}, status=401)

        if not user.is_active:
            return Response({"detail": "Usuario inactivo"}, status=401)

        if not user.check_password(password):
            return Response({"detail": "Credenciales inválidas"}, status=401)

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        token = AccessToken.for_user(user)
        return Response({"access_token": str(token), "token_type": "bearer"})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserOutSerializer(request.user).data)


class UserFirmaView(APIView):
    """Firma digital del usuario — se estampa en los PDFs que aprueba (cotización, orden)."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No se envió archivo"}, status=400)
        ext = Path(file.name).suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg"]:
            return Response({"detail": "Solo PNG o JPG. Se recomienda PNG con fondo transparente."}, status=400)

        firma_dir = settings.UPLOAD_DIR / "firmas"
        firma_dir.mkdir(parents=True, exist_ok=True)
        dest = firma_dir / f"firma_user_{request.user.id}{ext}"

        with dest.open("wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        request.user.firma_path = str(dest)
        request.user.save(update_fields=["firma_path"])
        return Response({"detail": "Firma actualizada", "firma_path": str(dest)})

    def get(self, request):
        """La imagen de la firma propia, para verla en Configuración."""
        path = request.user.firma_path
        if not path or not Path(path).exists():
            return Response({"detail": "Sin firma"}, status=404)
        return FileResponse(open(path, "rb"))

    def delete(self, request):
        old = request.user.firma_path
        request.user.firma_path = None
        request.user.save(update_fields=["firma_path"])
        if old:
            try:
                Path(old).unlink(missing_ok=True)
            except Exception:
                pass
        return Response(status=204)


class PerfilView(APIView):
    """Datos propios: nombre, correo, cédula, cargo, teléfono.

    Salen bajo la firma en la cotización, la orden y el control de despachos.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        ser = PerfilSerializer(request.user, data=request.data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        email = ser.validated_data.get("email")
        if email and User.objects.filter(email__iexact=email).exclude(id=request.user.id).exists():
            return Response({"email": ["Ese correo ya lo usa otro usuario."]}, status=400)
        ser.save()
        return Response(UserOutSerializer(request.user).data)


class CambiarPasswordView(APIView):
    """Cambio de contraseña propio. En el primer ingreso (contraseña puesta por
    otra persona) no se pide la actual: el usuario acaba de entrar con ella."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        actual = request.data.get("actual") or ""
        nueva = request.data.get("nueva") or ""
        if not user.debe_cambiar_password and not user.check_password(actual):
            return Response({"detail": "La contraseña actual no es correcta."}, status=400)
        if user.check_password(nueva):
            return Response({"detail": "La nueva contraseña debe ser distinta de la actual."}, status=400)
        if len(nueva) < 8:
            return Response({"detail": "La nueva contraseña debe tener al menos 8 caracteres."}, status=400)
        user.set_password(nueva)
        user.debe_cambiar_password = False
        user.save(update_fields=["hashed_password", "debe_cambiar_password"])
        return Response(UserOutSerializer(user).data)
