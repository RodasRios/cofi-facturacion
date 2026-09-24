import client from "./client";
import type { Material, MaterialTipo } from "../types";

export async function getMateriales(): Promise<Material[]> {
  const res = await client.get("/materiales/");
  return res.data;
}

export async function createMaterial(data: { nombre: string; tipo: MaterialTipo; unidad_medida: string }): Promise<Material> {
  const res = await client.post("/materiales/", data);
  return res.data;
}

/** Envía solo las tarifas indicadas, para poder editar una sin borrar la otra. */
export async function setPrecioMaterial(
  materialId: number,
  plantaId: number,
  precios: { precio_especial?: number; precio_detal?: number | null },
): Promise<Material> {
  const res = await client.post(`/materiales/${materialId}/precios/`, { planta: plantaId, ...precios });
  return res.data;
}

/** Quita el material de esa planta: deja de ofrecerse al cotizar allí. */
export async function quitarPrecioMaterial(materialId: number, plantaId: number): Promise<Material> {
  const res = await client.delete(`/materiales/${materialId}/precios/`, { params: { planta: plantaId } });
  return res.data;
}
