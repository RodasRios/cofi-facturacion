from rest_framework import serializers
from .models import (
    User, Planta, Material, MaterialPlanta, Cliente, ClienteToken,
    SolicitudCotizacion, SolicitudCotizacionItem,
    Cotizacion, CotizacionItem, CotizacionAjuste, Pago, OrdenSuministro, Seguimiento, SolicitudToken,
    Despacho, DespachoItem, OrdenSuministroItem,
)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class UserOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "username", "email", "nombre", "cedula", "rol", "cargo", "telefono",
            "is_admin", "is_superadmin", "is_active", "debe_cambiar_password",
            "permisos", "plantas", "firma_path", "last_login", "created_at",
        ]


class UserWriteSerializer(serializers.ModelSerializer):
    """Alta y edición de usuarios desde Configuración → Usuarios.

    Quién puede tocar qué (admin vs. superusuario) lo decide la vista; aquí
    solo se validan los datos.
    """
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "nombre", "cedula", "rol", "cargo", "telefono",
            "is_admin", "is_superadmin", "is_active", "password", "permisos", "plantas",
        ]
        extra_kwargs = {"plantas": {"required": False}}

    def validate_permisos(self, v):
        from api.permissions import CLAVES
        if not isinstance(v, list):
            raise serializers.ValidationError("Debe ser una lista.")
        desconocidos = [c for c in v if c not in CLAVES]
        if desconocidos:
            raise serializers.ValidationError(f"Permisos desconocidos: {', '.join(desconocidos)}")
        return [c for c in CLAVES if c in v]

    def validate_username(self, v):
        v = v.strip().lower()
        if not v:
            raise serializers.ValidationError("El usuario no puede estar vacío.")
        if " " in v:
            raise serializers.ValidationError("El usuario no puede tener espacios.")
        return v

    def validate_email(self, v):
        return (v or "").strip().lower() or None

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        plantas = validated_data.pop("plantas", None)
        if not password:
            raise serializers.ValidationError({"password": "Asigna una contraseña inicial."})
        user = User(**validated_data)
        user.set_password(password)
        # La puso otra persona: que la cambie al entrar.
        user.debe_cambiar_password = True
        user.save()
        if plantas is not None:
            user.plantas.set(plantas)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        plantas = validated_data.pop("plantas", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
            instance.debe_cambiar_password = True
        instance.save()
        if plantas is not None:
            instance.plantas.set(plantas)
        return instance


class PerfilSerializer(serializers.ModelSerializer):
    """Lo que cada usuario edita de sí mismo en Configuración → Mi cuenta."""

    class Meta:
        model = User
        fields = ["nombre", "email", "cedula", "cargo", "telefono"]

    def validate_email(self, v):
        return (v or "").strip().lower() or None


class PlantaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Planta
        fields = [
            "id", "nombre", "ubicacion", "activa", "whatsapp", "email",
            "nota_disponibilidad", "nota_actualizada_at", "created_at",
        ]
        read_only_fields = ["nota_actualizada_at"]


class MaterialPlantaSerializer(serializers.ModelSerializer):
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)
    material_nombre = serializers.CharField(source="material.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="material.unidad_medida", read_only=True)
    disponibilidad_actualizada_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = MaterialPlanta
        fields = [
            "id", "material", "material_nombre", "unidad_medida", "planta", "planta_nombre",
            "precio_especial", "precio_detal", "disponibilidad", "cantidad_disponible",
            "disponibilidad_nota", "disponibilidad_actualizada_at", "disponibilidad_actualizada_por_nombre",
        ]

    def get_disponibilidad_actualizada_por_nombre(self, obj):
        u = obj.disponibilidad_actualizada_por
        return (u.nombre or u.username) if u else None


class MaterialSerializer(serializers.ModelSerializer):
    precios = MaterialPlantaSerializer(source="precios_planta", many=True, read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Material
        fields = ["id", "nombre", "tipo", "tipo_display", "unidad_medida", "activo", "precios", "created_at"]


class ClienteSerializer(serializers.ModelSerializer):
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)

    class Meta:
        model = Cliente
        fields = [
            "id", "nombre", "nit", "telefono", "email", "direccion", "tipo_precio",
            "numero_vinculacion", "vinculado", "pdf_path",
            "creado_por", "creado_por_username", "created_at",
        ]
        read_only_fields = ["creado_por", "numero_vinculacion", "pdf_path"]


class ClienteTokenSerializer(serializers.ModelSerializer):
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    estado = serializers.CharField(read_only=True)

    class Meta:
        model = ClienteToken
        fields = [
            "id", "token", "etiqueta", "estado", "expira_at", "usado_at",
            "cliente", "cliente_nombre", "revocado",
            "creado_por", "creado_por_username", "created_at",
        ]
        read_only_fields = [
            "token", "estado", "expira_at", "usado_at", "cliente", "revocado", "creado_por",
        ]


class VinculacionPublicaSerializer(serializers.ModelSerializer):
    """Los mismos campos que llena el comercial en "Nuevo cliente"."""

    class Meta:
        model = Cliente
        fields = ["nombre", "nit", "telefono", "email", "direccion"]
        extra_kwargs = {"nombre": {"required": True, "allow_blank": False}}


class SolicitudCotizacionItemSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source="material.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="material.unidad_medida", read_only=True)

    class Meta:
        model = SolicitudCotizacionItem
        fields = ["id", "material", "material_nombre", "unidad_medida", "cantidad"]


class SeguimientoSerializer(serializers.ModelSerializer):
    usuario_username = serializers.CharField(source="usuario.username", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Seguimiento
        fields = [
            "id", "solicitud", "tipo", "tipo_display", "texto",
            "usuario", "usuario_username", "created_at",
        ]
        read_only_fields = ["solicitud", "usuario"]


class SolicitudTokenSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    estado = serializers.CharField(read_only=True)

    class Meta:
        model = SolicitudToken
        fields = [
            "id", "token", "cliente", "cliente_nombre", "estado", "activo", "expira_at",
            "usos", "ultimo_uso_at", "creado_por", "creado_por_username", "created_at",
        ]
        read_only_fields = [
            "token", "estado", "activo", "usos", "ultimo_uso_at", "creado_por",
        ]


class SolicitudCotizacionSerializer(serializers.ModelSerializer):
    items = SolicitudCotizacionItemSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    # La tarifa del cliente preselecciona los precios al armar la cotización.
    cliente_tipo_precio = serializers.CharField(source="cliente.tipo_precio", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    tiene_cotizacion = serializers.SerializerMethodField()
    cotizaciones_rechazadas = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudCotizacion
        fields = [
            "id", "numero", "cliente", "cliente_nombre", "cliente_tipo_precio", "estado", "obra", "notas",
            "items", "creado_por", "creado_por_username", "tiene_cotizacion",
            "cotizaciones_rechazadas", "created_at",
        ]
        read_only_fields = ["numero", "creado_por", "estado"]

    def get_tiene_cotizacion(self, obj):
        """Solo cuenta la cotización viva — una rechazada deja volver a cotizar."""
        return obj.cotizacion_vigente is not None

    def get_cotizaciones_rechazadas(self, obj):
        return sum(1 for c in obj.cotizaciones.all() if c.estado == "rechazada")


class CotizacionItemSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source="material.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="material.unidad_medida", read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    planta_nombre = serializers.SerializerMethodField()
    planta_efectiva = serializers.SerializerMethodField()
    cantidad_ordenada = serializers.SerializerMethodField()

    class Meta:
        model = CotizacionItem
        fields = [
            "id", "material", "material_nombre", "unidad_medida", "planta", "planta_nombre",
            "planta_efectiva", "cantidad", "precio_unitario", "origen_precio", "subtotal",
            "cantidad_ordenada",
        ]

    def get_planta_efectiva(self, obj):
        planta = obj.planta_efectiva
        return planta.id if planta else None

    def get_cantidad_ordenada(self, obj):
        """Lo que ya salió en órdenes de suministro; el resto es el saldo por ordenar."""
        return str(sum((oi.cantidad for oi in obj.ordenes_items.all()), 0))

    def get_planta_nombre(self, obj):
        """Cae a la planta de la cotización para las líneas viejas sin planta propia."""
        planta = obj.planta_efectiva
        return planta.nombre if planta else None


class CotizacionAjusteSerializer(serializers.ModelSerializer):
    valor_calculado = serializers.SerializerMethodField()

    class Meta:
        model = CotizacionAjuste
        fields = ["id", "tipo", "modo", "descripcion", "valor", "aplica_iva", "valor_calculado"]

    def get_valor_calculado(self, obj):
        """Con signo y ya resuelto el porcentaje: lo que suma o resta de verdad."""
        return str(obj.valor_sobre(obj.cotizacion.subtotal_materiales))


class CotizacionSerializer(serializers.ModelSerializer):
    items = CotizacionItemSerializer(many=True, read_only=True)
    ajustes = CotizacionAjusteSerializer(many=True, read_only=True)
    subtotal_materiales = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)
    solicitud_numero = serializers.CharField(source="solicitud.numero", read_only=True)
    cliente_nombre = serializers.CharField(source="solicitud.cliente.nombre", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    aprobado_por_username = serializers.CharField(source="aprobado_por.username", read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    iva = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tiene_orden_suministro = serializers.SerializerMethodField()
    plantas_nombres = serializers.SerializerMethodField()
    pagos_rechazados = serializers.SerializerMethodField()
    total_pagado = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_en_revision = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_por_confirmar = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    saldo_por_cobrar = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    saldo_sin_registrar = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    habilita_ordenes = serializers.BooleanField(read_only=True)
    porcentaje_ordenado = serializers.SerializerMethodField()

    class Meta:
        model = Cotizacion
        fields = [
            "id", "numero", "solicitud", "solicitud_numero", "cliente_nombre",
            "planta", "planta_nombre", "estado", "aprobado_por", "aprobado_por_username",
            "fecha_aprobacion", "motivo_rechazo", "notas", "pdf_path", "items",
            "tipo_precio", "iva_porcentaje", "subtotal_materiales", "ajustes",
            "subtotal", "iva", "total", "notas_aclaratorias",
            "creado_por", "creado_por_username", "tiene_orden_suministro",
            "plantas_nombres", "pagos_rechazados", "total_pagado", "total_en_revision",
            "total_por_confirmar", "saldo_por_cobrar", "saldo_sin_registrar",
            "habilita_ordenes", "porcentaje_ordenado", "created_at",
        ]
        read_only_fields = [
            "numero", "estado", "creado_por", "aprobado_por", "fecha_aprobacion",
            "pdf_path", "iva_porcentaje",
        ]

    def get_tiene_orden_suministro(self, obj):
        return obj.ordenes_suministro.exists()

    def get_plantas_nombres(self, obj):
        """Todas las plantas que despachan esta cotización, no solo la principal."""
        return [p.nombre for p in obj.plantas]

    def get_porcentaje_ordenado(self, obj):
        return round(float(obj.fraccion_ordenada) * 100)

    def get_pagos_rechazados(self, obj):
        return sum(1 for p in obj.pagos.all() if p.estado == "rechazado")


class PagoSerializer(serializers.ModelSerializer):
    cotizacion_numero = serializers.CharField(source="cotizacion.numero", read_only=True)
    cliente_nombre = serializers.CharField(source="cotizacion.solicitud.cliente.nombre", read_only=True)
    aprobado_por_username = serializers.CharField(source="aprobado_por.username", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id", "cotizacion", "cotizacion_numero", "cliente_nombre", "tipo", "tipo_display",
            "monto", "referencia", "fecha_pago", "notas", "comprobante_path",
            "estado", "estado_display", "aprobado_por", "aprobado_por_username", "fecha_aprobacion",
            "motivo_rechazo", "creado_por", "creado_por_username", "created_at",
        ]
        read_only_fields = ["estado", "creado_por", "aprobado_por", "fecha_aprobacion", "comprobante_path"]


class OrdenSuministroItemSerializer(serializers.ModelSerializer):
    material = serializers.IntegerField(source="cotizacion_item.material_id", read_only=True)
    material_nombre = serializers.CharField(source="cotizacion_item.material.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="cotizacion_item.material.unidad_medida", read_only=True)
    cantidad_despachada = serializers.SerializerMethodField()

    class Meta:
        model = OrdenSuministroItem
        fields = ["id", "cotizacion_item", "material", "material_nombre", "unidad_medida",
                  "cantidad", "cantidad_despachada"]

    def get_cantidad_despachada(self, obj):
        return str(obj.orden.cantidad_despachada(obj.cotizacion_item.material_id))


class OrdenSuministroSerializer(serializers.ModelSerializer):
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)
    planta_whatsapp = serializers.CharField(source="planta.whatsapp", read_only=True)
    planta_email = serializers.CharField(source="planta.email", read_only=True)
    cotizacion_numero = serializers.CharField(source="cotizacion.numero", read_only=True)
    cliente_nombre = serializers.CharField(source="cotizacion.solicitud.cliente.nombre", read_only=True)
    obra = serializers.CharField(source="obra_efectiva", read_only=True)
    notificada_por_username = serializers.CharField(source="notificada_por.username", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    items = OrdenSuministroItemSerializer(many=True, read_only=True)
    completamente_despachada = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrdenSuministro
        fields = [
            "id", "numero", "cotizacion", "cotizacion_numero", "cliente_nombre",
            "planta", "planta_nombre", "planta_whatsapp", "planta_email", "obra",
            "notificada_planta", "fecha_notificacion", "notificada_por_username", "canales_notificacion",
            "fecha_suministro", "placas_empresa", "placas_cliente",
            "notas", "pdf_path", "items", "completamente_despachada",
            "creado_por", "creado_por_username", "created_at",
        ]
        read_only_fields = ["numero", "creado_por", "pdf_path", "notificada_planta", "fecha_notificacion"]


class DespachoItemSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source="material.nombre", read_only=True)
    unidad_medida = serializers.CharField(source="material.unidad_medida", read_only=True)

    class Meta:
        model = DespachoItem
        fields = ["id", "material", "material_nombre", "unidad_medida", "cantidad"]


class DespachoSerializer(serializers.ModelSerializer):
    items = DespachoItemSerializer(many=True, read_only=True)
    orden_suministro_numero = serializers.CharField(source="orden_suministro.numero", read_only=True)
    planta_nombre = serializers.CharField(source="orden_suministro.planta.nombre", read_only=True)
    cliente_nombre = serializers.CharField(source="orden_suministro.cotizacion.solicitud.cliente.nombre", read_only=True)

    class Meta:
        model = Despacho
        fields = [
            "id", "numero", "orden_suministro", "orden_suministro_numero", "planta_nombre",
            "cliente_nombre", "consecutivo", "fecha", "recibido_por", "cliente_retira", "placa_vehiculo",
            "notas", "pdf_path", "soporte_path", "items", "creado_por", "created_at",
        ]
        read_only_fields = ["numero", "creado_por", "pdf_path", "soporte_path"]
