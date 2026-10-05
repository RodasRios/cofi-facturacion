import client from "./client";
import type { Despacho } from "../types";

export async function getDespachos(ordenSuministroId?: number): Promise<Despacho[]> {
  const res = await client.get("/despachos/", { params: ordenSuministroId ? { orden_suministro: ordenSuministroId } : undefined });
  return res.data;
}

/** Datos del formato (todo opcional menos la fecha). */
export interface DatosFormatoDespacho {
  fecha: string; consecutivo: string; hora_despacho: string; temperatura_despacho: string;
  despachado_por_nombre: string; despachado_por_cargo: string;
  placa_vehiculo: string; conductor_nombre: string; conductor_cedula: string;
  recibido_por: string; recibido_cargo: string; notas: string;
}

export async function actualizarDespacho(id: number, data: Partial<DatosFormatoDespacho>): Promise<Despacho> {
  return (await client.patch(`/despachos/${id}/`, data)).data;
}

export async function createDespacho(data: Partial<DatosFormatoDespacho> & {
  orden_suministro: number; fecha: string; cliente_retira?: boolean;
  items: { material: number; cantidad: number }[];
}): Promise<Despacho> {
  const res = await client.post("/despachos/", data);
  return res.data;
}

/** Foto o PDF del tiquete/remisión firmado. */
export async function subirSoporteDespacho(id: number, file: File): Promise<Despacho> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.post(`/despachos/${id}/soporte/`, form);
  return res.data;
}
