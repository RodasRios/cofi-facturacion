import client from "./client";
import type { Cotizacion } from "../types";

export async function getCotizaciones(estado?: string): Promise<Cotizacion[]> {
  const res = await client.get("/cotizaciones/", { params: estado ? { estado } : undefined });
  return res.data;
}

export async function createCotizacion(data: {
  solicitud: number; planta: number; notas?: string; items: { material: number; cantidad: number }[];
}): Promise<Cotizacion> {
  const res = await client.post("/cotizaciones/", data);
  return res.data;
}

export async function aprobarCotizacion(id: number, aprobar: boolean, motivo?: string): Promise<Cotizacion> {
  const res = await client.post(`/cotizaciones/${id}/aprobar/`, { aprobar, motivo });
  return res.data;
}
