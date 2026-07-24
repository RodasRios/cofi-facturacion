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

export async function setPrecioMaterial(materialId: number, plantaId: number, precioUnitario: number): Promise<Material> {
  const res = await client.post(`/materiales/${materialId}/precios/`, { planta: plantaId, precio_unitario: precioUnitario });
  return res.data;
}
