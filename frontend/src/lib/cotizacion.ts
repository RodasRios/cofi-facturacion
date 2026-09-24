import type { Disponibilidad, Material, OrigenPrecio, Planta, SolicitudCotizacionItem, TipoPrecio } from "../types";

/** IVA vigente. El servidor tiene la última palabra; esto es para la vista previa. */
export const IVA_PORCENTAJE = 19;

/** Una línea del formulario: de qué planta sale, cuánto y a qué precio. */
export interface Linea {
  planta: string;
  cantidad: string;
  origen: OrigenPrecio;
  /** Solo cuando origen es "manual". */
  precioManual: string;
}

/** materialId → líneas en que se reparte ese material */
export type Reparto = Record<number, Linea[]>;

export interface Ajuste {
  tipo: "cargo" | "descuento";
  modo: "monto" | "porcentaje";
  descripcion: string;
  valor: string;
  aplicaIva: boolean;
}

export interface OpcionPlanta {
  planta: Planta;
  especial: number;
  /** null si esa planta no maneja tarifa de detal. */
  detal: number | null;
  /** Lo que reporta la planta en su pestaña de Disponibilidad. */
  disponibilidad: Disponibilidad;
  disponibilidadNota: string | null;
}

/**
 * Plantas activas que tienen precio para el material, de la más barata a la
 * más cara según la tarifa (las que reportan el material agotado, al final). Una planta sin precio no se ofrece: antes se podía
 * elegir y la línea salía en $0.
 */
export function plantasConPrecio(material: Material | undefined, plantas: Planta[], tarifa: TipoPrecio): OpcionPlanta[] {
  if (!material) return [];
  const activas = new Map(plantas.map(p => [p.id, p]));
  return material.precios
    .filter(pr => activas.has(pr.planta))
    .map(pr => ({
      planta: activas.get(pr.planta)!,
      especial: Number(pr.precio_especial),
      detal: pr.precio_detal == null ? null : Number(pr.precio_detal),
      disponibilidad: pr.disponibilidad ?? "disponible",
      disponibilidadNota: pr.disponibilidad_nota ?? null,
    }))
    // Lo agotado al final: se puede elegir, pero no se propone primero.
    .sort((a, b) => Number(a.disponibilidad === "agotada") - Number(b.disponibilidad === "agotada")
      || precioDeTarifa(a, tarifa) - precioDeTarifa(b, tarifa));
}

/** Precio de la tarifa; sin detal en esa planta, cae a la especial (igual que el servidor). */
export function precioDeTarifa(op: OpcionPlanta, tarifa: TipoPrecio): number {
  return tarifa === "detal" && op.detal != null ? op.detal : op.especial;
}

/** Precio efectivo de una línea, o null si todavía no se puede calcular. */
export function precioLinea(linea: Linea, opciones: OpcionPlanta[]): number | null {
  if (linea.origen === "manual") {
    const v = Number(linea.precioManual);
    return v > 0 ? v : null;
  }
  const op = opciones.find(o => String(o.planta.id) === linea.planta);
  return op ? precioDeTarifa(op, linea.origen) : null;
}

/** Arranca con una línea por material: toda la cantidad en la planta más barata. */
export function repartoInicial(
  items: SolicitudCotizacionItem[], materiales: Material[], plantas: Planta[], tarifa: TipoPrecio,
): Reparto {
  return Object.fromEntries(items.map(i => {
    const opciones = plantasConPrecio(materiales.find(m => m.id === i.material), plantas, tarifa);
    return [i.material, [{
      planta: opciones[0] ? String(opciones[0].planta.id) : "",
      cantidad: String(Number(i.cantidad)),
      origen: tarifa,
      precioManual: "",
    }]];
  }));
}

export function sumaCantidades(lineas: Linea[]) {
  return lineas.reduce((t, l) => t + (Number(l.cantidad) || 0), 0);
}

export function valorAjuste(a: Ajuste, base: number): number {
  const v = Number(a.valor) || 0;
  const bruto = a.modo === "porcentaje" ? base * v / 100 : v;
  return a.tipo === "descuento" ? -bruto : bruto;
}

/** Mismo cálculo que Cotizacion.subtotal / iva / total en el servidor. */
export function calcularTotales(materiales: number, ajustes: Ajuste[]) {
  const valores = ajustes.map(a => valorAjuste(a, materiales));
  const sumaAjustes = valores.reduce((t, v) => t + v, 0);
  const gravado = materiales + ajustes.reduce((t, a, i) => t + (a.aplicaIva ? valores[i] : 0), 0);
  const subtotal = materiales + sumaAjustes;
  const iva = Math.round(gravado * IVA_PORCENTAJE) / 100;
  return { valores, subtotal, iva, total: subtotal + iva };
}

export function pesos(v: number) {
  return new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(v);
}
