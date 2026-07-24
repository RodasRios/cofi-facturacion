export type Rol = "comercial" | "aprobador" | "financiera" | "planta";

export interface User {
  id: number;
  username: string;
  email: string | null;
  nombre: string | null;
  rol: Rol;
  is_admin: boolean;
  is_active: boolean;
  firma_path: string | null;
  created_at: string;
}

export interface Planta {
  id: number;
  nombre: string;
  ubicacion: string | null;
  activa: boolean;
  created_at: string;
}

export type MaterialTipo = "triturado" | "agregado" | "otro";

export interface MaterialPlantaPrecio {
  id: number;
  material: number;
  planta: number;
  planta_nombre: string;
  precio_unitario: string;
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
  numero_vinculacion: string | null;
  vinculado: boolean;
  pdf_path: string | null;
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

export type SolicitudEstado = "pendiente" | "cotizada" | "cerrada";

export interface SolicitudCotizacion {
  id: number;
  numero: string;
  cliente: number;
  cliente_nombre: string;
  estado: SolicitudEstado;
  notas: string | null;
  items: SolicitudCotizacionItem[];
  creado_por: number | null;
  creado_por_username: string | null;
  tiene_cotizacion: boolean;
  created_at: string;
}

export interface CotizacionItem {
  id: number;
  material: number;
  material_nombre: string;
  unidad_medida: string;
  cantidad: string;
  precio_unitario: string;
  subtotal: string;
}

export type CotizacionEstado = "pendiente_aprobacion" | "aprobada" | "rechazada";

export interface Cotizacion {
  id: number;
  numero: string;
  solicitud: number;
  solicitud_numero: string;
  cliente_nombre: string;
  planta: number;
  planta_nombre: string;
  estado: CotizacionEstado;
  aprobado_por: number | null;
  aprobado_por_username: string | null;
  fecha_aprobacion: string | null;
  motivo_rechazo: string | null;
  notas: string | null;
  pdf_path: string | null;
  items: CotizacionItem[];
  total: string;
  creado_por: number | null;
  creado_por_username: string | null;
  tiene_orden_suministro: boolean;
  created_at: string;
}

export type PagoEstado = "pendiente" | "aprobado" | "rechazado";

export interface Pago {
  id: number;
  cotizacion: number;
  cotizacion_numero: string;
  monto: string;
  comprobante_path: string | null;
  estado: PagoEstado;
  aprobado_por: number | null;
  aprobado_por_username: string | null;
  fecha_aprobacion: string | null;
  motivo_rechazo: string | null;
  creado_por: number | null;
  created_at: string;
}

export interface OrdenSuministro {
  id: number;
  numero: string;
  cotizacion: number;
  cotizacion_numero: string;
  cliente_nombre: string;
  planta: number;
  planta_nombre: string;
  notificada_planta: boolean;
  fecha_notificacion: string | null;
  notas: string | null;
  pdf_path: string | null;
  items: CotizacionItem[];
  creado_por: number | null;
  created_at: string;
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
  fecha: string;
  recibido_por: string | null;
  cliente_retira: boolean;
  placa_vehiculo: string | null;
  notas: string | null;
  pdf_path: string | null;
  items: DespachoItem[];
  creado_por: number | null;
  created_at: string;
}
