import secrets
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
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
    # Dueño del sistema: único que crea o modifica administradores. Siempre es
    # admin también (ver save()), así todo lo que abre is_admin le aplica.
    is_superadmin = models.BooleanField(default=False)
    # La contraseña la puso otra persona (alta o restablecimiento): al entrar se
    # le pide cambiarla antes de dejarlo usar la app.
    debe_cambiar_password = models.BooleanField(default=False)
    firma_path = models.CharField(max_length=500, blank=True, null=True)
    # Aparecen bajo la firma en cotización, orden y control de despachos.
    cargo = models.CharField(max_length=120, blank=True, null=True)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    cedula = models.CharField(max_length=30, blank=True, null=True)
    # Pestañas y acciones que puede usar (claves de api.permissions.PERMISOS).
    # Un admin las tiene todas sin importar esta lista.
    permisos = models.JSONField(default=list, blank=True)
    # Si tiene plantas asignadas, solo ve y trabaja las órdenes, despachos y
    # disponibilidad de esas plantas. Vacío = todas.
    plantas = models.ManyToManyField("Planta", blank=True, related_name="usuarios")
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"

    def save(self, *args, **kwargs):
        if self.is_superadmin:
            self.is_admin = True
        super().save(*args, **kwargs)

    def tiene_documentos(self):
        """True si firmó, aprobó o creó algo: borrarlo dejaría esos documentos sin autor."""
        relaciones = [
            "clientes_creados", "tokens_cliente_creados", "solicitudes_creadas",
            "cotizaciones_aprobadas", "cotizaciones_creadas", "pagos_aprobados",
            "pagos_creados", "tokens_solicitud_creados", "seguimientos",
            "ordenes_creadas", "despachos_creados",
        ]
        return any(getattr(self, r).exists() for r in relaciones)

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
    # A dónde se avisa cuando se le emite una orden de suministro.
    whatsapp = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    # Aviso general de la planta ("sin despacho el sábado", "báscula en mantenimiento").
    nota_disponibilidad = models.CharField(max_length=300, blank=True, null=True)
    nota_actualizada_at = models.DateTimeField(null=True, blank=True)
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


TIPO_PRECIO_CHOICES = [
    ("especial", "Venta especial"),
    ("detal", "Venta página / clientes detal"),
]

# El IVA que aplica hoy a estos materiales. Se guarda una copia en cada
# cotización (`Cotizacion.iva_porcentaje`) para que un cambio de tarifa no
# altere documentos ya emitidos.
IVA_PORCENTAJE = Decimal("19")


DISPONIBILIDAD_CHOICES = [
    ("disponible", "Disponible"),
    ("limitada", "Poca disponibilidad"),
    ("agotada", "Agotado"),
]


class MaterialPlanta(models.Model):
    """Precio de un material en una planta específica, **sin IVA**.

    La lista de precios de la empresa maneja dos tarifas por material: la de
    venta especial (clientes con convenio) y la de detal. No todas las plantas
    tienen las dos — cuando falta la de detal se usa la especial.
    """
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name="precios_planta")
    planta = models.ForeignKey(Planta, on_delete=models.CASCADE, related_name="precios_material")
    precio_especial = models.DecimalField(max_digits=14, decimal_places=2)
    precio_detal = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # Disponibilidad: la actualiza la gente de planta desde su pestaña, y se ve
    # al cotizar para no ofrecer lo que no hay.
    disponibilidad = models.CharField(max_length=20, choices=DISPONIBILIDAD_CHOICES, default="disponible")
    cantidad_disponible = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    disponibilidad_nota = models.CharField(max_length=300, blank=True, null=True)
    disponibilidad_actualizada_at = models.DateTimeField(null=True, blank=True)
    disponibilidad_actualizada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        db_table = "material_plantas"
        unique_together = [["material", "planta"]]

    def __str__(self):
        return f"{self.material.nombre} @ {self.planta.nombre}: {self.precio_especial}"

    def precio(self, tipo_precio="especial"):
        """Precio sin IVA para la tarifa pedida, con respaldo en la especial."""
        if tipo_precio == "detal" and self.precio_detal is not None:
            return self.precio_detal
        return self.precio_especial


class Cliente(models.Model):
    nombre = models.CharField(max_length=200)
    nit = models.CharField(max_length=40, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, null=True)
    direccion = models.CharField(max_length=300, blank=True, null=True)
    # Tarifa que se le aplica por defecto al cotizarle.
    tipo_precio = models.CharField(max_length=20, choices=TIPO_PRECIO_CHOICES, default="especial")
    numero_vinculacion = models.CharField(max_length=50, unique=True, null=True)
    vinculado = models.BooleanField(default=False)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="clientes_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clientes"
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre


VINCULACION_TOKEN_DIAS = 3


def _generar_token():
    return secrets.token_urlsafe(32)


def _vencimiento_por_defecto():
    return timezone.now() + timedelta(days=VINCULACION_TOKEN_DIAS)


class ClienteToken(models.Model):
    """Link de un solo uso para que el cliente llene su propia vinculación.

    El comercial genera el token, copia el link y se lo manda al cliente. El
    cliente abre el link sin necesidad de tener usuario, llena los mismos datos
    que pediría el formulario de "Nuevo cliente", y al enviarlo se crea el
    ``Cliente`` con su ``numero_vinculacion`` y su PDF, igual que si lo hubiera
    creado el comercial a mano.
    """
    token = models.CharField(max_length=64, unique=True, db_index=True, default=_generar_token)
    # Referencia para que el comercial sepa de quién es cada link en la lista.
    etiqueta = models.CharField(max_length=200, blank=True, null=True)
    expira_at = models.DateTimeField(default=_vencimiento_por_defecto)
    usado_at = models.DateTimeField(null=True, blank=True)
    # Queda apuntando al cliente que se creó al usarlo, para poder rastrearlo.
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="tokens_vinculacion",
    )
    revocado = models.BooleanField(default=False)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="tokens_cliente_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cliente_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Token vinculación {self.etiqueta or self.token[:8]}"

    @property
    def vencido(self):
        return timezone.now() >= self.expira_at

    @property
    def estado(self):
        if self.usado_at:
            return "usado"
        if self.revocado:
            return "revocado"
        if self.vencido:
            return "vencido"
        return "activo"

    @property
    def utilizable(self):
        return self.estado == "activo"


SOLICITUD_ESTADO_CHOICES = [
    ("pendiente", "Pendiente"),
    ("cotizada", "Cotizada"),
    # El aprobador o financiera rechazaron algo y la solicitud volvió a manos
    # del comercial — es la caja "SEGUIMIENTO CLIENTE" del flujo.
    ("en_seguimiento", "En seguimiento"),
    ("cerrada", "Cerrada"),
]


class SolicitudCotizacion(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="solicitudes")
    estado = models.CharField(max_length=20, choices=SOLICITUD_ESTADO_CHOICES, default="pendiente")
    # Obra o proyecto del cliente al que va el material.
    obra = models.CharField(max_length=200, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="solicitudes_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "solicitudes_cotizacion"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero

    @property
    def cotizacion_vigente(self):
        """La cotización que sigue en juego, ignorando las rechazadas.

        Una solicitud puede acumular varias cotizaciones: cada rechazo del
        aprobador manda la solicitud a seguimiento y el comercial arma una
        nueva. Solo una puede estar viva a la vez.
        """
        return next((c for c in self.cotizaciones.all() if c.estado != "rechazada"), None)


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
    # FK y no 1:1: un rechazo no mata la solicitud, el comercial arma otra
    # cotización sobre la misma (la flecha "No → SEGUIMIENTO CLIENTE → FORMATO
    # COTIZACIÓN" del flujo). Solo una puede estar sin rechazar a la vez.
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name="cotizaciones")
    # Planta por defecto de la cotización. La planta de verdad vive en cada
    # CotizacionItem: una cotización puede repartirse entre varias plantas y
    # entonces esto es solo la que se preseleccionó al armarla.
    planta = models.ForeignKey(
        Planta, on_delete=models.PROTECT, related_name="cotizaciones", null=True, blank=True,
    )
    estado = models.CharField(max_length=25, choices=COTIZACION_ESTADO_CHOICES, default="pendiente_aprobacion")
    # Tarifa con la que se armó, copiada del cliente al crearla.
    tipo_precio = models.CharField(max_length=20, choices=TIPO_PRECIO_CHOICES, default="especial")
    # Copia del IVA vigente: si mañana cambia, esta cotización sigue cuadrando.
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=IVA_PORCENTAJE)
    aprobado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="cotizaciones_aprobadas")
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, null=True)
    # Notas extra que escribe el comercial, una por línea; salen como viñetas
    # adicionales al final de las notas aclaratorias.
    notas = models.TextField(blank=True, null=True)
    # Claves de las notas aclaratorias elegidas (ver services/notas_cotizacion.py).
    # None = todas: así quedan las cotizaciones anteriores a poder elegirlas.
    notas_aclaratorias = models.JSONField(null=True, blank=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="cotizaciones_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cotizaciones"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero

    # ── Totales ──────────────────────────────────────────────────────────
    # subtotal_materiales  suma de las líneas
    # + ajustes            fletes (+), descuentos (−), en monto o porcentaje
    # = subtotal           base antes de IVA
    # iva                  solo sobre lo gravado (un ajuste puede no gravar IVA)
    # total                subtotal + iva — lo que paga el cliente

    @property
    def subtotal_materiales(self) -> Decimal:
        return sum((i.subtotal for i in self.items.all()), Decimal("0"))

    @property
    def ajustes_calculados(self) -> list:
        """[(ajuste, valor con signo)] — los descuentos salen negativos."""
        base = self.subtotal_materiales
        return [(a, a.valor_sobre(base)) for a in self.ajustes.all()]

    @property
    def subtotal(self) -> Decimal:
        """Base antes de IVA: materiales más cargos, menos descuentos."""
        return self.subtotal_materiales + sum((v for _, v in self.ajustes_calculados), Decimal("0"))

    @property
    def iva(self) -> Decimal:
        gravado = self.subtotal_materiales + sum(
            (v for a, v in self.ajustes_calculados if a.aplica_iva), Decimal("0"))
        return (gravado * self.iva_porcentaje / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def total(self) -> Decimal:
        """Lo que paga el cliente: subtotal + IVA."""
        return self.subtotal + self.iva

    @property
    def plantas(self):
        """Las plantas que despachan esta cotización, sin repetir y en orden."""
        vistas, out = set(), []
        for i in self.items.all():
            p = i.planta or self.planta
            if p and p.id not in vistas:
                vistas.add(p.id)
                out.append(p)
        return out

    # ── Pagos parciales ──────────────────────────────────────────────────
    # Una cotización se puede pagar por partes y respaldar con una orden de
    # compra del cliente. Nada de esto se guarda: sale de sumar los pagos.

    def _suma_pagos(self, *estados):
        return sum((p.monto for p in self.pagos.all() if p.estado in estados), Decimal("0"))

    @property
    def total_pagado(self) -> Decimal:
        """Plata recibida y verificada por financiera."""
        return self._suma_pagos("aprobado")

    @property
    def total_en_revision(self) -> Decimal:
        """Comprobantes subidos que financiera aún no revisa."""
        return self._suma_pagos("pendiente")

    @property
    def total_por_confirmar(self) -> Decimal:
        """Respaldado por órdenes de compra del cliente, pendiente de pago real."""
        return self._suma_pagos("por_confirmar")

    @property
    def saldo_por_cobrar(self) -> Decimal:
        return max(self.total - self.total_pagado, Decimal("0"))

    @property
    def saldo_sin_registrar(self) -> Decimal:
        """Lo que falta por cubrir con algún pago u orden de compra."""
        cubierto = self._suma_pagos("aprobado", "pendiente", "por_confirmar")
        return max(self.total - cubierto, Decimal("0"))

    @property
    def habilita_ordenes(self) -> bool:
        """Se puede emitir orden de suministro con algo pagado o con orden de compra."""
        return self.estado == "aprobada" and (self.total_pagado + self.total_por_confirmar) > 0

    def cantidad_ordenada(self, item) -> Decimal:
        return sum(
            (oi.cantidad for o in self.ordenes_suministro.all() for oi in o.items.all()
             if oi.cotizacion_item_id == item.id),
            Decimal("0"),
        )

    @property
    def fraccion_ordenada(self) -> Decimal:
        """Qué parte del valor de materiales ya salió en órdenes (0 a 1)."""
        base = self.subtotal_materiales
        if not base:
            return Decimal("0")
        ordenado = sum(
            (oi.cantidad * oi.cotizacion_item.precio_unitario
             for o in self.ordenes_suministro.all() for oi in o.items.all()),
            Decimal("0"),
        )
        return ordenado / base


ORIGEN_PRECIO_CHOICES = TIPO_PRECIO_CHOICES + [("manual", "Precio escrito a mano")]

AJUSTE_TIPO_CHOICES = [("cargo", "Cargo"), ("descuento", "Descuento")]
AJUSTE_MODO_CHOICES = [("monto", "Monto fijo"), ("porcentaje", "Porcentaje")]


class CotizacionItem(models.Model):
    """Una línea de cotización: material, cantidad y **de qué planta sale**.

    Un mismo material puede aparecer en varias líneas con plantas distintas
    para repartir la cantidad entre ellas (p. ej. 60 m³ de una planta y 40 de
    otra). El ``precio_unitario`` es la foto del `MaterialPlanta` de **esa**
    planta al momento de armar la cotización, así que repartir entre plantas
    con precios distintos da el precio correcto en cada línea.
    """
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="items")
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    # null solo por las líneas viejas, anteriores al reparto por planta;
    # léelas siempre con `item.planta or item.cotizacion.planta`.
    planta = models.ForeignKey(
        Planta, on_delete=models.PROTECT, related_name="cotizacion_items", null=True, blank=True,
    )
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    # De dónde salió el precio: la tarifa especial o detal de la planta, o uno
    # escrito a mano. El aprobador lo ve, para saber qué está aprobando.
    origen_precio = models.CharField(max_length=20, choices=ORIGEN_PRECIO_CHOICES, default="especial")

    class Meta:
        db_table = "cotizacion_items"

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.precio_unitario

    @property
    def planta_efectiva(self):
        return self.planta or self.cotizacion.planta


class CotizacionAjuste(models.Model):
    """Cargo o descuento sobre la cotización: flete, descuento comercial, etc.

    El porcentaje se calcula sobre el subtotal de materiales (no sobre otros
    ajustes), para que el orden en que se agregan no cambie el resultado.
    """
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="ajustes")
    tipo = models.CharField(max_length=20, choices=AJUSTE_TIPO_CHOICES)
    modo = models.CharField(max_length=20, choices=AJUSTE_MODO_CHOICES)
    descripcion = models.CharField(max_length=200)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    # Un flete, por ejemplo, puede facturarse sin IVA. Se decide por ajuste.
    aplica_iva = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "cotizacion_ajustes"
        ordering = ["orden", "id"]

    def valor_sobre(self, base: Decimal) -> Decimal:
        """Valor con signo: positivo si suma (cargo), negativo si resta (descuento)."""
        bruto = (base * self.valor / Decimal("100")) if self.modo == "porcentaje" else self.valor
        bruto = bruto.quantize(Decimal("0.01"))
        return -bruto if self.tipo == "descuento" else bruto


PAGO_ESTADO_CHOICES = [
    ("pendiente", "Pendiente de revisión"),
    ("por_confirmar", "Orden de compra por confirmar"),
    ("aprobado", "Aprobado"),
    ("rechazado", "Rechazado"),
]

PAGO_TIPO_CHOICES = [
    ("transferencia", "Transferencia / consignación"),
    # El cliente entrega su orden de compra: se compromete a pagar. Respalda el
    # despacho, pero queda "por confirmar" hasta que entre la plata.
    ("orden_compra", "Orden de compra del cliente"),
]


class Pago(models.Model):
    # FK y no 1:1, por lo mismo que Cotizacion.solicitud: un comprobante
    # rechazado por financiera no deja la cotización inservible.
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="pagos")
    tipo = models.CharField(max_length=20, choices=PAGO_TIPO_CHOICES, default="transferencia")
    # Puede ser un abono: varios pagos suman hasta el total de la cotización.
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    fecha_pago = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True, null=True)
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


class SolicitudToken(models.Model):
    """Link permanente para que un cliente pida cotizaciones por su cuenta.

    A diferencia de ``ClienteToken`` (vinculación, un solo uso y 3 días), este
    es del cliente ya vinculado y sirve **muchas veces**: es su "link de
    pedidos", el que se guarda y usa cada vez que necesita material. Cada envío
    crea una ``SolicitudCotizacion`` pendiente, que es donde arranca el flujo.
    """
    token = models.CharField(max_length=64, unique=True, db_index=True, default=_generar_token)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="tokens_solicitud")
    activo = models.BooleanField(default=True)
    # Sin fecha = no vence. Es un link que el cliente conserva.
    expira_at = models.DateTimeField(null=True, blank=True)
    usos = models.PositiveIntegerField(default=0)
    ultimo_uso_at = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="tokens_solicitud_creados")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "solicitud_tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Link de pedidos de {self.cliente.nombre}"

    @property
    def estado(self):
        if not self.activo:
            return "revocado"
        if self.expira_at and timezone.now() >= self.expira_at:
            return "vencido"
        return "activo"

    @property
    def utilizable(self):
        return self.estado == "activo"


SEGUIMIENTO_TIPO_CHOICES = [
    ("nota", "Nota"),
    ("cotizacion_rechazada", "Cotización rechazada"),
    ("cotizacion_aprobada", "Cotización aprobada"),
    ("pago_rechazado", "Pago rechazado"),
    ("pago_aprobado", "Pago aprobado"),
    ("cotizacion_nueva", "Nueva cotización"),
]


class Seguimiento(models.Model):
    """Bitácora de una solicitud — la caja "SEGUIMIENTO CLIENTE" del flujo.

    Las entradas de rechazo y aprobación las escribe el sistema; las de tipo
    "nota" las escribe el comercial para dejar registro de lo que habló con el
    cliente mientras la solicitud da vueltas.
    """
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.CASCADE, related_name="seguimientos")
    tipo = models.CharField(max_length=30, choices=SEGUIMIENTO_TIPO_CHOICES, default="nota")
    texto = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="seguimientos")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "seguimientos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.solicitud.numero} · {self.get_tipo_display()}"


class OrdenSuministro(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    # FK y no 1:1: si la cotización se reparte entre varias plantas, se emite
    # una orden por planta, porque cada planta despacha lo suyo por su cuenta.
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name="ordenes_suministro")
    planta = models.ForeignKey(Planta, on_delete=models.PROTECT, related_name="ordenes_suministro")
    # Obra de esta entrega; si viene vacía se usa la de la solicitud.
    obra = models.CharField(max_length=250, blank=True, null=True)
    notificada_planta = models.BooleanField(default=False)
    fecha_notificacion = models.DateTimeField(null=True, blank=True)
    notificada_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    # "whatsapp", "email" — por dónde se avisó.
    canales_notificacion = models.JSONField(default=list, blank=True)
    # Para el link del PDF que va en el WhatsApp/correo: la planta lo abre sin usuario.
    token_publico = models.CharField(max_length=64, unique=True, null=True, blank=True, default=_generar_token)
    # Se llenan después de emitida la orden, cuando el cliente confirma el
    # retiro: la planta solo deja entrar los vehículos cuyas placas figuran aquí.
    fecha_suministro = models.DateField(null=True, blank=True)
    placas_empresa = models.CharField(max_length=300, blank=True, null=True)
    placas_cliente = models.CharField(max_length=300, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="ordenes_creadas")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ordenes_suministro"
        ordering = ["-created_at"]

    def __str__(self):
        return self.numero

    @property
    def obra_efectiva(self):
        return self.obra or self.cotizacion.solicitud.obra

    def cantidad_despachada(self, material_id) -> Decimal:
        return sum(
            (di.cantidad for d in self.despachos.all() for di in d.items.all() if di.material_id == material_id),
            Decimal("0"),
        )

    @property
    def completamente_despachada(self) -> bool:
        items = list(self.items.all())
        return bool(items) and all(self.cantidad_despachada(i.cotizacion_item.material_id) >= i.cantidad for i in items)


class OrdenSuministroItem(models.Model):
    """Cuánto de una línea de la cotización se entrega con esta orden.

    Las órdenes pueden ser parciales: 100 m³ cotizados pueden salir en dos
    órdenes de 60 y 40, cada una con su fecha y sus placas.
    """
    orden = models.ForeignKey(OrdenSuministro, on_delete=models.CASCADE, related_name="items")
    cotizacion_item = models.ForeignKey("CotizacionItem", on_delete=models.PROTECT, related_name="ordenes_items")
    cantidad = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "orden_suministro_items"


class Despacho(models.Model):
    """Formato de Control de Despacho y Recibo de Material (Remisión)."""
    numero = models.CharField(max_length=50, unique=True)
    orden_suministro = models.ForeignKey(OrdenSuministro, on_delete=models.CASCADE, related_name="despachos")
    # Número del tiquete que emite la planta (p. ej. 758812). No es el REM-xxxx
    # interno: es el que figura en el control de despachos que se le envía al cliente.
    consecutivo = models.CharField(max_length=50, blank=True, null=True)
    fecha = models.DateField()
    recibido_por = models.CharField(max_length=200, blank=True, null=True)
    cliente_retira = models.BooleanField(default=True)
    placa_vehiculo = models.CharField(max_length=20, blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=500, blank=True, null=True)
    # Foto o PDF del tiquete/remisión firmado que sube la planta.
    soporte_path = models.CharField(max_length=500, blank=True, null=True)
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
