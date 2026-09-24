import axios from "axios";
import client from "./client";
import type { SolicitudToken } from "../types";

export async function getSolicitudTokens(clienteId?: number): Promise<SolicitudToken[]> {
  const res = await client.get("/solicitud-tokens/", {
    params: clienteId ? { cliente: clienteId } : undefined,
  });
  return res.data;
}

/** Devuelve el link vivo del cliente si ya existe, o crea uno nuevo. */
export async function crearSolicitudToken(cliente: number): Promise<SolicitudToken> {
  const res = await client.post("/solicitud-tokens/", { cliente });
  return res.data;
}

export async function revocarSolicitudToken(id: number): Promise<SolicitudToken> {
  const res = await client.delete(`/solicitud-tokens/${id}/`);
  return res.data;
}

export function urlPedidos(token: string): string {
  return `${window.location.origin}/pedir/${token}`;
}

// Instancia propia para lo público, igual que en clienteTokens: el cliente
// compartido manda el token guardado y redirige a /login ante un 401.
const publico = axios.create({ baseURL: "/api/v1" });

export interface MaterialPublico {
  id: number;
  nombre: string;
  tipo: string;
  unidad_medida: string;
}

export interface PedidoInfo {
  cliente_nombre: string;
  materiales: MaterialPublico[];
}

export async function getPedidoInfo(token: string): Promise<PedidoInfo> {
  const res = await publico.get(`/publico/solicitud/${token}/`);
  return res.data;
}

export async function enviarPedido(
  token: string,
  data: { items: { material: number; cantidad: number }[]; obra?: string; notas?: string },
): Promise<{ detail: string; numero: string }> {
  const res = await publico.post(`/publico/solicitud/${token}/`, data);
  return res.data;
}
