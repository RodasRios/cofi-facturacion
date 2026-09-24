import { isAxiosError } from "axios";

/** El mensaje que manda el servidor ("detail" o el primer error de campo), o el de respaldo. */
export function mensajeError(e: unknown, respaldo: string): string {
  if (!isAxiosError(e)) return respaldo;
  const data = e.response?.data;
  if (!data || typeof data !== "object") return respaldo;
  if (typeof data.detail === "string") return data.detail;
  for (const v of Object.values(data)) {
    if (Array.isArray(v) && typeof v[0] === "string") return v[0];
    if (typeof v === "string") return v;
  }
  return respaldo;
}
