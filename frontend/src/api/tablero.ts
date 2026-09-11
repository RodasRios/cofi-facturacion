import client from "./client";
import type { FilaTablero, Seguimiento } from "../types";

export async function getTablero(): Promise<FilaTablero[]> {
  const res = await client.get("/tablero/");
  return res.data;
}

export async function getSeguimientos(solicitudId: number): Promise<Seguimiento[]> {
  const res = await client.get(`/solicitudes-cotizacion/${solicitudId}/seguimientos/`);
  return res.data;
}

export async function crearNota(solicitudId: number, texto: string): Promise<Seguimiento> {
  const res = await client.post(`/solicitudes-cotizacion/${solicitudId}/seguimientos/`, { texto });
  return res.data;
}
