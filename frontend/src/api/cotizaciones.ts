import client from "./client";
import type { Cotizacion, NotaAclaratoria, OrigenPrecio, TipoPrecio } from "../types";

export async function getCotizaciones(estado?: string): Promise<Cotizacion[]> {
  const res = await client.get("/cotizaciones/", { params: estado ? { estado } : undefined });
  return res.data;
}

export interface NuevaLinea {
  material: number;
  planta: number;
  cantidad: number;
  /** "especial"/"detal": el servidor pone el precio de la lista. "manual": manda precio_unitario. */
  origen_precio: OrigenPrecio;
  precio_unitario?: number;
}

export interface NuevoAjuste {
  tipo: "cargo" | "descuento";
  modo: "monto" | "porcentaje";
  descripcion: string;
  valor: number;
  aplica_iva: boolean;
}

export async function createCotizacion(data: {
  solicitud: number;
  /** Planta por defecto (la de la primera línea). */
  planta: number;
  tipo_precio: TipoPrecio;
  items: NuevaLinea[];
  ajustes: NuevoAjuste[];
  /** Claves elegidas del catálogo de notas aclaratorias. */
  notas_aclaratorias: string[];
  /** Notas extra, una por línea. */
  notas?: string;
}): Promise<Cotizacion> {
  const res = await client.post("/cotizaciones/", data);
  return res.data;
}

export async function getNotasAclaratorias(): Promise<NotaAclaratoria[]> {
  const res = await client.get("/cotizaciones/notas-aclaratorias/");
  return res.data;
}

export async function aprobarCotizacion(id: number, aprobar: boolean, motivo?: string): Promise<Cotizacion> {
  const res = await client.post(`/cotizaciones/${id}/aprobar/`, { aprobar, motivo });
  return res.data;
}
