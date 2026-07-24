from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .models import User


class FacturacionJWTAuthentication(JWTAuthentication):
    """JWT auth que usa nuestro modelo User personalizado (no AbstractUser)."""

    def get_user(self, validated_token):
        try:
            user_id = validated_token["user_id"]
        except KeyError:
            raise InvalidToken("Token no contiene user_id")
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise InvalidToken("Usuario no encontrado")
        if not user.is_active:
            raise InvalidToken("Usuario inactivo")
        return user
