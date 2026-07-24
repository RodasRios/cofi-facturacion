import client from "./client";
import type { Despacho } from "../types";

export async function getDespachos(ordenSuministroId?: number): Promise<Despacho[]> {
  const res = await client.get("/despachos/", { params: ordenSuministroId ? { orden_suministro: ordenSuministroId } : undefined });
  return res.data;
}

export async function createDespacho(data: {
  orden_suministro: number; fecha: string; recibido_por?: string; cliente_retira?: boolean;
  placa_vehiculo?: string; notas?: string; items: { material: number; cantidad: number }[];
}): Promise<Despacho> {
  const res = await client.post("/despachos/", data);
  return res.data;
}
