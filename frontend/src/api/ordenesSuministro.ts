import client from "./client";
import type { OrdenSuministro } from "../types";

export async function getOrdenesSuministro(plantaId?: number): Promise<OrdenSuministro[]> {
  const res = await client.get("/ordenes-suministro/", { params: plantaId ? { planta: plantaId } : undefined });
  return res.data;
}

export async function notificarOrdenSuministro(id: number): Promise<OrdenSuministro> {
  const res = await client.post(`/ordenes-suministro/${id}/notificar/`);
  return res.data;
}

/** Datos de retiro que se conocen después de emitida la orden. Regenera el PDF. */
export async function actualizarOrdenSuministro(id: number, data: {
  fecha_suministro?: string | null; placas_empresa?: string; placas_cliente?: string; notas?: string;
}): Promise<OrdenSuministro> {
  const res = await client.patch(`/ordenes-suministro/${id}/`, data);
  return res.data;
}
