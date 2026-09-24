export type Rol = "comercial" | "aprobador" | "financiera" | "planta";

export type Permiso =
  | "tablero" | "clientes" | "solicitudes" | "cotizaciones" | "aprobar_cotizaciones"
  | "pagos" | "aprobar_pagos" | "ordenes" | "despachos" | "disponibilidad" | "precios";

export interface User {
  id: number;
  username: string;
  email: string | null;
  nombre: string | null;
  rol: Rol;
  /** Salen bajo la firma en cotización, orden y control de despachos. */
  cargo: string | null;
  telefono: string | null;
  cedula: string | null;
  is_admin: boolean;
  /** Dueño del sistema: el único que crea o modifica administradores. */
  is_superadmin: boolean;
  is_active: boolean;
  /** La contraseña la puso otra persona: se pide cambiarla al entrar. */
  debe_cambiar_password: boolean;
  /** Pestañas y acciones permitidas. Un admin las tiene todas. */
  permisos: Permiso[];
  /** Plantas asignadas (órdenes, despachos, disponibilidad). Vacío = todas. */
  plantas: number[];
  firma_path: string | null;
  last_login: string | null;
  created_at: string;
}

export interface Planta {
  id: number;
  nombre: string;
  ubicacion: string | null;
  activa: boolean;
  /** A dónde se avisa al emitirle una orden de suministro. */
  whatsapp: string | null;
  email: string | null;
  nota_disponibilidad: string | null;
  nota_actualizada_at: string | null;
  created_at: string;
}

export type Disponibilidad = "disponible" | "limitada" | "agotada";

export type MaterialTipo = "triturado" | "agregado" | "otro";

export type TipoPrecio = "especial" | "detal";
/** De dónde salió el precio de una línea: una tarifa de la planta o escrito a mano. */
export type OrigenPrecio = TipoPrecio | "manual";

export interface NotaAclaratoria {
  clave: string;
  titulo: string;
  texto: string;
  posicion: "antes" | "despues";
}

export interface CotizacionAjuste {
  id: number;
  tipo: "cargo" | "descuento";
  modo: "monto" | "porcentaje";
  descripcion: string;
  valor: string;
  aplica_iva: boolean;
  /** Con signo y ya resuelto el porcentaje. */
  valor_calculado: string;
}

export interface MaterialPlantaPrecio {
  id: number;
  material: number;
  planta: number;
  planta_nombre: string;
  /** Ambos sin IVA. `precio_detal` en null = esa planta no maneja esa tarifa. */
  precio_especial: string;
  precio_detal: string | null;
  material_nombre: string;
  unidad_medida: string;
  disponibilidad: Disponibilidad;
  cantidad_disponible: string | null;
  disponibilidad_nota: string | null;
  disponibilidad_actualizada_at: string | null;
  disponibilidad_actualizada_por_nombre: string | null;
}

export interface PlantaDisponibilidad extends Planta {
  editable: boolean;
  materiales: MaterialPlantaPrecio[];
}

export interface Material {
  id: number;
  nombre: string;
  tipo: MaterialTipo;
  tipo_display: string;
  unidad_medida: string;
  activo: boolean;
  precios: MaterialPlantaPrecio[];
  created_at: string;
}

export interface Cliente {
  id: number;
  nombre: string;
  nit: string | null;
  telefono: string | null;
  email: string | null;
  direccion: string | null;
  tipo_precio: TipoPrecio;
  numero_vinculacion: string | null;
  vinculado: boolean;
  pdf_path: string | null;
  creado_por: number | null;
  creado_por_username: string | null;
  created_at: string;
}

export type ClienteTokenEstado = "activo" | "usado" | "vencido" | "revocado";

export interface ClienteToken {
  id: number;
  token: string;
  etiqueta: string | null;
  estado: ClienteTokenEstado;
  expira_at: string;
  usado_at: string | null;
  cliente: number | null;
  cliente_nombre: string | null;
  revocado: boolean;
  creado_por: number | null;
  creado_por_username: string | null;
  created_at: string;
}

export type EtapaFlujo =
  | "pendiente_cotizacion"
  | "en_seguimiento"
  | "pendiente_aprobacion"
  | "pendiente_pago"
  | "pendiente_aprobacion_pago"
  | "pendiente_orden"
  | "pendiente_notificacion"
  | "pendiente_despacho"
  | "despachada";

export interface FilaTablero {
  solicitud_id: number;
  numero: string;
  cliente_nombre: string;
  etapa: EtapaFlujo;
  etapa_titulo: string;
  responsable: Rol | null;
  desde: string;
  dias_en_etapa: number;
  cotizacion_numero: string | null;
  total: string | null;
  pagado: string | null;
  por_confirmar: string | null;
  saldo_por_cobrar: string | null;
  cotizaciones_rechazadas: number;
  pagos_rechazados: number;
  created_at: string;
}

export type SeguimientoTipo =
  | "nota"
  | "cotizacion_rechazada"
  | "cotizacion_aprobada"
  | "pago_rechazado"
  | "pago_aprobado"
  | "cotizacion_nueva";

export interface Seguimiento {
  id: number;
  solicitud: number;
  tipo: SeguimientoTipo;
  tipo_display: string;
  texto: string | null;
  usuario: number | null;
  usuario_username: string | null;
  created_at: string;
}

export interface SolicitudToken {
  id: number;
  token: string;
  cliente: number;
  cliente_nombre: string;
  estado: "activo" | "vencido" | "revocado";
  activo: boolean;
  expira_at: string | null;
  usos: number;
  ultimo_uso_at: string | null;
  creado_por: number | null;
  creado_por_username: string | null;
  created_at: string;
}

export interface SolicitudCotizacionItem {
  id: number;
  material: number;
  material_nombre: string;
  unidad_medida: string;
  cantidad: string;
}

export type SolicitudEstado = "pendiente" | "cotizada" | "en_seguimiento" | "cerrada";

export interface SolicitudCotizacion {
  id: number;
  numero: string;
  cliente: number;
  cliente_nombre: string;
  cliente_tipo_precio: TipoPrecio;
  estado: SolicitudEstado;
  obra: string | null;
  notas: string | null;
  items: SolicitudCotizacionItem[];
  creado_por: number | null;
  creado_por_username: string | null;
  tiene_cotizacion: boolean;
  cotizaciones_rechazadas: number;
  created_at: string;
}

export interface CotizacionItem {
  id: number;
  material: number;
  material_nombre: string;
  unidad_medida: string;
  planta: number | null;
  planta_nombre: string | null;
  cantidad: string;
  precio_unitario: string;
  origen_precio: OrigenPrecio;
  subtotal: string;
  /** Planta real de la línea (la de la cotización si la línea no tiene propia). */
  planta_efectiva: number | null;
  /** Lo que ya salió en órdenes de suministro. */
  cantidad_ordenada: string;
}

export type CotizacionEstado = "pendiente_aprobacion" | "aprobada" | "rechazada";

export interface Cotizacion {
  id: number;
  numero: string;
  solicitud: number;
  solicitud_numero: string;
  cliente_nombre: string;
  planta: number | null;
  planta_nombre: string | null;
  /** Todas las plantas que despachan esta cotización, no solo la principal. */
  plantas_nombres: string[];
  estado: CotizacionEstado;
  aprobado_por: number | null;
  aprobado_por_username: string | null;
  fecha_aprobacion: string | null;
  motivo_rechazo: string | null;
  notas: string | null;
  pdf_path: string | null;
  items: CotizacionItem[];
  tipo_precio: TipoPrecio;
  iva_porcentaje: string;
  subtotal_materiales: string;
  ajustes: CotizacionAjuste[];
  notas_aclaratorias: string[] | null;
  subtotal: string;
  iva: string;
  total: string;
  creado_por: number | null;
  creado_por_username: string | null;
  tiene_orden_suministro: boolean;
  pagos_rechazados: number;
  total_pagado: string;
  total_en_revision: string;
  total_por_confirmar: string;
  saldo_por_cobrar: string;
  /** Lo que falta cubrir con algún pago u orden de compra. */
  saldo_sin_registrar: string;
  /** Aprobada y con algo pagado u orden de compra: ya se puede emitir orden. */
  habilita_ordenes: boolean;
  porcentaje_ordenado: number;
  created_at: string;
  /** Solo en /ordenes-suministro/por-ordenar/. */
  obra?: string | null;
}

export type PagoEstado = "pendiente" | "por_confirmar" | "aprobado" | "rechazado";
export type PagoTipo = "transferencia" | "orden_compra";

export interface Pago {
  id: number;
  cotizacion: number;
  cotizacion_numero: string;
  cliente_nombre: string;
  tipo: PagoTipo;
  tipo_display: string;
  monto: string;
  referencia: string | null;
  fecha_pago: string | null;
  notas: string | null;
  comprobante_path: string | null;
  estado: PagoEstado;
  estado_display: string;
  aprobado_por: number | null;
  aprobado_por_username: string | null;
  fecha_aprobacion: string | null;
  motivo_rechazo: string | null;
  creado_por: number | null;
  creado_por_username: string | null;
  created_at: string;
}

export interface FilaCartera {
  cotizacion_id: number;
  cotizacion_numero: string;
  cliente_nombre: string;
  total: string;
  pagado: string;
  en_revision: string;
  por_confirmar: string;
  saldo_por_cobrar: string;
  sin_respaldo: string;
  fecha_aprobacion: string | null;
}

export interface OrdenSuministroItem {
  id: number;
  cotizacion_item: number;
  material: number;
  material_nombre: string;
  unidad_medida: string;
  cantidad: string;
  cantidad_despachada: string;
}

export interface OrdenSuministro {
  id: number;
  numero: string;
  cotizacion: number;
  cotizacion_numero: string;
  cliente_nombre: string;
  planta: number;
  planta_nombre: string;
  planta_whatsapp: string | null;
  planta_email: string | null;
  obra: string | null;
  notificada_planta: boolean;
  fecha_notificacion: string | null;
  notificada_por_username: string | null;
  canales_notificacion: ("whatsapp" | "email" | "manual")[];
  fecha_suministro: string | null;
  placas_empresa: string | null;
  placas_cliente: string | null;
  notas: string | null;
  pdf_path: string | null;
  items: OrdenSuministroItem[];
  completamente_despachada: boolean;
  creado_por: number | null;
  creado_por_username: string | null;
  created_at: string;
  /** Solo en detalle, creación y notificación. */
  whatsapp_url?: string;
  link_pdf_publico?: string;
  email_configurado?: boolean;
}

export interface DespachoItem {
  id: number;
  material: number;
  material_nombre: string;
  unidad_medida: string;
  cantidad: string;
}

export interface Despacho {
  id: number;
  numero: string;
  orden_suministro: number;
  orden_suministro_numero: string;
  planta_nombre: string;
  cliente_nombre: string;
  /** Número del tiquete de báscula de la planta (no el REM interno). */
  consecutivo: string | null;
  fecha: string;
  recibido_por: string | null;
  cliente_retira: boolean;
  placa_vehiculo: string | null;
  notas: string | null;
  pdf_path: string | null;
  /** Foto o PDF del tiquete firmado que sube la planta. */
  soporte_path: string | null;
  items: DespachoItem[];
  creado_por: number | null;
  created_at: string;
}

export interface ResumenTablero {
  kpis: {
    ventas_mes: string;
    cotizado_mes: string;
    tasa_aprobacion: number | null;
    pendientes_aprobacion: number;
    pagos_por_revisar: number;
    solicitudes_en_curso: number;
    despachado_mes: string;
    por_cobrar: string;
    por_confirmar: string;
  };
  por_mes: { mes: string; ventas: string; cotizado: string }[];
  cotizaciones_por_estado: Partial<Record<CotizacionEstado, number>>;
  por_planta: { nombre: string; valor: string }[];
  top_clientes: { nombre: string; valor: string }[];
  top_materiales: { nombre: string; cantidad: string; unidad: string }[];
}
