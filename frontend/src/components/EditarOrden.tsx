import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { actualizarOrdenSuministro } from "../api/ordenesSuministro";
import { getCotizacion } from "../api/cotizaciones";
import { mensajeError } from "../lib/errores";
import type { OrdenSuministro } from "../types";

const n = (v: string | number | null | undefined) => Number(v ?? 0);
const cant = (v: number) => v.toLocaleString("es-CO", { maximumFractionDigits: 2 });

/**
 * Editar una orden ya emitida: cantidades (dentro del saldo de la cotización y
 * nunca por debajo de lo ya despachado), obra, fecha, placas y observación.
 * Si cambia algo que la planta necesita saber y ya se le había avisado, el
 * servidor la deja otra vez "por avisar".
 */
export function EditarOrden({ orden, onListo }: { orden: OrdenSuministro; onListo: () => void }) {
  const qc = useQueryClient();
  const { data: cot } = useQuery({ queryKey: ["cotizacion", orden.cotizacion], queryFn: () => getCotizacion(orden.cotizacion) });
  const [cantidades, setCantidades] = useState<Record<number, string>>(() =>
    Object.fromEntries(orden.items.map(i => [i.cotizacion_item, String(n(i.cantidad))])));
  const [obra, setObra] = useState(orden.obra ?? "");
  const [fecha, setFecha] = useState(orden.fecha_suministro ?? "");
  const [cliente, setCliente] = useState(orden.placas_cliente ?? "");
  const [empresa, setEmpresa] = useState(orden.placas_empresa ?? "");
  const [obs, setObs] = useState(orden.notas ?? "");

  // Líneas de la cotización en la planta de esta orden.
  const lineas = (cot?.items ?? []).filter(i => i.planta_efectiva === orden.planta);
  const enEstaOrden = (id: number) => n(orden.items.find(i => i.cotizacion_item === id)?.cantidad);
  const maximo = (i: (typeof lineas)[number]) => n(i.cantidad) - n(i.cantidad_ordenada) + enEstaOrden(i.id);
  const despachado = (materialId: number) => n(orden.items.find(i => i.material === materialId)?.cantidad_despachada);

  const problemas = lineas.flatMap(i => {
    const v = n(cantidades[i.id]);
    const out: string[] = [];
    if (v > maximo(i)) out.push(`${i.material_nombre}: máximo ${cant(maximo(i))} ${i.unidad_medida}.`);
    if (despachado(i.material) > 0 && v < despachado(i.material))
      out.push(`${i.material_nombre}: ya se despacharon ${cant(despachado(i.material))}.`);
    return out;
  });
  if (cot && !lineas.some(i => n(cantidades[i.id]) > 0)) problemas.push("La orden debe tener al menos un material.");

  const guardar = useMutation({
    mutationFn: () => actualizarOrdenSuministro(orden.id, {
      obra, fecha_suministro: fecha || null, placas_cliente: cliente, placas_empresa: empresa, notas: obs,
      items: lineas.filter(i => n(cantidades[i.id]) > 0).map(i => ({ cotizacion_item: i.id, cantidad: n(cantidades[i.id]) })),
    }),
    onSuccess: o => {
      ["ordenes-suministro", "por-ordenar", "tablero", "cotizacion"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(orden.notificada_planta && !o.notificada_planta
        ? "Orden actualizada — vuelve a avisarle a la planta del cambio"
        : "Orden actualizada");
      onListo();
    },
    onError: e => toast.error(mensajeError(e, "No se pudo actualizar la orden")),
  });

  return (
    <form className="eo" onSubmit={e => { e.preventDefault(); if (!problemas.length) guardar.mutate(); }}>
      {!cot && <p className="eo-sub">Cargando…</p>}
      {lineas.length > 0 && (
        <div className="eo-lineas">
          {lineas.map(i => (
            <label key={i.id}>
              <span>{i.material_nombre}
                <small>máx. {cant(maximo(i))} {i.unidad_medida}{despachado(i.material) > 0 && ` · despachado ${cant(despachado(i.material))}`}</small>
              </span>
              <span className="eo-cant">
                <input className="input-base" type="number" min="0" step="0.01" value={cantidades[i.id] ?? ""}
                  placeholder="0" onChange={e => setCantidades(c => ({ ...c, [i.id]: e.target.value }))} />
                {i.unidad_medida}
              </span>
            </label>
          ))}
        </div>
      )}
      <div className="eo-campos">
        <label className="eo-ancho">Obra<input className="input-base" value={obra} onChange={e => setObra(e.target.value)} /></label>
        <label>Fecha de suministro<input className="input-base" type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></label>
        <label>Placas del cliente<input className="input-base" value={cliente} placeholder="SPT880, WMB006" onChange={e => setCliente(e.target.value.toUpperCase())} /></label>
        <label>Placas Triturados y Concretos<input className="input-base" value={empresa} placeholder="Si el transporte es propio" onChange={e => setEmpresa(e.target.value.toUpperCase())} /></label>
        <label>Observación<input className="input-base" value={obs} onChange={e => setObs(e.target.value)} /></label>
      </div>
      {problemas.length > 0 && <ul className="eo-problemas">{problemas.map(p => <li key={p}>{p}</li>)}</ul>}
      <div className="eo-acciones">
        {orden.notificada_planta && <span className="eo-sub">Si cambias material, fecha o placas, habrá que volver a avisar a la planta.</span>}
        <button type="button" className="btn-secondary" onClick={onListo}>Cancelar</button>
        <button className="btn-primary" disabled={guardar.isPending || problemas.length > 0 || !cot}>
          <Icon name="save" size={14} />{guardar.isPending ? "Guardando…" : "Guardar cambios"}
        </button>
      </div>
      <style>{`
        .eo { padding: 12px 14px; display: flex; flex-direction: column; gap: 10px; }
        .eo-sub { font-size: 11.5px; color: var(--text-muted); margin: 0; }
        .eo-lineas { display: flex; flex-direction: column; gap: 6px; }
        .eo-lineas label { display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: 13px; flex-wrap: wrap; }
        .eo-lineas small { display: block; font-size: 11px; color: var(--text-muted); }
        .eo-cant { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
        .eo-cant .input-base { width: 110px; text-align: right; }
        .eo-campos { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
        .eo-campos > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .eo-campos .input-base { width: 100%; font-weight: 400; }
        .eo-ancho { grid-column: 1 / -1; }
        .eo-problemas { margin: 0; padding-left: 18px; font-size: 12px; color: #dc2626; }
        .eo-acciones { display: flex; justify-content: flex-end; align-items: center; gap: 8px; flex-wrap: wrap; }
        .eo-acciones .eo-sub { margin-right: auto; }
      `}</style>
    </form>
  );
}
