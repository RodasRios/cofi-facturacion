import client from "./client";
import type { Planta } from "../types";

export async function getPlantas(): Promise<Planta[]> {
  const res = await client.get("/plantas/");
  return res.data;
}

export async function createPlanta(data: { nombre: string; ubicacion?: string }): Promise<Planta> {
  const res = await client.post("/plantas/", data);
  return res.data;
}
