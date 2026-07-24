from rest_framework.permissions import BasePermission


def _has_rol(user, *roles):
    return bool(
        user
        and user.is_authenticated
        and (user.is_admin or user.rol in roles)
    )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsComercial(BasePermission):
    def has_permission(self, request, view):
        return _has_rol(request.user, "comercial")


class IsAprobador(BasePermission):
    def has_permission(self, request, view):
        return _has_rol(request.user, "aprobador")


class IsFinanciera(BasePermission):
    def has_permission(self, request, view):
        return _has_rol(request.user, "financiera")


class IsPlanta(BasePermission):
    def has_permission(self, request, view):
        return _has_rol(request.user, "planta")
