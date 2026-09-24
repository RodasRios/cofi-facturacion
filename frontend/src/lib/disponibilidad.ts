import type { Disponibilidad } from "../types";

export const DISPONIBILIDAD: Record<Disponibilidad, { label: string; color: string; icon: string }> = {
  disponible: { label: "Disponible", color: "#16a34a", icon: "check_circle" },
  limitada: { label: "Poca", color: "#d97706", icon: "error" },
  agotada: { label: "Agotado", color: "#dc2626", icon: "cancel" },
};
