import client from "./client";
import type { Disponibilidad, MaterialPlantaPrecio, Planta, PlantaDisponibilidad } from "../types";

export async function getDisponibilidad(mias = false): Promise<PlantaDisponibilidad[]> {
  const res = await client.get("/disponibilidad/", { params: mias ? { mias: 1 } : undefined });
  return res.data;
}

export async function actualizarDisponibilidad(mpId: number, data: {
  disponibilidad?: Disponibilidad; cantidad_disponible?: string | null; disponibilidad_nota?: string;
}): Promise<MaterialPlantaPrecio> {
  const res = await client.patch(`/disponibilidad/materiales/${mpId}/`, data);
  return res.data;
}

export async function actualizarNotaPlanta(plantaId: number, nota: string): Promise<Planta> {
  const res = await client.patch(`/disponibilidad/plantas/${plantaId}/`, { nota_disponibilidad: nota });
  return res.data;
}
