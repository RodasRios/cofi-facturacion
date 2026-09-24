import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getDespachos, createDespacho, subirSoporteDespacho } from "../api/despachos";
import { getOrdenesSuministro } from "../api/ordenesSuministro";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { mensajeError } from "../lib/errores";
import type { Despacho, OrdenSuministro } from "../types";

const n = (v: string | number | null | undefined) => Number(v ?? 0);
const cant = (v: number) => v.toLocaleString("es-CO", { maximumFractionDigits: 2 });

function FormDespacho({ orden, onListo }: { orden: OrdenSuministro; onListo: () => void }) {
  const qc = useQueryClient();
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [placa, setPlaca] = useState("");
  const [consecutivo, setConsecutivo] = useState("");
  const [recibidoPor, setRecibidoPor] = useState("");
  const [clienteRetira, setClienteRetira] = useState(!orden.placas_empresa);
  const [notas, setNotas] = useState("");
  const [soporte, setSoporte] = useState<File | null>(null);
  const saldo = (i: OrdenSuministro["items"][number]) => Math.max(0, n(i.cantidad) - n(i.cantidad_despachada));
  const [cantidades, setCantidades] = useState<Record<number, string>>({});
  const cantidadDe = (i: OrdenSuministro["items"][number]) => cantidades[i.id] ?? "";
  const placasOrden = [orden.placas_cliente, orden.placas_empresa].filter(Boolean).join(", ");

  const mut = useMutation({
    mutationFn: async () => {
      const d = await createDespacho({
        orden_suministro: orden.id, fecha, consecutivo, recibido_por: recibidoPor,
        placa_vehiculo: placa, cliente_retira: clienteRetira, notas,
        // El despacho se registra por material: si la orden trae el mismo material
        // en dos líneas, se suman.
        items: Object.entries(orden.items.reduce<Record<number, number>>((acc, i) => {
          if (n(cantidadDe(i)) > 0) acc[i.material] = (acc[i.material] ?? 0) + n(cantidadDe(i));
          return acc;
        }, {})).map(([material, cantidad]) => ({ material: Number(material), cantidad })),
      });
      return soporte ? subirSoporteDespacho(d.id, soporte) : d;
    },
    onSuccess: d => {
      ["despachos", "ordenes-suministro", "tablero"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(`Despacho ${d.numero} registrado`);
      onListo();
    },
    onError: e => toast.error(mensajeError(e, "No se pudo registrar el despacho")),
  });

  const hayCantidad = orden.items.some(i => n(cantidadDe(i)) > 0);
  const excede = orden.items.filter(i => n(cantidadDe(i)) > saldo(i));

  return (
    <form className="ds-form" onSubmit={e => { e.preventDefault(); mut.mutate(); }}>
      <div className="ds-lineas">
        {orden.items.map(i => (
          <label key={i.id}>
            <span>{i.material_nombre}<small>quedan {cant(saldo(i))} de {cant(n(i.cantidad))} {i.unidad_medida}</small></span>
            <span className="ds-cant">
              <input className="input-base" type="number" min="0" step="0.01" placeholder="0"
                value={cantidadDe(i)} onChange={e => setCantidades(c => ({ ...c, [i.id]: e.target.value }))} />
              {i.unidad_medida}
            </span>
          </label>
        ))}
      </div>
      {excede.length > 0 && (
        <p className="ds-aviso"><Icon name="warning" size={14} />
          {excede.map(i => i.material_nombre).join(", ")}: supera lo que queda por despachar de la orden.
        </p>
      )}
      <div className="ds-campos">
        <label>Fecha<input className="input-base" type="date" value={fecha} onChange={e => setFecha(e.target.value)} required /></label>
        <label>Tiquete de báscula<input className="input-base" value={consecutivo} placeholder="758812" onChange={e => setConsecutivo(e.target.value)} /></label>
        <label>Placa del vehículo
          <input className="input-base" value={placa} list={`placas-${orden.id}`} placeholder={placasOrden || "ABC123"}
            onChange={e => setPlaca(e.target.value.toUpperCase())} />
          <datalist id={`placas-${orden.id}`}>
            {placasOrden.split(/[,;\n]+/).map(p => p.trim()).filter(Boolean).map(p => <option key={p} value={p} />)}
          </datalist>
        </label>
        <label>Recibido por<input className="input-base" value={recibidoPor} onChange={e => setRecibidoPor(e.target.value)} /></label>
        <label className="ds-ancho">Foto o PDF del tiquete firmado
          <input className="input-base" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" capture="environment"
            onChange={e => setSoporte(e.target.files?.[0] ?? null)} />
        </label>
        <label className="ds-ancho">Notas<input className="input-base" value={notas} onChange={e => setNotas(e.target.value)} /></label>
        <label className="ds-check">
          <input type="checkbox" checked={clienteRetira} onChange={e => setClienteRetira(e.target.checked)} />
          El cliente retira con su vehículo
        </label>
      </div>
      <div className="ds-acciones">
        <button type="button" className="btn-secondary" onClick={onListo}>Cancelar</button>
        <button className="btn-primary" disabled={mut.isPending || !hayCantidad}>
          <Icon name="local_shipping" size={15} />{mut.isPending ? "Guardando…" : "Registrar despacho"}
        </button>
      </div>
    </form>
  );
}

export function DespachosPage() {
  const qc = useQueryClient();
  const { data: despachos, isLoading } = useQuery({ queryKey: ["despachos"], queryFn: () => getDespachos() });
  const { data: ordenes } = useQuery({ queryKey: ["ordenes-suministro"], queryFn: () => getOrdenesSuministro() });
  const [visor, setVisor] = useState<{ url: string; filename: string } | null>(null);
  const [abierta, setAbierta] = useState<number | null>(null);

  const pendientes = useMemo(() => (ordenes ?? []).filter(o => !o.completamente_despachada), [ordenes]);

  const soporte = useMutation({
    mutationFn: ({ d, file }: { d: Despacho; file: File }) => subirSoporteDespacho(d.id, file),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["despachos"] }); toast.success("Soporte cargado"); },
    onError: e => toast.error(mensajeError(e, "No se pudo subir el soporte")),
  });

  const verSoporte = (d: Despacho) => {
    const ext = d.soporte_path?.split(".").pop() ?? "pdf";
    setVisor({ url: `/despachos/${d.id}/soporte/`, filename: `${d.numero}_soporte.${ext}` });
  };

  return (
    <div className="ds">
      <h1>Despachos</h1>

      <section className="card ds-seccion">
        <h2>Órdenes por despachar <span className="ds-conteo">{pendientes.length}</span></h2>
        {pendientes.length === 0 && <p className="ds-vacio">No hay órdenes pendientes de despacho.</p>}
        <div className="ds-ordenes">
          {pendientes.map(o => (
            <article key={o.id} className={`ds-orden ${abierta === o.id ? "abierta" : ""}`}>
              <header>
                <div>
                  <strong>{o.numero}</strong> · {o.planta_nombre.replace("Planta ", "")}
                  <span className="ds-sub">{o.cliente_nombre}{o.obra && ` — ${o.obra}`}</span>
                </div>
                <div className="ds-meta">
                  {o.fecha_suministro && <span><Icon name="event" size={13} />{new Date(o.fecha_suministro + "T00:00:00").toLocaleDateString("es-CO")}</span>}
                  {(o.placas_cliente || o.placas_empresa) && <span><Icon name="directions_car" size={13} />{[o.placas_cliente, o.placas_empresa].filter(Boolean).join(", ")}</span>}
                </div>
                <div className="ds-botones">
                  <button className="btn-ghost" title="Ver orden" onClick={() => setVisor({ url: `/ordenes-suministro/${o.id}/pdf/`, filename: `${o.numero}.pdf` })}>
                    <Icon name="picture_as_pdf" size={16} />
                  </button>
                  {abierta !== o.id && (
                    <button className="btn-primary" onClick={() => setAbierta(o.id)}><Icon name="add" size={15} />Despachar</button>
                  )}
                </div>
              </header>
              <div className="ds-saldos">
                {o.items.map(i => {
                  const pct = Math.min(100, (n(i.cantidad_despachada) / (n(i.cantidad) || 1)) * 100);
                  return (
                    <div key={i.id}>
                      <span>{i.material_nombre}</span>
                      <span className="ds-pista"><i style={{ width: `${pct}%` }} /></span>
                      <span className="ds-num">{cant(n(i.cantidad_despachada))} / {cant(n(i.cantidad))} {i.unidad_medida}</span>
                    </div>
                  );
                })}
              </div>
              {abierta === o.id && <FormDespacho orden={o} onListo={() => setAbierta(null)} />}
            </article>
          ))}
        </div>
      </section>

      <section className="card ds-seccion">
        <h2>Despachos registrados</h2>
        <table className="table-sharp">
          <thead><tr><th>N.°</th><th>Fecha</th><th>Cliente</th><th>Material</th><th>Vehículo</th><th>Soporte</th><th /></tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="ds-vacio">Cargando…</td></tr>}
            {despachos?.map(d => (
              <tr key={d.id}>
                <td className="nowrap"><strong>{d.numero}</strong><span className="ds-sub">{d.orden_suministro_numero}{d.consecutivo && ` · tiq. ${d.consecutivo}`}</span></td>
                <td className="nowrap">{new Date(d.fecha + "T00:00:00").toLocaleDateString("es-CO")}</td>
                <td>{d.cliente_nombre}<span className="ds-sub">{d.planta_nombre}</span></td>
                <td className="ds-sub-celda">{d.items.map(i => `${i.material_nombre} ${cant(n(i.cantidad))} ${i.unidad_medida}`).join(", ")}</td>
                <td>{d.placa_vehiculo || "—"}<span className="ds-sub">{d.cliente_retira ? "Cliente" : "Propio"}</span></td>
                <td>
                  {d.soporte_path ? (
                    <button className="btn-ghost" onClick={() => verSoporte(d)}><Icon name="image" size={16} />Ver</button>
                  ) : (
                    <label className="btn-secondary" style={{ cursor: "pointer" }}>
                      <Icon name="upload" size={14} />Subir
                      <input type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp"
                        onChange={e => e.target.files?.[0] && soporte.mutate({ d, file: e.target.files[0] })} />
                    </label>
                  )}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button className="btn-ghost" title="Remisión PDF" onClick={() => setVisor({ url: `/despachos/${d.id}/pdf/`, filename: `${d.numero}.pdf` })}>
                    <Icon name="picture_as_pdf" size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && despachos?.length === 0 && <tr><td colSpan={7} className="ds-vacio">Sin despachos todavía</td></tr>}
          </tbody>
        </table>
      </section>

      {visor && <PdfViewerModal url={visor.url} filename={visor.filename} onClose={() => setVisor(null)} />}

      <style>{`
        .ds h1 { font-size: 18px; font-weight: 700; margin: 0 0 14px; }
        .ds-seccion { padding: 14px; margin-bottom: 14px; overflow-x: auto; }
        .ds-seccion h2 { font-size: 14px; font-weight: 700; margin: 0 0 10px; display: flex; gap: 6px; align-items: center; }
        .ds-conteo { font-size: 11px; background: var(--bg-surface-2); color: var(--text-muted); padding: 1px 7px; border-radius: 8px; }
        .ds-vacio { text-align: center; padding: 16px; color: var(--text-muted); font-size: 12.5px; }
        .ds-sub { display: block; font-size: 11px; color: var(--text-muted); }
        .ds-sub-celda { font-size: 12px; }
        .ds-ordenes { display: flex; flex-direction: column; gap: 10px; }
        .ds-orden { border: 1px solid var(--border); padding: 12px; background: var(--bg-surface); }
        .ds-orden.abierta { border-color: var(--accent); }
        .ds-orden header { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .ds-orden header > div:first-child { flex: 1; min-width: 180px; font-size: 13px; }
        .ds-meta { display: flex; gap: 12px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; }
        .ds-meta span { display: inline-flex; align-items: center; gap: 4px; }
        .ds-botones { display: flex; gap: 6px; }
        .ds-saldos { display: flex; flex-direction: column; gap: 5px; margin-top: 10px; font-size: 12px; }
        .ds-saldos > div { display: grid; grid-template-columns: minmax(100px, 30%) 1fr auto; gap: 10px; align-items: center; }
        .ds-pista { height: 7px; background: var(--bg-surface-2); }
        .ds-pista i { display: block; height: 100%; background: #16a34a; }
        .ds-num { font-variant-numeric: tabular-nums; color: var(--text-secondary); white-space: nowrap; }
        .ds-form { border-top: 1px dashed var(--border); margin-top: 12px; padding-top: 12px; }
        .ds-lineas { display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px; }
        .ds-lineas label { display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: 13px; flex-wrap: wrap; }
        .ds-lineas small { display: block; font-size: 11px; color: var(--text-muted); }
        .ds-cant { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
        .ds-cant .input-base { width: 120px; text-align: right; }
        .ds-aviso { display: flex; gap: 6px; font-size: 12px; color: #b45309; margin: 0 0 10px; }
        .ds-campos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
        @media (max-width: 800px) { .ds-campos { grid-template-columns: 1fr 1fr; } }
        @media (max-width: 480px) { .ds-campos { grid-template-columns: 1fr; } }
        .ds-campos > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .ds-campos .input-base { width: 100%; font-weight: 400; }
        .ds-ancho { grid-column: span 2; }
        @media (max-width: 480px) { .ds-ancho { grid-column: auto; } }
        .ds-check { flex-direction: row !important; align-items: center; font-weight: 400 !important; grid-column: 1 / -1; }
        .ds-acciones { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
      `}</style>
    </div>
  );
}
