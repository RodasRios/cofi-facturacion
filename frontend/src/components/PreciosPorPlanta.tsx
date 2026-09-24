import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { setPrecioMaterial, quitarPrecioMaterial } from "../api/materiales";
import type { Material, Planta } from "../types";

const pesos = (v: number) =>
  new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(v);

/**
 * Lista de precios por planta.
 *
 * Una planta a la vez (pestañas) y solo los materiales que esa planta vende:
 * la matriz material × planta × tarifa crecía hacia los lados con cada planta
 * y quedaba casi vacía, porque cada planta vende una fracción del catálogo.
 */
export function PreciosPorPlanta({ plantas, materiales }: { plantas: Planta[]; materiales: Material[] }) {
  const qc = useQueryClient();
  const activas = plantas.filter(p => p.activa);
  const [plantaId, setPlantaId] = useState<number | null>(null);
  const planta = activas.find(p => p.id === plantaId) ?? activas[0];
  const [buscar, setBuscar] = useState("");

  const [nuevoMaterial, setNuevoMaterial] = useState("");
  const [nuevoEspecial, setNuevoEspecial] = useState("");
  const [nuevoDetal, setNuevoDetal] = useState("");

  const conteo = useMemo(() => Object.fromEntries(activas.map(p => [
    p.id, materiales.filter(m => m.precios.some(pr => pr.planta === p.id)).length,
  ])), [activas, materiales]);

  const filas = useMemo(() => {
    if (!planta) return [];
    const q = buscar.trim().toLowerCase();
    return materiales
      .map(m => ({ m, precio: m.precios.find(pr => pr.planta === planta.id) }))
      .filter(f => f.precio && (!q || f.m.nombre.toLowerCase().includes(q)));
  }, [materiales, planta, buscar]);

  const sinPrecio = planta ? materiales.filter(m => !m.precios.some(pr => pr.planta === planta.id)) : [];

  const guardar = useMutation({
    mutationFn: ({ materialId, datos }: {
      materialId: number; datos: { precio_especial?: number; precio_detal?: number | null };
    }) => setPrecioMaterial(materialId, planta!.id, datos),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["materiales"] }); toast.success("Precio guardado"); },
    onError: () => toast.error("No se pudo guardar el precio"),
  });

  const quitar = useMutation({
    mutationFn: (materialId: number) => quitarPrecioMaterial(materialId, planta!.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["materiales"] }); toast.success("Material quitado de la planta"); },
    onError: () => toast.error("No se pudo quitar el material"),
  });

  const agregar = useMutation({
    mutationFn: () => setPrecioMaterial(Number(nuevoMaterial), planta!.id, {
      precio_especial: Number(nuevoEspecial),
      precio_detal: nuevoDetal ? Number(nuevoDetal) : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["materiales"] });
      toast.success("Material agregado a la planta");
      setNuevoMaterial(""); setNuevoEspecial(""); setNuevoDetal("");
    },
    onError: () => toast.error("No se pudo agregar el material"),
  });

  /** Casilla que guarda al salir si el valor cambió. */
  const casilla = (materialId: number, campo: "precio_especial" | "precio_detal", actual: string | null) => (
    <input
      key={`${planta?.id}-${materialId}-${campo}-${actual}`}
      className="input-base pp-precio"
      type="number" min="0" step="1"
      defaultValue={actual == null ? "" : Number(actual)}
      placeholder={campo === "precio_detal" ? "Usa especial" : ""}
      aria-label={campo === "precio_especial" ? "Precio especial" : "Precio detal"}
      onBlur={e => {
        const txt = e.target.value.trim();
        const valor = txt === "" ? null : Number(txt);
        const previo = actual == null ? null : Number(actual);
        if (valor === previo) return;
        if (valor !== null && !(valor > 0)) { e.target.value = actual ?? ""; return; }
        // La tarifa especial es obligatoria: vaciarla no tiene sentido.
        if (campo === "precio_especial" && valor === null) { e.target.value = actual ?? ""; return; }
        guardar.mutate({ materialId, datos: { [campo]: valor } });
      }}
      onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
    />
  );

  if (activas.length === 0) {
    return <p style={{ fontSize: 12.5, color: "var(--text-muted)" }}>No hay plantas activas.</p>;
  }

  return (
    <div className="pp">
      <div className="pp-tabs" role="tablist">
        {activas.map(p => (
          <button key={p.id} role="tab" aria-selected={p.id === planta?.id}
            className={p.id === planta?.id ? "activo" : ""} onClick={() => setPlantaId(p.id)}>
            {p.nombre.replace("Planta ", "")}
            <span className="pp-conteo">{conteo[p.id] ?? 0}</span>
          </button>
        ))}
      </div>

      {planta && (
        <>
          <div className="pp-barra">
            <div className="pp-buscar">
              <Icon name="search" size={15} />
              <input className="input-base" placeholder={`Buscar en ${planta.nombre}…`}
                value={buscar} onChange={e => setBuscar(e.target.value)} />
            </div>
            <span className="pp-nota">Valores sin IVA · se guardan al salir de la casilla</span>
          </div>

          <div className="pp-tabla-wrap">
            <table className="table-sharp pp-tabla">
              <thead>
                <tr>
                  <th>Material</th>
                  <th>Unidad</th>
                  <th className="der">Venta especial</th>
                  <th className="der">Venta detal</th>
                  <th className="der">Con IVA (especial)</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filas.map(({ m, precio }) => (
                  <tr key={m.id}>
                    <td>
                      {m.nombre}
                      <span className="pp-tipo">{m.tipo_display}</span>
                    </td>
                    <td>{m.unidad_medida}</td>
                    <td className="der">{casilla(m.id, "precio_especial", precio!.precio_especial)}</td>
                    <td className="der">{casilla(m.id, "precio_detal", precio!.precio_detal)}</td>
                    <td className="der pp-iva">{pesos(Number(precio!.precio_especial) * 1.19)}</td>
                    <td className="der">
                      <button className="btn-ghost" title={`Quitar ${m.nombre} de ${planta.nombre}`}
                        onClick={() => {
                          if (confirm(`¿Quitar ${m.nombre} de ${planta.nombre}? Dejará de ofrecerse al cotizar en esta planta.`)) {
                            quitar.mutate(m.id);
                          }
                        }}>
                        <Icon name="delete" size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {filas.length === 0 && (
                  <tr><td colSpan={6} className="pp-vacio">
                    {buscar ? "Ningún material coincide con la búsqueda." : "Esta planta todavía no tiene materiales con precio."}
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>

          {sinPrecio.length > 0 && (
            <form className="pp-agregar" onSubmit={e => { e.preventDefault(); agregar.mutate(); }}>
              <span className="pp-agregar-titulo"><Icon name="add_circle" size={15} />Agregar material a {planta.nombre}</span>
              <select className="input-base" value={nuevoMaterial} onChange={e => setNuevoMaterial(e.target.value)} required>
                <option value="">Material…</option>
                {sinPrecio.map(m => <option key={m.id} value={m.id}>{m.nombre} ({m.unidad_medida})</option>)}
              </select>
              <input className="input-base" type="number" min="1" step="1" placeholder="Especial *"
                value={nuevoEspecial} onChange={e => setNuevoEspecial(e.target.value)} required />
              <input className="input-base" type="number" min="1" step="1" placeholder="Detal (opcional)"
                value={nuevoDetal} onChange={e => setNuevoDetal(e.target.value)} />
              <button type="submit" className="btn-primary" disabled={agregar.isPending}>Agregar</button>
            </form>
          )}
        </>
      )}

      <style>{`
        .pp-tabs { display: flex; flex-wrap: wrap; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 12px; }
        .pp-tabs button {
          background: none; border: none; border-bottom: 2px solid transparent; margin-bottom: -1px;
          padding: 8px 14px; font-size: 12.5px; cursor: pointer; color: var(--text-secondary);
          display: flex; align-items: center; gap: 6px;
        }
        .pp-tabs button:hover { color: var(--text-primary); }
        .pp-tabs button.activo { color: var(--text-primary); font-weight: 600; border-bottom-color: var(--accent, #0f6cbd); }
        .pp-conteo { font-size: 10.5px; background: var(--bg-surface-2); padding: 1px 6px; border-radius: 8px; color: var(--text-muted); }
        .pp-barra { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
        .pp-buscar { display: flex; align-items: center; gap: 6px; flex: 0 1 320px; color: var(--text-muted); }
        .pp-buscar .input-base { width: 100%; }
        .pp-nota { font-size: 11.5px; color: var(--text-muted); }
        .pp-tabla-wrap { overflow-x: auto; }
        .pp-tabla { width: 100%; }
        .pp-tabla td { vertical-align: middle; }
        .pp-tipo { display: block; font-size: 10.5px; color: var(--text-muted); }
        .pp-precio { width: 120px; text-align: right; font-variant-numeric: tabular-nums; }
        .pp-iva { color: var(--text-muted); font-variant-numeric: tabular-nums; font-size: 12px; }
        .der, .pp-tabla th.der { text-align: right; }
        .pp-vacio { text-align: center; padding: 18px; color: var(--text-muted); }
        .pp-agregar {
          display: grid; grid-template-columns: auto minmax(180px, 1fr) 130px 130px auto; gap: 8px;
          align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border);
        }
        @media (max-width: 760px) { .pp-agregar { grid-template-columns: 1fr 1fr; } .pp-agregar-titulo { grid-column: 1 / -1; } }
        .pp-agregar .input-base { width: 100%; min-width: 0; }
        .pp-agregar-titulo { display: flex; align-items: center; gap: 4px; font-size: 12.5px; font-weight: 600; white-space: nowrap; }
      `}</style>
    </div>
  );
}
