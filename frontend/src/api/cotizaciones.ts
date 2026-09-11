import client from "./client";
import type { Cotizacion } from "../types";

export async function getCotizaciones(estado?: string): Promise<Cotizacion[]> {
  const res = await client.get("/cotizaciones/", { params: estado ? { estado } : undefined });
  return res.data;
}

export async function createCotizacion(data: {
  solicitud: number;
  /** Planta por defecto: la que se usa para los ítems que no traen la suya. */
  planta: number;
  notas?: string;
  /** `planta` por ítem permite repartir un material entre varias plantas. */
  items: { material: number; cantidad: number; planta?: number }[];
}): Promise<Cotizacion> {
  const res = await client.post("/cotizaciones/", data);
  return res.data;
}

export async function aprobarCotizacion(id: number, aprobar: boolean, motivo?: string): Promise<Cotizacion> {
  const res = await client.post(`/cotizaciones/${id}/aprobar/`, { aprobar, motivo });
  return res.data;
}
