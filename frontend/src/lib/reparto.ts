import type { SolicitudCotizacionItem } from "../types";

/** Una línea del reparto: de qué planta sale y cuánto. */
export interface LineaReparto {
  planta: string;
  cantidad: string;
}

/** materialId → líneas en que se reparte ese material */
export type Reparto = Record<number, LineaReparto[]>;

/** Arranca con una sola línea por material: todo de la planta por defecto. */
export function repartoInicial(items: SolicitudCotizacionItem[], plantaDefecto: string): Reparto {
  return Object.fromEntries(
    items.map(i => [i.material, [{ planta: plantaDefecto, cantidad: String(Number(i.cantidad)) }]]),
  );
}

export function sumaReparto(lineas: LineaReparto[]) {
  return lineas.reduce((t, l) => t + (Number(l.cantidad) || 0), 0);
}

/** true si todo material está repartido exactamente por la cantidad pedida. */
export function repartoValido(items: SolicitudCotizacionItem[], reparto: Reparto) {
  return items.every(i => {
    const lineas = reparto[i.material] ?? [];
    if (lineas.some(l => !l.planta)) return false;
    // Tolerancia de un centésimo: las cantidades son decimales.
    return Math.abs(sumaReparto(lineas) - Number(i.cantidad)) < 0.01;
  });
}

/** Aplana el reparto al formato que espera la API. */
export function repartoAItems(reparto: Reparto) {
  return Object.entries(reparto).flatMap(([material, lineas]) =>
    lineas
      .filter(l => Number(l.cantidad) > 0 && l.planta)
      .map(l => ({
        material: Number(material),
        planta: Number(l.planta),
        cantidad: Number(l.cantidad),
      })),
  );
}
