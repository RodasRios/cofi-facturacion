from rest_framework import serializers
from .models import (
    User, Planta, Material, MaterialPlanta, Cliente, ClienteToken,
    SolicitudCotizacion, SolicitudCotizacionItem,
    Cotizacion, CotizacionItem, Pago, OrdenSuministro, Seguimiento,
    Despacho, DespachoItem,
)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


class UserOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "nombre", "rol", "is_admin", "is_active", "firma_path", "created_at"]


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "nombre", "rol", "is_admin", "is_active", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        user.set_password(password or User.objects.make_random_password())
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PlantaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Planta
        fields = ["id", "nombre", "ubicacion", "activa", "created_at"]


class MaterialPlantaSerializer(serializers.ModelSerializer):
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)

    class Meta:
        model = MaterialPlanta
        fields = ["id", "material", "planta", "planta_nombre", "precio_unitario"]


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
            "id", "nombre", "nit", "telefono", "email", "direccion", "numero_vinculacion",
            "vinculado", "pdf_path", "creado_por", "creado_por_username", "created_at",
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


class SolicitudCotizacionSerializer(serializers.ModelSerializer):
    items = SolicitudCotizacionItemSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    tiene_cotizacion = serializers.SerializerMethodField()
    cotizaciones_rechazadas = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudCotizacion
        fields = [
            "id", "numero", "cliente", "cliente_nombre", "estado", "notas",
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

    class Meta:
        model = CotizacionItem
        fields = ["id", "material", "material_nombre", "unidad_medida", "cantidad", "precio_unitario", "subtotal"]


class CotizacionSerializer(serializers.ModelSerializer):
    items = CotizacionItemSerializer(many=True, read_only=True)
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)
    solicitud_numero = serializers.CharField(source="solicitud.numero", read_only=True)
    cliente_nombre = serializers.CharField(source="solicitud.cliente.nombre", read_only=True)
    creado_por_username = serializers.CharField(source="creado_por.username", read_only=True)
    aprobado_por_username = serializers.CharField(source="aprobado_por.username", read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tiene_orden_suministro = serializers.SerializerMethodField()
    tiene_pago = serializers.SerializerMethodField()
    pagos_rechazados = serializers.SerializerMethodField()

    class Meta:
        model = Cotizacion
        fields = [
            "id", "numero", "solicitud", "solicitud_numero", "cliente_nombre",
            "planta", "planta_nombre", "estado", "aprobado_por", "aprobado_por_username",
            "fecha_aprobacion", "motivo_rechazo", "notas", "pdf_path", "items", "total",
            "creado_por", "creado_por_username", "tiene_orden_suministro",
            "tiene_pago", "pagos_rechazados", "created_at",
        ]
        read_only_fields = ["numero", "estado", "creado_por", "aprobado_por", "fecha_aprobacion", "pdf_path"]

    def get_tiene_orden_suministro(self, obj):
        return hasattr(obj, "orden_suministro")

    def get_tiene_pago(self, obj):
        """Solo cuenta el pago vivo — uno rechazado deja subir otro comprobante."""
        return obj.pago_vigente is not None

    def get_pagos_rechazados(self, obj):
        return sum(1 for p in obj.pagos.all() if p.estado == "rechazado")


class PagoSerializer(serializers.ModelSerializer):
    cotizacion_numero = serializers.CharField(source="cotizacion.numero", read_only=True)
    aprobado_por_username = serializers.CharField(source="aprobado_por.username", read_only=True)

    class Meta:
        model = Pago
        fields = [
            "id", "cotizacion", "cotizacion_numero", "monto", "comprobante_path",
            "estado", "aprobado_por", "aprobado_por_username", "fecha_aprobacion",
            "motivo_rechazo", "creado_por", "created_at",
        ]
        read_only_fields = ["estado", "creado_por", "aprobado_por", "fecha_aprobacion", "comprobante_path"]


class OrdenSuministroSerializer(serializers.ModelSerializer):
    planta_nombre = serializers.CharField(source="planta.nombre", read_only=True)
    cotizacion_numero = serializers.CharField(source="cotizacion.numero", read_only=True)
    cliente_nombre = serializers.CharField(source="cotizacion.solicitud.cliente.nombre", read_only=True)
    items = CotizacionItemSerializer(source="cotizacion.items", many=True, read_only=True)

    class Meta:
        model = OrdenSuministro
        fields = [
            "id", "numero", "cotizacion", "cotizacion_numero", "cliente_nombre",
            "planta", "planta_nombre", "notificada_planta", "fecha_notificacion",
            "notas", "pdf_path", "items", "creado_por", "created_at",
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
            "cliente_nombre", "fecha", "recibido_por", "cliente_retira", "placa_vehiculo",
            "notas", "pdf_path", "items", "creado_por", "created_at",
        ]
        read_only_fields = ["numero", "creado_por", "pdf_path"]
