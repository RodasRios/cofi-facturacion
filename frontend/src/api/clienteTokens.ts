import axios from "axios";
import client from "./client";
import type { Cliente, ClienteToken } from "../types";

export async function getClienteTokens(): Promise<ClienteToken[]> {
  const res = await client.get("/cliente-tokens/");
  return res.data;
}

export async function createClienteToken(etiqueta?: string): Promise<ClienteToken> {
  const res = await client.post("/cliente-tokens/", { etiqueta: etiqueta || null });
  return res.data;
}

export async function revocarClienteToken(id: number): Promise<ClienteToken> {
  const res = await client.delete(`/cliente-tokens/${id}/`);
  return res.data;
}

/** El link que se le copia y se le manda al cliente. */
export function urlVinculacion(token: string): string {
  return `${window.location.origin}/vincular/${token}`;
}

// El formulario público usa un axios propio: el cliente `client` manda el
// Authorization guardado y, ante un 401, redirige a /login — nada de eso tiene
// sentido para alguien que entra por un link sin tener usuario.
const publico = axios.create({ baseURL: "/api/v1" });

export interface VinculacionInfo {
  estado: string;
  expira_at: string;
  etiqueta: string | null;
}

export async function getVinculacionInfo(token: string): Promise<VinculacionInfo> {
  const res = await publico.get(`/publico/vinculacion/${token}/`);
  return res.data;
}

export async function enviarVinculacion(
  token: string,
  data: { nombre: string; nit?: string; telefono?: string; email?: string; direccion?: string },
): Promise<{ detail: string; numero_vinculacion: string; cliente: Cliente }> {
  const res = await publico.post(`/publico/vinculacion/${token}/`, data);
  return res.data;
}
