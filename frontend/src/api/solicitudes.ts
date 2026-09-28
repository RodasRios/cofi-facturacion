import client from "./client";
import type { SolicitudCotizacion } from "../types";

export async function getSolicitudes(estado?: string): Promise<SolicitudCotizacion[]> {
  const res = await client.get("/solicitudes-cotizacion/", { params: estado ? { estado } : undefined });
  return res.data;
}

export async function createSolicitud(data: {
  cliente: number; obra?: string; notas?: string; items: { material: number; cantidad: number }[];
}): Promise<SolicitudCotizacion> {
  const res = await client.post("/solicitudes-cotizacion/", data);
  return res.data;
}

/** Solo sin cotización en curso. */
export async function actualizarSolicitud(id: number, data: {
  cliente?: number; obra?: string; notas?: string; items?: { material: number; cantidad: number }[];
}): Promise<SolicitudCotizacion> {
  const res = await client.patch(`/solicitudes-cotizacion/${id}/`, data);
  return res.data;
}

export async function eliminarSolicitud(id: number): Promise<void> {
  await client.delete(`/solicitudes-cotizacion/${id}/`);
}
