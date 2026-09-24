import client from "./client";
import type { Cotizacion, OrdenSuministro } from "../types";

export async function getOrdenesSuministro(params?: { planta?: number; cotizacion?: number }): Promise<OrdenSuministro[]> {
  const res = await client.get("/ordenes-suministro/", { params });
  return res.data;
}

export async function getOrdenSuministro(id: number): Promise<OrdenSuministro> {
  const res = await client.get(`/ordenes-suministro/${id}/`);
  return res.data;
}

/** Cotizaciones aprobadas con pago u orden de compra y material por ordenar. */
export async function getPorOrdenar(): Promise<Cotizacion[]> {
  const res = await client.get("/ordenes-suministro/por-ordenar/");
  return res.data;
}

export interface NuevaOrden {
  cotizacion: number;
  planta: number;
  items: { cotizacion_item: number; cantidad: number }[];
  obra?: string;
  fecha_suministro?: string | null;
  placas_empresa?: string;
  placas_cliente?: string;
  notas?: string;
}

export async function crearOrdenSuministro(data: NuevaOrden): Promise<OrdenSuministro> {
  const res = await client.post("/ordenes-suministro/", data);
  return res.data;
}

export async function anularOrdenSuministro(id: number): Promise<void> {
  await client.delete(`/ordenes-suministro/${id}/`);
}

/** Registra el aviso a planta; con "email" el servidor manda el correo con el PDF. */
export async function notificarOrdenSuministro(id: number, canales: ("whatsapp" | "email" | "manual")[]): Promise<OrdenSuministro> {
  const res = await client.post(`/ordenes-suministro/${id}/notificar/`, { canales });
  return res.data;
}

/** Datos de retiro que se conocen después de emitida la orden. Regenera el PDF. */
export async function actualizarOrdenSuministro(id: number, data: {
  fecha_suministro?: string | null; placas_empresa?: string; placas_cliente?: string; notas?: string; obra?: string;
}): Promise<OrdenSuministro> {
  const res = await client.patch(`/ordenes-suministro/${id}/`, data);
  return res.data;
}
