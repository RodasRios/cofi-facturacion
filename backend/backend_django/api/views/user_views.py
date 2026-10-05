"""Gestión de usuarios (panel Usuarios).

Lo usa quien tenga el permiso `usuarios` (Administrador nivel 1 y nivel 2, y el
superusuario). La regla es jerárquica, como en `cofi-gestor-insumos`
(`permissions.rango`: superusuario 3, nivel 1 = 2, nivel 2 = 1, puestos 0):

- Solo se gestiona a quien está **por debajo** de uno; el superusuario, a todos.
- Solo se dan roles **por debajo** del propio rango: el nivel 1 nombra niveles
  2, el nivel 2 solo puestos, y únicamente el superusuario nombra niveles 1 y
  superusuarios.
- Quien no es nivel 1 ni superusuario solo da permisos que él mismo tiene: un
  nivel 2 no puede crear aprobadores.
- Nadie se cambia sus propios roles ni se quita el acceso, y siempre queda al
  menos un superusuario activo.
"""
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import User, Cotizacion, Pago
from api.serializers import UserOutSerializer, UserWriteSerializer
from api.permissions import (
    Requiere, rango, permisos_de, permisos_de_roles, validar_roles, ROLES,
)


def _otros_superusuarios(user):
    return User.objects.filter(is_superadmin=True, is_active=True).exclude(id=user.id).exists()


def _si(data, campo):
    return str(data.get(campo, "")).lower() in ("true", "1")


def _validar_privilegios(actor, data, objetivo=None):
    """Lo que el actor pide dar (roles, superusuario, permisos adicionales)
    debe quedar por debajo de su rango. Devuelve un mensaje de error o None."""
    if actor.is_superadmin:
        return None
    if _si(data, "is_superadmin") or (objetivo and objetivo.is_superadmin and "is_superadmin" in data):
        return "Solo el superusuario nombra superusuarios."
    mio = rango(actor)
    if "roles" in data:
        roles, err = validar_roles(data["roles"] or [])
        if err:
            return err
        if rango(roles=roles) >= mio:
            nombre = ROLES[roles[0]]["label"] if roles else ""
            return f"No puedes dar el rol {nombre}: solo alguien de rango superior lo asigna."
    else:
        roles = objetivo.roles if objetivo else []
    extra = data.get("permisos_extra", data.get("permisos")) if ("permisos_extra" in data or "permisos" in data) else None
    if mio < 2:
        # Un nivel 2 no reparte lo que él no tiene (aprobar cotizaciones o pagos).
        propios = permisos_de(actor)
        pedidos = permisos_de_roles(roles) | set(extra or [])
        ajenos = sorted(pedidos - propios)
        if ajenos:
            return f"No puedes dar permisos que no tienes: {', '.join(ajenos)}."
    return None


class UserListCreateView(APIView):
    permission_classes = [Requiere(("usuarios",))]

    def get(self, request):
        usuarios = User.objects.prefetch_related("plantas").order_by("-is_active", "-is_superadmin", "-is_admin", "nombre", "username")
        return Response(UserOutSerializer(usuarios, many=True).data)

    def post(self, request):
        error = _validar_privilegios(request.user, request.data)
        if error:
            return Response({"detail": error}, status=403)
        ser = UserWriteSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
        if User.objects.filter(username__iexact=ser.validated_data["username"]).exists():
            return Response({"username": ["Ya existe un usuario con ese nombre."]}, status=400)
        user = ser.save()
        return Response(UserOutSerializer(user).data, status=201)


class UserDetailView(APIView):
    permission_classes = [Requiere(("usuarios",))]

    def _objetivo(self, request, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return None, Response({"detail": "No encontrado"}, status=404)
        actor = request.user
        if user.id != actor.id and not actor.is_superadmin and rango(user) >= rango(actor):
            return None, Response(
                {"detail": "Solo alguien de rango superior puede modificar a este usuario."}, status=403,
            )
        return user, None

    def patch(self, request, user_id):
        user, error = self._objetivo(request, user_id)
        if error:
            return error
        data = request.data
        es_yo = user.id == request.user.id
        quita = lambda campo: campo in data and str(data[campo]).lower() in ("false", "0")

        if es_yo and ("roles" in data or "permisos_extra" in data or "permisos" in data
                      or quita("is_active") or quita("is_superadmin")):
            return Response({"detail": "No puedes cambiar tus propios roles ni quitarte el acceso."}, status=400)
        if user.is_superadmin and (quita("is_superadmin") or quita("is_active")) and not _otros_superusuarios(user):
            return Response({"detail": "Debe quedar al menos un superusuario activo."}, status=400)
        error = _validar_privilegios(request.user, data, user)
        if error:
            return Response({"detail": error}, status=403)

        if "username" in data and User.objects.filter(
            username__iexact=str(data["username"]).strip(),
        ).exclude(id=user.id).exists():
            return Response({"username": ["Ya existe un usuario con ese nombre."]}, status=400)

        ser = UserWriteSerializer(user, data=data, partial=True)
        if not ser.is_valid():
            return Response(ser.errors, status=400)
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


class PanelUsuariosView(APIView):
    """Salud del equipo: las alertas que piden una decisión.

    Lo que importa no es cuánta gente hay sino si el flujo se puede trabar:
    nadie que apruebe pagos o cotizaciones, nadie que despache, personas sin
    rol, claves temporales sin cambiar.
    """
    permission_classes = [Requiere(("usuarios",))]

    def get(self, request):
        activos = [u for u in User.objects.filter(is_active=True)]
        con = lambda clave: [u for u in activos if clave in permisos_de(u)]
        alertas = []
        for clave, texto in (
            ("aprobar_pagos", "Nadie puede aprobar pagos: los abonos se quedan esperando."),
            ("aprobar_cotizaciones", "Nadie puede aprobar cotizaciones."),
            ("despachos", "Nadie puede registrar despachos."),
            ("ordenes", "Nadie puede emitir órdenes de suministro."),
        ):
            if not con(clave):
                alertas.append({"tipo": "sin_" + clave, "nivel": "grave", "texto": texto})
        sin_rol = [u for u in activos if not u.is_superadmin and not u.roles and not u.permisos]
        if sin_rol:
            alertas.append({"tipo": "sin_rol", "nivel": "aviso",
                            "texto": f"{len(sin_rol)} persona(s) activa(s) sin rol: no ven ninguna pestaña."})
        clave_temp = [u for u in activos if u.debe_cambiar_password]
        if clave_temp:
            alertas.append({"tipo": "clave_temporal", "nivel": "info",
                            "texto": f"{len(clave_temp)} persona(s) aún no cambian su contraseña temporal."})

        por_rol = {r: 0 for r in ROLES}
        for u in activos:
            for r in u.roles or []:
                if r in por_rol:
                    por_rol[r] += 1
        return Response({
            "activos": len(activos),
            "inactivos": User.objects.filter(is_active=False).count(),
            "administradores": sum(1 for u in activos if rango(u) > 0),
            "clave_temporal": len(clave_temp),
            "por_rol": por_rol,
            "esperando_aprobacion": {
                "cotizaciones": Cotizacion.objects.filter(estado="pendiente_aprobacion").count(),
                "pagos": Pago.objects.filter(Q(estado="pendiente") | Q(estado="por_confirmar")).count(),
            },
            "alertas": alertas,
        })
