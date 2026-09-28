import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { renombrarMaterial, unirMaterial } from "../api/materiales";
import { mensajeError } from "../lib/errores";
import type { Material, Planta } from "../types";

/**
 * Nombres del catálogo, que son los que salen en solicitudes, cotizaciones,
 * precios y disponibilidad. Cada planta nombraba distinto el mismo material
 * ("Gravilla 3/4" / "Gravilla (canto rodado) 3/4\""), así que aquí se pueden
 * renombrar y unir los duplicados en uno solo.
 */
export function CatalogoMateriales({ materiales, plantas }: { materiales: Material[]; plantas: Planta[] }) {
  const qc = useQueryClient();
  const [buscar, setBuscar] = useState("");
  const [uniendo, setUniendo] = useState<Material | null>(null);
  const [destino, setDestino] = useState("");

  const invalidar = () => ["materiales", "disponibilidad", "solicitudes", "cotizaciones"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
  const renombrar = useMutation({
    mutationFn: ({ id, nombre }: { id: number; nombre: string }) => renombrarMaterial(id, nombre),
    onSuccess: () => { invalidar(); toast.success("Nombre actualizado en toda la aplicación"); },
    onError: e => toast.error(mensajeError(e, "No se pudo renombrar")),
  });
  const unir = useMutation({
    mutationFn: () => unirMaterial(uniendo!.id, Number(destino)),
    onSuccess: r => { invalidar(); toast.success(r.detail); setUniendo(null); setDestino(""); },
    onError: e => toast.error(mensajeError(e, "No se pudieron unir")),
  });

  const nombrePlanta = (id: number) => plantas.find(p => p.id === id)?.nombre.replace("Planta ", "") ?? "";
  const filas = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    return [...materiales].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
      .filter(m => !q || m.nombre.toLowerCase().includes(q));
  }, [materiales, buscar]);

  return (
    <div className="cm">
      <div className="cm-buscar">
        <Icon name="search" size={15} />
        <input className="input-base" placeholder="Buscar material…" value={buscar} onChange={e => setBuscar(e.target.value)} />
      </div>
      <table className="table-sharp cm-tabla">
        <thead><tr><th>Nombre (se guarda al salir de la casilla)</th><th>Unidad</th><th>Plantas que lo venden</th><th /></tr></thead>
        <tbody>
          {filas.map(m => (
            <tr key={m.id}>
              <td>
                <input className="input-base" key={`${m.id}-${m.nombre}`} defaultValue={m.nombre} style={{ width: "100%" }}
                  onBlur={e => { const v = e.target.value.trim(); if (v && v !== m.nombre) renombrar.mutate({ id: m.id, nombre: v }); }}
                  onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
              </td>
              <td>{m.unidad_medida}</td>
              <td className="cm-plantas">
                {m.precios.length ? m.precios.map(p => nombrePlanta(p.planta)).filter(Boolean).join(", ") : <em>Ninguna</em>}
              </td>
              <td style={{ textAlign: "right" }}>
                <button className="btn-ghost" title="Es el mismo que otro material: unirlos" onClick={() => { setUniendo(m); setDestino(""); }}>
                  <Icon name="merge" size={16} />Unir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {uniendo && (
        <div className="cm-modal" role="dialog" onClick={() => setUniendo(null)}>
          <form className="card cm-dialogo" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); unir.mutate(); }}>
            <h3>Unir “{uniendo.nombre}”</h3>
            <p>Elige el nombre que se queda. Todo lo de “{uniendo.nombre}” (precios por planta, solicitudes,
              cotizaciones y despachos) pasa a ese material y “{uniendo.nombre}” desaparece de las listas.
              Si los dos tienen precio en la misma planta, se conserva el del que se queda.</p>
            <select className="input-base" value={destino} onChange={e => setDestino(e.target.value)} required autoFocus>
              <option value="">Queda con el nombre…</option>
              {materiales.filter(m => m.id !== uniendo.id && m.unidad_medida === uniendo.unidad_medida)
                .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
                .map(m => <option key={m.id} value={m.id}>{m.nombre}</option>)}
            </select>
            <div className="cm-acciones">
              <button type="button" className="btn-secondary" onClick={() => setUniendo(null)}>Cancelar</button>
              <button className="btn-primary" disabled={!destino || unir.isPending}><Icon name="merge" size={15} />Unir</button>
            </div>
          </form>
        </div>
      )}

      <style>{`
        .cm-buscar { display: flex; align-items: center; gap: 6px; max-width: 320px; margin-bottom: 10px; color: var(--text-muted); }
        .cm-buscar .input-base { width: 100%; }
        .cm-tabla td { vertical-align: middle; }
        .cm-plantas { font-size: 12px; color: var(--text-secondary); }
        .cm-plantas em { color: #b45309; }
        .cm-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 16px; }
        .cm-dialogo { max-width: 480px; width: 100%; padding: 18px; display: flex; flex-direction: column; gap: 10px; }
        .cm-dialogo h3 { margin: 0; font-size: 15px; }
        .cm-dialogo p { margin: 0; font-size: 12.5px; color: var(--text-secondary); }
        .cm-acciones { display: flex; justify-content: flex-end; gap: 8px; }
      `}</style>
    </div>
  );
}
