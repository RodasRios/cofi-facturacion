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
