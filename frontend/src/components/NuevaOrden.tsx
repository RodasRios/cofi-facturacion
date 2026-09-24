import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { crearOrdenSuministro } from "../api/ordenesSuministro";
import { mensajeError } from "../lib/errores";
import { pesos } from "../lib/cotizacion";
import type { Cotizacion, OrdenSuministro } from "../types";

const n = (v: string | number | null | undefined) => Number(v ?? 0);
const cant = (v: number) => v.toLocaleString("es-CO", { maximumFractionDigits: 2 });

/**
 * Emitir una orden de suministro a mano: planta, cuánto de cada material
 * (puede ser parcial), fecha de retiro, placas y observación.
 */
export function NuevaOrden({ cotizaciones, inicial, onCreada, onCancelar }: {
  cotizaciones: Cotizacion[];
  inicial: number | null;
  onCreada: (o: OrdenSuministro) => void;
  onCancelar: () => void;
}) {
  const qc = useQueryClient();
  const [cotId, setCotId] = useState(inicial ? String(inicial) : "");
  const cot = cotizaciones.find(c => String(c.id) === cotId);

  // Plantas de la cotización con algo por ordenar.
  const plantas = useMemo(() => {
    const vistas = new Map<number, string>();
    cot?.items.forEach(i => {
      if (i.planta_efectiva && n(i.cantidad) > n(i.cantidad_ordenada)) vistas.set(i.planta_efectiva, i.planta_nombre ?? "");
    });
    return [...vistas.entries()].map(([id, nombre]) => ({ id, nombre }));
  }, [cot]);

  const [plantaId, setPlantaId] = useState<string>("");
  const planta = plantas.find(p => String(p.id) === plantaId) ?? (plantas.length === 1 ? plantas[0] : undefined);
  const lineas = (cot?.items ?? []).filter(i => planta && i.planta_efectiva === planta.id);

  const [cantidades, setCantidades] = useState<Record<number, string>>({});
  const [obra, setObra] = useState<string | null>(null);
  const [fecha, setFecha] = useState("");
  const [placasCliente, setPlacasCliente] = useState("");
  const [placasEmpresa, setPlacasEmpresa] = useState("");
  const [notas, setNotas] = useState("");

  const saldo = (i: Cotizacion["items"][number]) => Math.max(0, n(i.cantidad) - n(i.cantidad_ordenada));
  const cantidadDe = (i: Cotizacion["items"][number]) => cantidades[i.id] ?? String(saldo(i));

  // Valor de lo que se ordena (sin IVA) contra lo que está respaldado.
  const valorOrden = lineas.reduce((t, i) => t + n(cantidadDe(i)) * n(i.precio_unitario), 0);
  const factorTotal = cot && n(cot.subtotal_materiales) ? n(cot.total) / n(cot.subtotal_materiales) : 1;
  const respaldado = cot ? n(cot.total_pagado) + n(cot.total_por_confirmar) : 0;
  const yaOrdenado = cot ? (cot.porcentaje_ordenado / 100) * n(cot.total) : 0;
  const excedeRespaldo = cot && yaOrdenado + valorOrden * factorTotal > respaldado + 1;

  const problemas: string[] = [];
  if (!cot) problemas.push("Elige la cotización.");
  else if (!planta) problemas.push("Elige la planta.");
  else {
    lineas.forEach(i => {
      if (n(cantidadDe(i)) > saldo(i)) problemas.push(`${i.material_nombre}: máximo ${cant(saldo(i))} ${i.unidad_medida}.`);
    });
    if (!lineas.some(i => n(cantidadDe(i)) > 0)) problemas.push("Indica la cantidad de al menos un material.");
  }

  const mut = useMutation({
    mutationFn: () => crearOrdenSuministro({
      cotizacion: cot!.id, planta: planta!.id,
      items: lineas.filter(i => n(cantidadDe(i)) > 0).map(i => ({ cotizacion_item: i.id, cantidad: n(cantidadDe(i)) })),
      obra: obra ?? cot?.obra ?? "", fecha_suministro: fecha || null,
      placas_cliente: placasCliente, placas_empresa: placasEmpresa, notas,
    }),
    onSuccess: o => {
      ["ordenes-suministro", "por-ordenar", "tablero"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(`Orden ${o.numero} emitida`);
      onCreada(o);
    },
    onError: e => toast.error(mensajeError(e, "No se pudo emitir la orden")),
  });

  return (
    <form className="card no-form" onSubmit={e => { e.preventDefault(); if (!problemas.length) mut.mutate(); }}>
      <div className="no-titulo">
        <h2>Nueva orden de suministro</h2>
        <button type="button" className="btn-ghost" onClick={onCancelar}><Icon name="close" size={16} /></button>
      </div>

      <div className="no-grid">
        <label className="no-ancho">Cotización
          <select className="input-base" value={cotId} required onChange={e => {
            setCotId(e.target.value); setPlantaId(""); setCantidades({}); setObra(null);
          }}>
            <option value="">Selecciona…</option>
            {cotizaciones.map(c => (
              <option key={c.id} value={c.id}>{c.numero} — {c.cliente_nombre} · {c.porcentaje_ordenado}% ordenado</option>
            ))}
          </select>
        </label>

        {cot && (
          <div className="no-ancho no-respaldo">
            <span>Total <strong>{pesos(n(cot.total))}</strong></span>
            <span>Pagado <strong>{pesos(n(cot.total_pagado))}</strong></span>
            {n(cot.total_por_confirmar) > 0 && <span>Orden de compra <strong>{pesos(n(cot.total_por_confirmar))}</strong></span>}
            <span>Ya ordenado <strong>{cot.porcentaje_ordenado}%</strong></span>
          </div>
        )}

        {cot && plantas.length > 1 && (
          <div className="no-ancho no-plantas" role="radiogroup">
            {plantas.map(p => (
              <button type="button" key={p.id} className={planta?.id === p.id ? "activo" : ""}
                onClick={() => { setPlantaId(String(p.id)); setCantidades({}); }}>
                <Icon name="factory" size={15} />{p.nombre}
              </button>
            ))}
          </div>
        )}

        {planta && (
          <div className="no-ancho">
            <table className="table-sharp no-lineas">
              <thead><tr><th>Material</th><th className="der">Cotizado</th><th className="der">Ya ordenado</th><th className="der">Esta orden</th></tr></thead>
              <tbody>
                {lineas.map(i => {
                  const s = saldo(i);
                  return (
                    <tr key={i.id}>
                      <td>{i.material_nombre}</td>
                      <td className="der">{cant(n(i.cantidad))} {i.unidad_medida}</td>
                      <td className="der">{cant(n(i.cantidad_ordenada))}</td>
                      <td className="der">
                        {s > 0 ? (
                          <span className="no-cant">
                            <input className="input-base" type="number" min="0" step="0.01" max={s}
                              value={cantidadDe(i)} onChange={e => setCantidades(c => ({ ...c, [i.id]: e.target.value }))} />
                            <small>de {cant(s)}</small>
                          </span>
                        ) : <span className="no-completo">Completo</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {planta && (
          <>
            <label className="no-ancho">Obra
              <input className="input-base" value={obra ?? cot?.obra ?? ""} onChange={e => setObra(e.target.value)} />
            </label>
            <label>Fecha de suministro
              <input className="input-base" type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
            </label>
            <label>Placas del cliente
              <input className="input-base" value={placasCliente} placeholder="SPT880, WMB006"
                onChange={e => setPlacasCliente(e.target.value.toUpperCase())} />
            </label>
            <label>Placas Triturados y Concretos
              <input className="input-base" value={placasEmpresa} placeholder="Si el transporte es propio"
                onChange={e => setPlacasEmpresa(e.target.value.toUpperCase())} />
            </label>
            <label>Observación
              <input className="input-base" value={notas} onChange={e => setNotas(e.target.value)} />
            </label>
          </>
        )}
      </div>

      {excedeRespaldo && (
        <p className="no-aviso"><Icon name="warning" size={15} />
          Con esta orden lo despachado superaría lo pagado y respaldado por orden de compra ({pesos(respaldado)}).
          Se puede emitir, pero conviene confirmarlo con cartera.
        </p>
      )}
      {cot && problemas.length > 0 && <ul className="no-problemas">{problemas.map(p => <li key={p}>{p}</li>)}</ul>}

      <div className="no-acciones">
        <span className="no-valor">{planta && `Valor de esta orden: ${pesos(valorOrden * factorTotal)} con IVA`}</span>
        <button type="button" className="btn-secondary" onClick={onCancelar}>Cancelar</button>
        <button className="btn-primary" disabled={mut.isPending || problemas.length > 0}>
          <Icon name="local_shipping" size={15} />{mut.isPending ? "Emitiendo…" : "Emitir orden"}
        </button>
      </div>

      <style>{`
        .no-form { padding: 16px; margin-bottom: 14px; }
        .no-titulo { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .no-titulo h2 { font-size: 14px; font-weight: 700; margin: 0; }
        .no-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        @media (max-width: 640px) { .no-grid { grid-template-columns: 1fr; } }
        .no-grid > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .no-grid .input-base { width: 100%; font-weight: 400; }
        .no-ancho { grid-column: 1 / -1; }
        .no-respaldo { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; color: var(--text-secondary); background: var(--bg-surface-2); padding: 8px 12px; }
        .no-respaldo strong { color: var(--text-primary); }
        .no-plantas { display: flex; flex-wrap: wrap; gap: 6px; }
        .no-plantas button { display: inline-flex; align-items: center; gap: 6px; padding: 7px 12px; border: 1px solid var(--border);
          background: var(--bg-surface); color: var(--text-secondary); font: inherit; font-size: 12.5px; cursor: pointer; }
        .no-plantas button.activo { border-color: var(--accent); background: var(--accent-light); color: var(--accent-text); font-weight: 600; }
        .no-lineas .der { text-align: right; }
        .no-lineas td { vertical-align: middle; }
        .no-cant { display: inline-flex; align-items: center; gap: 6px; }
        .no-cant .input-base { width: 110px !important; text-align: right; }
        .no-cant small { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
        .no-completo { font-size: 11.5px; color: #16a34a; }
        .no-aviso { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; background: #fffbeb; color: #92400e;
          border: 1px solid #fcd34d; padding: 8px 10px; margin: 12px 0 0; }
        .dark .no-aviso { background: #2a1f05; color: #fbbf24; border-color: #78580c; }
        .no-problemas { font-size: 12px; color: #dc2626; margin: 10px 0 0; padding-left: 18px; }
        .no-acciones { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
        .no-valor { margin-right: auto; font-size: 12px; color: var(--text-muted); }
      `}</style>
    </form>
  );
}
