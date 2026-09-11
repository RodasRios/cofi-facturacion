import { Icon } from "./ui/Icon";
import { sumaReparto, type Reparto, type LineaReparto } from "../lib/reparto";
import type { Planta, SolicitudCotizacionItem } from "../types";

interface Props {
  items: SolicitudCotizacionItem[];
  plantas: Planta[];
  reparto: Reparto;
  onChange: (r: Reparto) => void;
}

/**
 * Reparto de cada material de la solicitud entre una o varias plantas.
 *
 * Por defecto cada material sale entero de la planta principal. "Repartir"
 * agrega otra línea para partir la cantidad entre plantas — útil cuando una
 * sola planta no tiene todo el material, o cuando conviene mezclar precios.
 */
export function RepartoPlantas({ items, plantas, reparto, onChange }: Props) {
  const editar = (materialId: number, idx: number, campo: keyof LineaReparto, valor: string) => {
    const lineas = [...(reparto[materialId] ?? [])];
    lineas[idx] = { ...lineas[idx], [campo]: valor };
    onChange({ ...reparto, [materialId]: lineas });
  };

  const agregar = (materialId: number, pedido: number) => {
    const lineas = [...(reparto[materialId] ?? [])];
    const restante = Math.max(pedido - sumaReparto(lineas), 0);
    // La planta se deja vacía a propósito: obliga a elegir una distinta.
    onChange({ ...reparto, [materialId]: [...lineas, { planta: "", cantidad: String(restante) }] });
  };

  const quitar = (materialId: number, idx: number) => {
    const lineas = (reparto[materialId] ?? []).filter((_, i) => i !== idx);
    onChange({ ...reparto, [materialId]: lineas });
  };

  return (
    <div className="reparto">
      {items.map(item => {
        const lineas = reparto[item.material] ?? [];
        const pedido = Number(item.cantidad);
        const suma = sumaReparto(lineas);
        const descuadre = Math.abs(suma - pedido) >= 0.01;

        return (
          <div key={item.material} className="reparto-material">
            <div className="reparto-encabezado">
              <strong>{item.material_nombre}</strong>
              <span className={descuadre ? "reparto-descuadre" : "reparto-ok"}>
                {suma.toLocaleString("es-CO")} de {pedido.toLocaleString("es-CO")} {item.unidad_medida}
                {descuadre && (suma > pedido ? " — sobra" : " — falta")}
              </span>
            </div>

            {lineas.map((linea, idx) => {
              const pct = pedido > 0 ? Math.round((Number(linea.cantidad) || 0) / pedido * 100) : 0;
              return (
                <div key={idx} className="reparto-linea">
                  <select
                    className="input-base"
                    value={linea.planta}
                    onChange={e => editar(item.material, idx, "planta", e.target.value)}
                  >
                    <option value="">Selecciona planta</option>
                    {plantas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                  <input
                    className="input-base reparto-cantidad"
                    type="number"
                    min="0"
                    step="0.01"
                    value={linea.cantidad}
                    onChange={e => editar(item.material, idx, "cantidad", e.target.value)}
                  />
                  <span className="reparto-pct">{pct}%</span>
                  {lineas.length > 1 && (
                    <button type="button" className="btn-ghost" title="Quitar esta planta"
                      onClick={() => quitar(item.material, idx)}>
                      <Icon name="close" size={15} />
                    </button>
                  )}
                </div>
              );
            })}

            <button type="button" className="btn-ghost reparto-agregar"
              onClick={() => agregar(item.material, pedido)}>
              <Icon name="add" size={14} />Repartir entre otra planta
            </button>
          </div>
        );
      })}

      <style>{`
        .reparto { display: flex; flex-direction: column; gap: 12px; margin-bottom: 12px; }
        .reparto-material { border: 1px solid var(--border); padding: 10px 12px; }
        .reparto-encabezado {
          display: flex; justify-content: space-between; align-items: baseline;
          gap: 10px; flex-wrap: wrap; font-size: 12.5px; margin-bottom: 8px;
        }
        .reparto-ok { font-size: 11.5px; color: var(--text-muted); }
        .reparto-descuadre { font-size: 11.5px; color: #ef4444; font-weight: 600; }
        .reparto-linea { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
        .reparto-linea .input-base { flex: 1; }
        .reparto-cantidad { max-width: 120px; }
        .reparto-pct { font-size: 11.5px; color: var(--text-muted); min-width: 36px; text-align: right; }
        .reparto-agregar { font-size: 11.5px; padding: 3px 6px; }
      `}</style>
    </div>
  );
}
