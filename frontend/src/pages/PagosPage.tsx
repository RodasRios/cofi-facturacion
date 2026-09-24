import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getPagos, createPago, uploadComprobante, aprobarPago } from "../api/pagos";
import { getCotizaciones } from "../api/cotizaciones";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { pesos } from "../lib/cotizacion";
import { puede } from "../lib/permisos";
import { mensajeError } from "../lib/errores";
import type { Cotizacion, Pago, PagoEstado, PagoTipo } from "../types";

const ESTADO: Record<PagoEstado, { label: string; color: string }> = {
  pendiente: { label: "Por revisar", color: "#d97706" },
  por_confirmar: { label: "OC por confirmar", color: "#7c3aed" },
  aprobado: { label: "Aprobado", color: "#16a34a" },
  rechazado: { label: "Rechazado", color: "#dc2626" },
};

const n = (v: string | number | null | undefined) => Number(v ?? 0);

/** Barra de cobro: pagado (verde), OC por confirmar (morado), en revisión (ámbar). */
function BarraCobro({ c }: { c: Cotizacion }) {
  const total = n(c.total) || 1;
  const pct = (v: string) => `${Math.min(100, (n(v) / total) * 100)}%`;
  return (
    <div className="pg-barra" title={`Pagado ${pesos(n(c.total_pagado))} · OC ${pesos(n(c.total_por_confirmar))} · En revisión ${pesos(n(c.total_en_revision))}`}>
      <i className="pagado" style={{ width: pct(c.total_pagado) }} />
      <i className="oc" style={{ width: pct(c.total_por_confirmar) }} />
      <i className="revision" style={{ width: pct(c.total_en_revision) }} />
    </div>
  );
}

function FormPago({ cotizaciones, inicial, onListo }: { cotizaciones: Cotizacion[]; inicial: number | null; onListo: () => void }) {
  const qc = useQueryClient();
  const [cotId, setCotId] = useState(inicial ? String(inicial) : "");
  const cot = cotizaciones.find(c => String(c.id) === cotId);
  const [tipo, setTipo] = useState<PagoTipo>("transferencia");
  const [monto, setMonto] = useState(() => (cot ? String(Math.round(n(cot.saldo_sin_registrar))) : ""));
  const [referencia, setReferencia] = useState("");
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [notas, setNotas] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const saldo = n(cot?.saldo_sin_registrar);
  const excede = cot && n(monto) > saldo + 1;

  const mut = useMutation({
    mutationFn: () => createPago({
      cotizacion: Number(cotId), tipo, monto: n(monto), referencia, fecha_pago: fecha, notas, file: archivo,
    }),
    onSuccess: () => {
      ["pagos", "cotizaciones", "tablero", "cartera"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
      toast.success(tipo === "orden_compra" ? "Orden de compra registrada — queda por confirmar" : "Pago registrado — pendiente de revisión");
      onListo();
    },
    onError: e => toast.error(mensajeError(e, "No se pudo registrar el pago")),
  });

  return (
    <form className="card pg-form" onSubmit={e => { e.preventDefault(); mut.mutate(); }}>
      <div className="pg-form-titulo">
        <h2>Registrar pago</h2>
        <button type="button" className="btn-ghost" onClick={onListo}><Icon name="close" size={16} /></button>
      </div>

      <div className="pg-tipo" role="radiogroup">
        <button type="button" className={tipo === "transferencia" ? "activo" : ""} onClick={() => setTipo("transferencia")}>
          <Icon name="account_balance" size={18} />
          <span><strong>Pago / abono</strong><small>Transferencia o consignación. Financiera la revisa.</small></span>
        </button>
        <button type="button" className={tipo === "orden_compra" ? "activo" : ""} onClick={() => setTipo("orden_compra")}>
          <Icon name="assignment" size={18} />
          <span><strong>Orden de compra</strong><small>El cliente se compromete a pagar. Queda por confirmar.</small></span>
        </button>
      </div>

      <div className="pg-campos">
        <label className="pg-ancho">Cotización
          <select className="input-base" value={cotId} required onChange={e => {
            setCotId(e.target.value);
            const c = cotizaciones.find(x => String(x.id) === e.target.value);
            setMonto(c ? String(Math.round(n(c.saldo_sin_registrar))) : "");
          }}>
            <option value="">Selecciona…</option>
            {cotizaciones.map(c => (
              <option key={c.id} value={c.id}>
                {c.numero} — {c.cliente_nombre} · falta {pesos(n(c.saldo_sin_registrar))}
              </option>
            ))}
          </select>
        </label>
        {cot && (
          <div className="pg-ancho pg-resumen">
            <span>Total <strong>{pesos(n(cot.total))}</strong></span>
            <span>Pagado <strong>{pesos(n(cot.total_pagado))}</strong></span>
            {n(cot.total_por_confirmar) > 0 && <span>OC <strong>{pesos(n(cot.total_por_confirmar))}</strong></span>}
            {n(cot.total_en_revision) > 0 && <span>En revisión <strong>{pesos(n(cot.total_en_revision))}</strong></span>}
            <span>Falta cubrir <strong>{pesos(saldo)}</strong></span>
          </div>
        )}
        <label>Monto
          <div className="pg-monto">
            <input className="input-base" type="number" min="1" step="1" value={monto} required
              onChange={e => setMonto(e.target.value)} />
            {cot && <button type="button" className="btn-ghost" onClick={() => setMonto(String(Math.round(saldo)))}>Todo</button>}
          </div>
          {cot && n(monto) > 0 && n(monto) < saldo && <small className="pg-nota">Abono parcial: quedan {pesos(saldo - n(monto))}</small>}
          {excede && <small className="pg-error">Supera lo que falta por cubrir</small>}
        </label>
        <label>{tipo === "orden_compra" ? "N.º de orden de compra" : "N.º de transacción / referencia"}
          <input className="input-base" value={referencia} onChange={e => setReferencia(e.target.value)}
            placeholder={tipo === "orden_compra" ? "OC-2026-118" : "Opcional"} required={tipo === "orden_compra"} />
        </label>
        <label>{tipo === "orden_compra" ? "Fecha de la orden" : "Fecha del pago"}
          <input className="input-base" type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
        </label>
        <label>{tipo === "orden_compra" ? "Documento de la orden de compra" : "Comprobante"}
          <input className="input-base" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => setArchivo(e.target.files?.[0] ?? null)} />
        </label>
        <label className="pg-ancho">Notas
          <input className="input-base" value={notas} onChange={e => setNotas(e.target.value)}
            placeholder={tipo === "orden_compra" ? "Ej. pago a 30 días" : ""} />
        </label>
      </div>
      <div className="pg-acciones">
        <button type="button" className="btn-secondary" onClick={onListo}>Cancelar</button>
        <button className="btn-primary" disabled={mut.isPending || !cot || !!excede || n(monto) <= 0}>
          <Icon name="check" size={15} />{mut.isPending ? "Guardando…" : "Registrar"}
        </button>
      </div>
    </form>
  );
}

export function PagosPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const puedeRegistrar = puede(user, "pagos");
  const puedeAprobar = puede(user, "aprobar_pagos");
  const { data: pagos, isLoading } = useQuery({ queryKey: ["pagos"], queryFn: () => getPagos() });
  const { data: cotizaciones } = useQuery({ queryKey: ["cotizaciones", "aprobada"], queryFn: () => getCotizaciones("aprobada") });
  const [form, setForm] = useState<{ cot: number | null } | null>(null);
  const [visor, setVisor] = useState<{ url: string; filename: string } | null>(null);
  const [verSaldadas, setVerSaldadas] = useState(false);

  const conSaldo = useMemo(() => (cotizaciones ?? []).filter(c => n(c.saldo_por_cobrar) > 0), [cotizaciones]);
  const paraRegistrar = useMemo(() => (cotizaciones ?? []).filter(c => n(c.saldo_sin_registrar) > 0), [cotizaciones]);
  const porRevisar = (pagos ?? []).filter(p => p.estado === "pendiente" || p.estado === "por_confirmar");
  const invalidar = () => ["pagos", "cotizaciones", "tablero", "cartera"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));

  const comprobante = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => uploadComprobante(id, file),
    onSuccess: () => { invalidar(); toast.success("Archivo cargado"); },
    onError: e => toast.error(mensajeError(e, "No se pudo cargar el archivo")),
  });
  const decidir = useMutation({
    mutationFn: ({ p, aprobar, monto, motivo }: { p: Pago; aprobar: boolean; monto?: number; motivo?: string }) =>
      aprobarPago(p.id, aprobar, { monto, motivo }),
    onSuccess: p => { invalidar(); toast.success(`${p.tipo === "orden_compra" ? "Orden de compra" : "Pago"}: ${ESTADO[p.estado].label.toLowerCase()}`); },
    onError: e => toast.error(mensajeError(e, "No se pudo actualizar")),
  });

  const confirmarOC = (p: Pago) => {
    const txt = prompt(`¿Cuánto ingresó por la orden de compra ${p.referencia ?? ""}?`, String(Math.round(n(p.monto))));
    if (txt === null) return;
    const monto = Number(txt.replace(/[^\d]/g, ""));
    if (!(monto > 0)) { toast.error("Monto no válido"); return; }
    decidir.mutate({ p, aprobar: true, monto });
  };
  const rechazar = (p: Pago) => {
    const motivo = prompt(p.tipo === "orden_compra" ? "¿Por qué se anula la orden de compra?" : "Motivo del rechazo");
    if (motivo === null) return;
    decidir.mutate({ p, aprobar: false, motivo });
  };
  const verArchivo = (p: Pago) => {
    const ext = p.comprobante_path?.split(".").pop() ?? "pdf";
    setVisor({ url: `/pagos/${p.id}/comprobante/`, filename: `${p.cotizacion_numero}_${p.id}.${ext}` });
  };

  const cotizacionesVisibles = verSaldadas ? cotizaciones ?? [] : conSaldo;

  return (
    <div className="pg">
      <div className="pg-cabecera">
        <h1>Pagos</h1>
        {puedeRegistrar && !form && (
          <button className="btn-primary" onClick={() => setForm({ cot: null })}>
            <Icon name="add" size={16} />Registrar pago u orden de compra
          </button>
        )}
      </div>

      {form && <FormPago key={form.cot ?? "nuevo"} cotizaciones={paraRegistrar} inicial={form.cot} onListo={() => setForm(null)} />}

      {porRevisar.length > 0 && (
        <section className="card pg-seccion">
          <h2>Por revisar <span className="pg-conteo">{porRevisar.length}</span></h2>
          <table className="table-sharp">
            <thead><tr><th>Cotización</th><th>Tipo</th><th className="der">Monto</th><th>Referencia</th><th>Registró</th><th /></tr></thead>
            <tbody>
              {porRevisar.map(p => (
                <tr key={p.id}>
                  <td><strong>{p.cotizacion_numero}</strong><span className="pg-sub">{p.cliente_nombre}</span></td>
                  <td><span className="badge" style={{ background: `${ESTADO[p.estado].color}1f`, color: ESTADO[p.estado].color }}>{ESTADO[p.estado].label}</span></td>
                  <td className="der nowrap">{pesos(n(p.monto))}</td>
                  <td>{p.referencia ?? "—"}{p.notas && <span className="pg-sub">{p.notas}</span>}</td>
                  <td className="pg-sub-celda">{p.creado_por_username}<span className="pg-sub">{new Date(p.created_at).toLocaleDateString("es-CO")}</span></td>
                  <td className="pg-acciones-fila">
                    {p.comprobante_path
                      ? <button className="btn-ghost" title="Ver archivo" onClick={() => verArchivo(p)}><Icon name="attach_file" size={16} /></button>
                      : puedeRegistrar && (
                        <label className="btn-ghost" title="Subir archivo" style={{ cursor: "pointer" }}>
                          <Icon name="upload" size={16} />
                          <input type="file" hidden accept=".pdf,.png,.jpg,.jpeg"
                            onChange={e => e.target.files?.[0] && comprobante.mutate({ id: p.id, file: e.target.files[0] })} />
                        </label>
                      )}
                    {puedeAprobar && (p.estado === "pendiente" ? (
                      <>
                        <button className="btn-secondary" onClick={() => decidir.mutate({ p, aprobar: true })}><Icon name="check" size={14} />Aprobar</button>
                        <button className="btn-danger" onClick={() => rechazar(p)}><Icon name="close" size={14} />Rechazar</button>
                      </>
                    ) : (
                      <>
                        <button className="btn-secondary" onClick={() => confirmarOC(p)}><Icon name="paid" size={14} />Confirmar pago</button>
                        <button className="btn-danger" onClick={() => rechazar(p)}><Icon name="block" size={14} />Anular</button>
                      </>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card pg-seccion">
        <div className="pg-seccion-cab">
          <h2>Cotizaciones por cobrar <span className="pg-conteo">{conSaldo.length}</span></h2>
          <div className="pg-leyenda">
            <span><i className="pagado" />Pagado</span><span><i className="oc" />Orden de compra</span><span><i className="revision" />En revisión</span>
          </div>
        </div>
        <table className="table-sharp">
          <thead><tr><th>Cotización</th><th className="der">Total</th><th style={{ width: "28%" }}>Cobro</th><th className="der">Por cobrar</th><th /></tr></thead>
          <tbody>
            {cotizacionesVisibles.map(c => (
              <tr key={c.id}>
                <td><strong>{c.numero}</strong><span className="pg-sub">{c.cliente_nombre}</span></td>
                <td className="der nowrap">{pesos(n(c.total))}</td>
                <td>
                  <BarraCobro c={c} />
                  <span className="pg-sub">
                    {Math.round((n(c.total_pagado) / (n(c.total) || 1)) * 100)}% pagado
                    {n(c.total_por_confirmar) > 0 && ` · OC ${pesos(n(c.total_por_confirmar))}`}
                  </span>
                </td>
                <td className="der nowrap"><strong>{pesos(n(c.saldo_por_cobrar))}</strong>
                  {n(c.saldo_sin_registrar) > 0 && n(c.saldo_sin_registrar) < n(c.saldo_por_cobrar) && (
                    <span className="pg-sub">{pesos(n(c.saldo_sin_registrar))} sin respaldo</span>
                  )}
                </td>
                <td className="pg-acciones-fila">
                  {puedeRegistrar && n(c.saldo_sin_registrar) > 0 && (
                    <button className="btn-secondary" onClick={() => setForm({ cot: c.id })}><Icon name="add" size={14} />Registrar</button>
                  )}
                </td>
              </tr>
            ))}
            {cotizacionesVisibles.length === 0 && <tr><td colSpan={5} className="pg-vacio">No hay cotizaciones con saldo por cobrar.</td></tr>}
          </tbody>
        </table>
        <button className="btn-ghost" style={{ fontSize: 12, marginTop: 6 }} onClick={() => setVerSaldadas(v => !v)}>
          {verSaldadas ? "Ver solo las que tienen saldo" : "Ver también las pagadas"}
        </button>
      </section>

      <section className="card pg-seccion">
        <h2>Historial</h2>
        <table className="table-sharp">
          <thead><tr><th>Fecha</th><th>Cotización</th><th>Tipo</th><th className="der">Monto</th><th>Estado</th><th /></tr></thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="pg-vacio">Cargando…</td></tr>}
            {pagos?.map(p => (
              <tr key={p.id}>
                <td className="nowrap">{new Date(p.fecha_pago ?? p.created_at).toLocaleDateString("es-CO")}</td>
                <td><strong>{p.cotizacion_numero}</strong><span className="pg-sub">{p.cliente_nombre}</span></td>
                <td>{p.tipo === "orden_compra" ? "Orden de compra" : "Pago"}{p.referencia && <span className="pg-sub">{p.referencia}</span>}</td>
                <td className="der nowrap">{pesos(n(p.monto))}</td>
                <td>
                  <span className="badge" style={{ background: `${ESTADO[p.estado].color}1f`, color: ESTADO[p.estado].color }}>{ESTADO[p.estado].label}</span>
                  {p.motivo_rechazo && <span className="pg-sub">{p.motivo_rechazo}</span>}
                </td>
                <td className="pg-acciones-fila">
                  {p.comprobante_path && <button className="btn-ghost" title="Ver archivo" onClick={() => verArchivo(p)}><Icon name="attach_file" size={16} /></button>}
                </td>
              </tr>
            ))}
            {!isLoading && pagos?.length === 0 && <tr><td colSpan={6} className="pg-vacio">Sin pagos registrados.</td></tr>}
          </tbody>
        </table>
      </section>

      {visor && <PdfViewerModal url={visor.url} filename={visor.filename} onClose={() => setVisor(null)} />}

      <style>{`
        .pg-cabecera { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .pg-cabecera h1 { font-size: 18px; font-weight: 700; margin: 0; }
        .pg-seccion { padding: 14px; margin-bottom: 14px; overflow-x: auto; }
        .pg-seccion h2, .pg-form h2 { font-size: 14px; font-weight: 700; margin: 0 0 10px; display: flex; align-items: center; gap: 6px; }
        .pg-seccion-cab { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
        .pg-conteo { font-size: 11px; font-weight: 600; background: var(--bg-surface-2); color: var(--text-muted); padding: 1px 7px; border-radius: 8px; }
        .pg .der { text-align: right; }
        .pg-sub { display: block; font-size: 11px; color: var(--text-muted); font-weight: 400; }
        .pg-sub-celda { font-size: 12px; }
        .pg-acciones-fila { text-align: right; white-space: nowrap; }
        .pg-acciones-fila > * { margin-left: 4px; }
        .pg-vacio { text-align: center; padding: 18px; color: var(--text-muted); }
        .pg-barra { display: flex; height: 8px; background: var(--bg-surface-2); gap: 2px; margin-bottom: 3px; }
        .pg-barra i { display: block; height: 100%; }
        .pg i.pagado { background: #16a34a; } .pg i.oc { background: #7c3aed; } .pg i.revision { background: #d97706; }
        .pg-leyenda { display: flex; gap: 12px; font-size: 11.5px; color: var(--text-secondary); }
        .pg-leyenda span { display: inline-flex; align-items: center; gap: 5px; }
        .pg-leyenda i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; }
        .pg-form { padding: 16px; margin-bottom: 14px; }
        .pg-form-titulo { display: flex; justify-content: space-between; align-items: center; }
        .pg-tipo { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
        @media (max-width: 640px) { .pg-tipo { grid-template-columns: 1fr; } }
        .pg-tipo button {
          display: flex; gap: 10px; align-items: flex-start; text-align: left; padding: 10px 12px; cursor: pointer;
          border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-primary); font: inherit; font-size: 12.5px;
        }
        .pg-tipo button.activo { border-color: var(--accent); background: var(--accent-light); }
        .pg-tipo small { display: block; font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .pg-campos { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
        @media (max-width: 640px) { .pg-campos { grid-template-columns: 1fr; } }
        .pg-campos > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .pg-campos .input-base { width: 100%; font-weight: 400; }
        .pg-ancho { grid-column: 1 / -1; }
        .pg-resumen { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 12px; color: var(--text-secondary); background: var(--bg-surface-2); padding: 8px 12px; }
        .pg-resumen strong { color: var(--text-primary); font-variant-numeric: tabular-nums; }
        .pg-monto { display: flex; gap: 6px; }
        .pg-nota { font-weight: 400; color: var(--text-muted); }
        .pg-error { font-weight: 400; color: #dc2626; }
        .pg-acciones { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
      `}</style>
    </div>
  );
}
