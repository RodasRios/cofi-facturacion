import client from "./client";
import type { Cliente } from "../types";

export async function getClientes(q?: string): Promise<Cliente[]> {
  const res = await client.get("/clientes/", { params: q ? { q } : undefined });
  return res.data;
}

export async function createCliente(data: {
  nombre: string; nit?: string; telefono?: string; email?: string; direccion?: string;
}): Promise<Cliente> {
  const res = await client.post("/clientes/", data);
  return res.data;
}

export async function marcarVinculado(clienteId: number, vinculado: boolean): Promise<Cliente> {
  const res = await client.patch(`/clientes/${clienteId}/`, { vinculado });
  return res.data;
}
