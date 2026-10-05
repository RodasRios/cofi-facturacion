"""Roles y permisos — fuente única de verdad de quién puede qué.

Modelo traído de `cofi-gestor-insumos` (`api/permisos.py`), adaptado al flujo
de facturación:

- **Permiso** = una pestaña o una acción (`PERMISOS`). Las vistas preguntan
  SIEMPRE por permiso (`Requiere(...)`, `tiene()`), nunca por rol ni por
  `is_admin`: así un rol nuevo no obliga a revisar veinte archivos.
- **Rol** = un puesto real (`ROLES`). Una persona tiene uno o varios
  (`User.roles`): los niveles de administración van solos; los puestos se
  combinan (la misma persona puede ser Comercial y Logística).
- **Permisos adicionales** (`User.permisos`): ajuste fino por persona, se suman
  a los de sus roles. Sirven para los casos raros sin inventar un rol.

Permisos efectivos = permisos de sus roles ∪ adicionales. `is_admin` (lo pone
el rol Administrador nivel 1, ver `User.save`) además abre todo lo que no sea
EXCLUSIVO.

CÓMO AGREGAR UN ROL: clave en `ROLES` y sus permisos en `PERMISOS_DE_ROL`
(y lo mismo en `frontend/src/lib/permisos.ts`).
CÓMO PROTEGER UNA ACCIÓN NUEVA: clave en `PERMISOS`, inclúyela en los roles
que la tengan, y en la vista `Requiere(("clave",))`.
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
    ("usuarios", "Usuarios", "Crear usuarios y asignarles roles y permisos"),
]
CLAVES = [p[0] for p in PERMISOS]

# Permisos que ni un Administrador nivel 1 tendría por serlo (habría que
# dárselos a propósito). Hoy ninguno: el dueño decidió que el nivel 1 tiene
# todo, incluido aprobar pagos. Se deja el mecanismo por si vuelve a hacer falta.
EXCLUSIVOS = set()
APROBACIONES = {"aprobar_cotizaciones", "aprobar_pagos"}


# ── Roles ─────────────────────────────────────────────────────────────────────
#
# Cada rol es un puesto del flujo comercial, no un nivel genérico de acceso.

ROL_ADMIN = "admin"
ROL_COORDINADOR = "coordinador"

ROLES = {
    ROL_ADMIN: {
        "label": "Administrador nivel 1",
        "descripcion": "Todo: aprobar cotizaciones y pagos, precios y usuarios.",
    },
    ROL_COORDINADOR: {
        "label": "Administrador nivel 2",
        "descripcion": "Todo el trabajo diario, precios y usuarios, pero no aprueba cotizaciones ni pagos.",
    },
    "comercial": {
        "label": "Comercial",
        "descripcion": "Clientes, solicitudes, cotizaciones, registro de pagos y órdenes de suministro.",
    },
    "aprobador": {
        "label": "Gerencia (aprobador)",
        "descripcion": "Aprueba o rechaza las cotizaciones.",
    },
    "financiera": {
        "label": "Financiera",
        "descripcion": "Registra y aprueba pagos, confirma órdenes de compra y lleva la cartera.",
    },
    "logistica": {
        "label": "Logística",
        "descripcion": "Emite las órdenes de suministro, avisa a la planta y sigue los despachos.",
    },
    "despacho": {
        "label": "Despacho (báscula)",
        "descripcion": "Registra los despachos y sube la foto o PDF del tiquete.",
    },
    "disponibilidad": {
        "label": "Disponibilidad (planta)",
        "descripcion": "Actualiza qué material hay en planta.",
    },
}
ROLES_ADMINISTRACION = [ROL_ADMIN, ROL_COORDINADOR]
PUESTOS = [r for r in ROLES if r not in ROLES_ADMINISTRACION]

_TODO = set(CLAVES)
PERMISOS_DE_ROL = {
    ROL_ADMIN: _TODO - EXCLUSIVOS,
    ROL_COORDINADOR: _TODO - APROBACIONES,
    "comercial": {"tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"},
    "aprobador": {"tablero", "aprobar_cotizaciones"},
    "financiera": {"tablero", "pagos", "aprobar_pagos"},
    "logistica": {"tablero", "ordenes", "despachos"},
    "despacho": {"despachos"},
    "disponibilidad": {"disponibilidad"},
}

# Permisos de partida que recibieron los usuarios de antes de los permisos por
# pestaña, según su `User.rol` de entonces. Lo usa la migración 0012: no tocar.
PERMISOS_POR_ROL = {
    "comercial": ["tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"],
    "aprobador": ["tablero", "aprobar_cotizaciones"],
    "financiera": ["tablero", "pagos", "aprobar_pagos"],
    "planta": ["despachos", "disponibilidad"],
}

# Quién responde por cada paso del tablero ("le toca a"). Tener permiso no es
# lo mismo que ser responsable: un admin puede registrar un pago, pero es
# trabajo de financiera o del comercial. Solo si nadie tiene el puesto se nombra
# a quien tenga el permiso (en la práctica, los administradores).
RESPONSABLES_POR_PERMISO = {
    "cotizaciones": ["comercial"],
    "aprobar_cotizaciones": ["aprobador"],
    "pagos": ["comercial", "financiera"],
    "aprobar_pagos": ["financiera"],
    "ordenes": ["logistica", "comercial"],
    "despachos": ["despacho", "logistica"],
}


def ordenar_roles(roles):
    orden = list(ROLES)
    return sorted({r for r in roles if r in ROLES}, key=orden.index)


def permisos_de_roles(roles):
    p = set()
    for r in roles or []:
        p |= PERMISOS_DE_ROL.get(r, set())
    return p


def permisos_de(user):
    """Permisos efectivos: roles ∪ adicionales (∪ todo lo no exclusivo si es admin)."""
    efectivos = permisos_de_roles(user.roles) | set(user.permisos or [])
    if user.is_admin:
        efectivos |= _TODO - EXCLUSIVOS
    return efectivos


def rango(user=None, roles=None, superadmin=False):
    """Nivel jerárquico: 3 superusuario, 2 nivel 1, 1 nivel 2, 0 puestos.

    Regla de gestión: solo se toca a quien está por debajo, y solo se dan roles
    por debajo del propio rango (el superusuario puede todo).
    """
    if user is not None:
        roles, superadmin = user.roles or [], user.is_superadmin or superadmin
        if user.is_admin and ROL_ADMIN not in roles:
            roles = [*roles, ROL_ADMIN]
    if superadmin:
        return 3
    if ROL_ADMIN in (roles or []):
        return 2
    if ROL_COORDINADOR in (roles or []):
        return 1
    return 0


def validar_roles(roles):
    """Normaliza la lista de roles. Devuelve (roles, error)."""
    if not isinstance(roles, (list, tuple)):
        return None, "Los roles deben ser una lista."
    desconocidos = [r for r in roles if r not in ROLES]
    if desconocidos:
        return None, f"Roles desconocidos: {', '.join(desconocidos)}."
    roles = ordenar_roles(roles)
    if any(r in ROLES_ADMINISTRACION for r in roles) and len(roles) > 1:
        return None, "Un nivel de administración va solo: ya incluye lo que hacen los demás puestos."
    return roles, None


def tiene(user, *claves):
    if not (user and user.is_authenticated):
        return False
    efectivos = permisos_de(user)
    return any(c in efectivos for c in claves)


def plantas_de(user):
    """IDs de las plantas a las que está limitado el usuario, o None si ve todas."""
    if rango(user) > 0:
        return None
    ids = list(user.plantas.values_list("id", flat=True))
    return ids or None


def responsables(permiso, equipo, planta_id=None):
    """A quién le toca un paso: [{"id", "nombre"}]. `equipo` = usuarios activos
    con sus plantas precargadas (ver `equipo()`)."""
    puestos = set(RESPONSABLES_POR_PERMISO.get(permiso, []))

    def cubre_planta(u):
        return planta_id is None or not u._plantas or planta_id in u._plantas

    candidatos = [u for u in equipo if permiso in u._permisos and cubre_planta(u)]
    elegidos = [u for u in candidatos if puestos & set(u.roles or [])] or candidatos
    return [{"id": u.id, "nombre": u.nombre or u.username} for u in elegidos]


def equipo():
    """Usuarios activos con permisos y plantas ya calculados (una consulta)."""
    from api.models import User
    gente = list(User.objects.filter(is_active=True).prefetch_related("plantas").order_by("nombre", "username"))
    for u in gente:
        u._permisos = permisos_de(u)
        u._plantas = {p.id for p in u.plantas.all()} if rango(u) == 0 else set()
    return gente


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
