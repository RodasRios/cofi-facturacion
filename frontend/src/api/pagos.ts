import client from "./client";
import type { FilaCartera, Pago, PagoTipo } from "../types";

export async function getPagos(params?: { estado?: string; cotizacion?: number }): Promise<Pago[]> {
  const res = await client.get("/pagos/", { params });
  return res.data;
}

/** Abono, pago completo u orden de compra. El archivo (comprobante u OC) es opcional. */
export async function createPago(data: {
  cotizacion: number; tipo: PagoTipo; monto: number; referencia?: string;
  fecha_pago?: string; notas?: string; file?: File | null;
}): Promise<Pago> {
  const form = new FormData();
  Object.entries(data).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    form.append(k, v instanceof File ? v : String(v));
  });
  const res = await client.post("/pagos/", form);
  return res.data;
}

export async function uploadComprobante(pagoId: number, file: File): Promise<Pago> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.post(`/pagos/${pagoId}/comprobante/`, form);
  return res.data;
}

/** Aprobar/rechazar un pago, o confirmar/anular una orden de compra (con el monto que llegó). */
export async function aprobarPago(id: number, aprobar: boolean, extra?: { motivo?: string; monto?: number; referencia?: string }): Promise<Pago> {
  const res = await client.post(`/pagos/${id}/aprobar/`, { aprobar, ...extra });
  return res.data;
}

export async function getCartera(): Promise<FilaCartera[]> {
  const res = await client.get("/pagos/cartera/");
  return res.data;
}
