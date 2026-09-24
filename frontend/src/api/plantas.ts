import client from "./client";
import type { Planta } from "../types";

/** Solo las activas, salvo que se pidan todas (panel de administración). */
export async function getPlantas(todas = false): Promise<Planta[]> {
  const res = await client.get("/plantas/", { params: todas ? { todas: 1 } : undefined });
  return res.data;
}

export async function createPlanta(data: { nombre: string; ubicacion?: string }): Promise<Planta> {
  const res = await client.post("/plantas/", data);
  return res.data;
}

export async function setPlantaActiva(id: number, activa: boolean): Promise<Planta> {
  const res = await client.patch(`/plantas/${id}/`, { activa });
  return res.data;
}

export async function actualizarPlanta(id: number, data: Partial<Pick<Planta, "nombre" | "ubicacion" | "whatsapp" | "email">>): Promise<Planta> {
  const res = await client.patch(`/plantas/${id}/`, data);
  return res.data;
}
