from pathlib import Path
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework_simplejwt.tokens import AccessToken

from api.models import User
from api.serializers import LoginSerializer, UserOutSerializer


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
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "Credenciales inválidas"}, status=401)

        if not user.is_active:
            return Response({"detail": "Usuario inactivo"}, status=401)

        if not user.check_password(password):
            return Response({"detail": "Credenciales inválidas"}, status=401)

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
