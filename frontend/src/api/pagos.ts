import client from "./client";
import type { Pago } from "../types";

export async function getPagos(estado?: string): Promise<Pago[]> {
  const res = await client.get("/pagos/", { params: estado ? { estado } : undefined });
  return res.data;
}

export async function createPago(data: { cotizacion: number; monto?: number }): Promise<Pago> {
  const res = await client.post("/pagos/", data);
  return res.data;
}

export async function uploadComprobante(pagoId: number, file: File): Promise<Pago> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.post(`/pagos/${pagoId}/comprobante/`, form);
  return res.data;
}

export async function aprobarPago(id: number, aprobar: boolean, motivo?: string): Promise<Pago> {
  const res = await client.post(`/pagos/${id}/aprobar/`, { aprobar, motivo });
  return res.data;
}
