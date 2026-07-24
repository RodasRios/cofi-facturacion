import client from "./client";
import type { SolicitudCotizacion } from "../types";

export async function getSolicitudes(estado?: string): Promise<SolicitudCotizacion[]> {
  const res = await client.get("/solicitudes-cotizacion/", { params: estado ? { estado } : undefined });
  return res.data;
}

export async function createSolicitud(data: {
  cliente: number; notas?: string; items: { material: number; cantidad: number }[];
}): Promise<SolicitudCotizacion> {
  const res = await client.post("/solicitudes-cotizacion/", data);
  return res.data;
}
