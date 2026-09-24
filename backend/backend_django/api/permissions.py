"""Permisos por pestaña.

Cada usuario tiene una lista de permisos (`User.permisos`) que el superusuario
o un admin marcan en Configuración → Usuarios. Un permiso abre una pestaña (y
lo que hace falta leer para trabajar en ella); los de aprobación van aparte
para poder separar quien arma de quien aprueba. `is_admin` los tiene todos.

`User.rol` quedó solo como etiqueta de área (sale en el tablero como
"responsable"); ya no decide qué puede hacer nadie.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

# (clave, pestaña, descripción) — el orden es el de la barra de navegación.
PERMISOS = [
    ("tablero", "Tablero", "Ver el tablero, los indicadores y la cartera por cobrar"),
    ("clientes", "Clientes", "Crear clientes y generar sus links de vinculación y pedidos"),
    ("solicitudes", "Solicitudes", "Registrar solicitudes de cotización"),
    ("cotizaciones", "Cotizaciones", "Armar cotizaciones"),
    ("aprobar_cotizaciones", "Cotizaciones", "Aprobar o rechazar cotizaciones"),
    ("pagos", "Pagos", "Registrar pagos, abonos y órdenes de compra del cliente"),
    ("aprobar_pagos", "Pagos", "Aprobar pagos y confirmar órdenes de compra"),
    ("ordenes", "Órdenes", "Crear órdenes de suministro y notificar a planta"),
    ("despachos", "Despachos", "Registrar despachos y subir su soporte"),
    ("disponibilidad", "Disponibilidad", "Actualizar la disponibilidad de material en planta"),
    ("precios", "Plantas y precios", "Editar plantas, materiales y precios"),
]
CLAVES = [p[0] for p in PERMISOS]

# Permisos de partida para los usuarios que existían antes, según su rol.
PERMISOS_POR_ROL = {
    "comercial": ["tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"],
    "aprobador": ["tablero", "aprobar_cotizaciones"],
    "financiera": ["tablero", "pagos", "aprobar_pagos"],
    "planta": ["despachos", "disponibilidad"],
}


def tiene(user, *claves):
    if not (user and user.is_authenticated):
        return False
    if user.is_admin:
        return True
    propios = set(user.permisos or [])
    return any(c in propios for c in claves)


def plantas_de(user):
    """IDs de las plantas a las que está limitado el usuario, o None si ve todas."""
    if user.is_admin:
        return None
    ids = list(user.plantas.values_list("id", flat=True))
    return ids or None


def Requiere(lectura=(), escritura=None):
    """Clase de permiso: `lectura` para GET, `escritura` para lo demás.

    Sin `escritura`, se exige lo mismo para todo. Con lectura vacía, basta
    estar autenticado para leer.
    """
    escritura = lectura if escritura is None else escritura

    class _Permiso(BasePermission):
        message = "No tienes permiso para esta sección."

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            claves = lectura if request.method in SAFE_METHODS else escritura
            return True if not claves else tiene(request.user, *claves)

    return _Permiso


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superadmin)
