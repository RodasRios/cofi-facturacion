from decimal import Decimal
from django.db import models
from django.contrib.auth.hashers import make_password, check_password as django_check_password


ROL_CHOICES = [
    ("comercial", "Comercial"),
    ("aprobador", "Aprobador"),
    ("financiera", "Financiera"),
    ("planta", "Planta"),
]


class User(models.Model):
    username = models.CharField(max_length=50, unique=True, db_index=True)
    email = models.EmailField(max_length=254, unique=True, null=True, blank=True)
    hashed_password = models.CharField(max_length=255)
    nombre = models.CharField(max_length=150, blank=True, null=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="comercial")
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    firma_path = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.username

    def set_password(self, raw_password):
        self.hashed_password = make_password(raw_password)

    def check_password(self, raw_password):
        return django_check_password(raw_password, self.hashed_password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False


class Planta(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    ubicacion = models.CharField(max_length=250, blank=True, null=True)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "plantas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


MATERIAL_TIPO_CHOICES = [
    ("triturado", "Triturado"),
    ("agregado", "Agregado"),
    ("otro", "Otro"),
]


class Material(models.Model):
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=20, choices=MATERIAL_TIPO_CHOICES, default="agregado")
    unidad_medida = models.CharField(max_length=20, default="m3")
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "materiales"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class MaterialPlanta(models.Model):
    """Precio de un material en una planta específica."""
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="precios_planta")
    planta = models.ForeignKey(Planta, on_delete=models.CASCADE, related_name="precios_material")
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "material_plantas"
        unique_together = [["material", "planta"]]

    def __str__(self):
        return f"{self.material.nombre} @ {self.planta.nombre}: {self.precio_unitario}"


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    nit = models.CharField(max_length=40, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    direccion = models.CharField(max_length=300, blank=True, null=True)
    vinculado = models.BooleanField(default=False)
    documento_vinculacion_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="clientes_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clientes"
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre


SOLICITUD_ESTADO_CHOICES = [
    ("pendiente", "Pendiente"),
    ("cotizada", "Cotizada"),
    ("cerrada", "Cerrada"),
]


class SolicitudCotizacion(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="solicitudes")
    estado = models.CharField(max_length=20, choices=SOLICITUD_ESTADO_CHOICES, default="pendiente")
    notas = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="solicitudes_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "solicitudes_cotizacion"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero


class SolicitudCotizacionItem(models.Model):
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "solicitud_cotizacion_items"


COTIZACION_ESTADO_CHOICES = [
    ("pendiente_aprobacion", "Pendiente de aprobación"),
    ("aprobada", "Aprobada"),
    ("rechazada", "Rechazada"),
]


class Cotizacion(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    solicitud = models.OneToOneField(SolicitudCotizacion, on_delete=models.CASCADE, related_name="cotizacion")
    planta = models.ForeignKey(Planta, on_delete=models.PROTECT, related_name="cotizaciones")
    estado = models.CharField(max_length=25, choices=COTIZACION_ESTADO_CHOICES, default="pendiente_aprobacion")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="cotizaciones_aprobadas")
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="cotizaciones_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cotizaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero

    @property
    def total(self) -> Decimal:
        return sum((i.subtotal for i in self.items.all()), Decimal("0"))


class CotizacionItem(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "cotizacion_items"

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.precio_unitario


PAGO_ESTADO_CHOICES = [
    ("pendiente", "Pendiente"),
    ("aprobado", "Aprobado"),
    ("rechazado", "Rechazado"),
]


class Pago(models.Model):
    cotizacion = models.OneToOneField(Cotizacion, on_delete=models.CASCADE, related_name="pago")
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    comprobante_path = models.CharField(max_length=500, blank=True, null=True)
    estado = models.CharField(max_length=20, choices=PAGO_ESTADO_CHOICES, default="pendiente")
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pagos_aprobados")
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="pagos_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pagos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pago {self.cotizacion.numero}"


class OrdenSuministro(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    cotizacion = models.OneToOneField(Cotizacion, on_delete=models.CASCADE, related_name="orden_suministro")
    planta = models.ForeignKey(Planta, on_delete=models.PROTECT, related_name="ordenes_suministro")
    notificada_planta = models.BooleanField(default=False)
    fecha_notificacion = models.DateTimeField(null=True, blank=True)
    notas = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ordenes_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ordenes_suministro"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero


class Despacho(models.Model):
    """Formato de Control de Despacho y Recibo de Material (Remisión)."""
    numero = models.CharField(max_length=50, unique=True)
    orden_suministro = models.ForeignKey(OrdenSuministro, on_delete=models.CASCADE, related_name="despachos")
    fecha = models.DateField()
    recibido_por = models.CharField(max_length=200, blank=True, null=True)
    cliente_retira = models.BooleanField(default=True)
    placa_vehiculo = models.CharField(max_length=20, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="despachos_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "despachos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero


class DespachoItem(models.Model):
    despacho = models.ForeignKey(Despacho, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "despacho_items"
