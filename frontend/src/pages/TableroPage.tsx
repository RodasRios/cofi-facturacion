import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "../components/ui/Icon";
import { getTablero, getSeguimientos, crearNota } from "../api/tablero";
import { ResumenTablero } from "../components/ResumenTablero";
import { getCartera } from "../api/pagos";
import type { EtapaFlujo, FilaCartera, FilaTablero, Rol, SeguimientoTipo } from "../types";

// Las etapas en el orden del flujo, con el color que las identifica.
const ETAPA_COLOR: Record<EtapaFlujo, { bg: string; color: string }> = {
  pendiente_cotizacion:      { bg: "#94a3b822", color: "#64748b" },
  en_seguimiento:            { bg: "#f9731622", color: "#f97316" },
  pendiente_aprobacion:      { bg: "#f59e0b22", color: "#f59e0b" },
  pendiente_pago:            { bg: "#8b5cf622", color: "#8b5cf6" },
  pendiente_aprobacion_pago: { bg: "#3b82f622", color: "#3b82f6" },
  pendiente_orden:           { bg: "#6366f122", color: "#6366f1" },
  pendiente_notificacion:    { bg: "#06b6d422", color: "#0891b2" },
  pendiente_despacho:        { bg: "#14b8a622", color: "#0d9488" },
  despachada:                { bg: "#22c55e22", color: "#16a34a" },
};

const ETAPA_ORDEN: EtapaFlujo[] = [
  "pendiente_cotizacion", "en_seguimiento", "pendiente_aprobacion", "pendiente_pago",
  "pendiente_aprobacion_pago", "pendiente_orden", "pendiente_notificacion", "pendiente_despacho", "despachada",
];

const ROL_LABEL: Record<Rol, string> = {
  comercial: "Comercial", aprobador: "Aprobador", financiera: "Financiera", planta: "Planta",
};

const ICONO_SEGUIMIENTO: Record<SeguimientoTipo, string> = {
  nota: "chat",
  cotizacion_rechazada: "cancel",
  cotizacion_aprobada: "check_circle",
  pago_rechazado: "cancel",
  pago_aprobado: "check_circle",
  cotizacion_nueva: "refresh",
};

function moneda(v: string | null) {
  if (!v) return "-";
  return new Intl.NumberFormat("es-CO", {
    style: "currency", currency: "COP", maximumFractionDigits: 0,
  }).format(Number(v));
}

function tiempoEnEtapa(dias: number) {
  if (dias === 0) return "hoy";
  if (dias === 1) return "1 día";
  return `${dias} días`;
}

/** Bitácora de una solicitud, con caja para agregar notas. */
function Bitacora({ solicitudId }: { solicitudId: number }) {
  const qc = useQueryClient();
  const [texto, setTexto] = useState("");

  const { data: seguimientos, isLoading } = useQuery({
    queryKey: ["seguimientos", solicitudId],
    queryFn: () => getSeguimientos(solicitudId),
  });

  const agregar = useMutation({
    mutationFn: () => crearNota(solicitudId, texto.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["seguimientos", solicitudId] });
      setTexto("");
      toast.success("Nota agregada");
    },
    onError: () => toast.error("No se pudo agregar la nota"),
  });

  return (
    <div className="bitacora">
      <form
        className="bitacora-form"
        onSubmit={(e) => { e.preventDefault(); if (texto.trim()) agregar.mutate(); }}
      >
        <input
          className="input-base"
          placeholder="Anotar lo que se habló con el cliente…"
          value={texto}
          onChange={e => setTexto(e.target.value)}
        />
        <button type="submit" className="btn-secondary" disabled={!texto.trim() || agregar.isPending}>
          <Icon name="add_comment" size={14} />Anotar
        </button>
      </form>

      {isLoading && <p className="bitacora-vacia">Cargando…</p>}
      {!isLoading && seguimientos?.length === 0 && (
        <p className="bitacora-vacia">Sin movimientos registrados todavía.</p>
      )}

      <ul className="bitacora-lista">
        {seguimientos?.map(s => (
          <li key={s.id}>
            <Icon name={ICONO_SEGUIMIENTO[s.tipo] ?? "chat"} size={15} />
            <div>
              <span className="bitacora-texto">{s.texto || s.tipo_display}</span>
              <span className="bitacora-meta">
                {s.usuario_username || "sistema"} · {new Date(s.created_at).toLocaleString("es-CO", {
                  day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Estado de cobro de la solicitud: pagado, respaldado por orden de compra, saldo. */
function Cobro({ f }: { f: FilaTablero }) {
  if (f.saldo_por_cobrar == null) return <span className="tb-tenue">—</span>;
  const total = Number(f.total) || 1;
  const pagado = Number(f.pagado ?? 0);
  const oc = Number(f.por_confirmar ?? 0);
  const saldo = Number(f.saldo_por_cobrar);
  if (saldo <= 0) return <span className="badge" style={{ background: "#16a34a1f", color: "#16a34a" }}>Pagada</span>;
  return (
    <span className="tb-cobro" title={`Pagado ${moneda(String(pagado))} · Orden de compra ${moneda(String(oc))} · Saldo ${moneda(String(saldo))}`}>
      <span className="tb-barra"><i className="pagado" style={{ width: `${(pagado / total) * 100}%` }} /><i className="oc" style={{ width: `${(oc / total) * 100}%` }} /></span>
      <span className="tb-tenue">{Math.round((pagado / total) * 100)}% pagado{oc > 0 && " · con OC"}</span>
    </span>
  );
}

/** Lo que falta por cobrar, con lo respaldado por orden de compra aparte. */
function Cartera() {
  const { data: filas } = useQuery({ queryKey: ["cartera"], queryFn: getCartera });
  if (!filas?.length) return null;
  const suma = (k: keyof FilaCartera) => filas.reduce((t, f) => t + Number(f[k] ?? 0), 0);
  return (
    <section className="card tb-cartera">
      <div className="tb-cartera-cab">
        <h2>Cartera por cobrar</h2>
        <span>Por cobrar <strong>{moneda(String(suma("saldo_por_cobrar")))}</strong></span>
        <span>Con orden de compra <strong style={{ color: "#7c3aed" }}>{moneda(String(suma("por_confirmar")))}</strong></span>
        <span>Sin respaldo <strong style={{ color: "#dc2626" }}>{moneda(String(suma("sin_respaldo")))}</strong></span>
      </div>
      <table className="table-sharp">
        <thead><tr><th>Cotización</th><th style={{ textAlign: "right" }}>Total</th><th style={{ textAlign: "right" }}>Pagado</th>
          <th style={{ textAlign: "right" }}>En revisión</th><th style={{ textAlign: "right" }}>Orden de compra</th>
          <th style={{ textAlign: "right" }}>Sin respaldo</th><th style={{ textAlign: "right" }}>Por cobrar</th></tr></thead>
        <tbody>
          {filas.map(f => (
            <tr key={f.cotizacion_id}>
              <td><strong>{f.cotizacion_numero}</strong><span className="tb-tenue" style={{ display: "block" }}>{f.cliente_nombre}</span></td>
              <td className="tb-num">{moneda(f.total)}</td>
              <td className="tb-num">{moneda(f.pagado)}</td>
              <td className="tb-num">{Number(f.en_revision) ? moneda(f.en_revision) : "—"}</td>
              <td className="tb-num" style={Number(f.por_confirmar) ? { color: "#7c3aed", fontWeight: 600 } : undefined}>{Number(f.por_confirmar) ? moneda(f.por_confirmar) : "—"}</td>
              <td className="tb-num" style={Number(f.sin_respaldo) ? { color: "#dc2626" } : undefined}>{Number(f.sin_respaldo) ? moneda(f.sin_respaldo) : "—"}</td>
              <td className="tb-num"><strong>{moneda(f.saldo_por_cobrar)}</strong></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function TableroPage() {
  const [filtro, setFiltro] = useState<EtapaFlujo | "todas">("todas");
  const [abierta, setAbierta] = useState<number | null>(null);

  const { data: filas, isLoading } = useQuery({ queryKey: ["tablero"], queryFn: getTablero });

  const conteos = (filas ?? []).reduce<Record<string, number>>((acc, f) => {
    acc[f.etapa] = (acc[f.etapa] ?? 0) + 1;
    return acc;
  }, {});

  const visibles = filtro === "todas" ? filas : filas?.filter(f => f.etapa === filtro);
  const atascadas = (filas ?? []).filter(f => f.etapa !== "despachada" && f.dias_en_etapa >= 3).length;

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 12px" }}>Tablero</h1>
      </div>

      <ResumenTablero />
      <Cartera />

      <div style={{ marginBottom: 14 }}>
        <h2 style={{ fontSize: 15, fontWeight: 700, margin: 0 }}>Seguimiento de solicitudes</h2>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "3px 0 0" }}>
          En qué etapa del flujo va cada solicitud y quién tiene la pelota.
          {atascadas > 0 && <> <strong>{atascadas}</strong> llevan 3 días o más sin moverse.</>}
        </p>
      </div>

      <div className="etapa-chips">
        <button
          className={`etapa-chip ${filtro === "todas" ? "activo" : ""}`}
          onClick={() => setFiltro("todas")}
        >
          Todas <span className="etapa-chip-n">{filas?.length ?? 0}</span>
        </button>
        {ETAPA_ORDEN.filter(e => conteos[e]).map(e => {
          const c = ETAPA_COLOR[e];
          const titulo = filas?.find(f => f.etapa === e)?.etapa_titulo ?? e;
          return (
            <button
              key={e}
              className={`etapa-chip ${filtro === e ? "activo" : ""}`}
              style={filtro === e ? { background: c.bg, color: c.color, borderColor: c.color } : undefined}
              onClick={() => setFiltro(e)}
            >
              {titulo} <span className="etapa-chip-n">{conteos[e]}</span>
            </button>
          );
        })}
      </div>

      <div className="card">
        <table className="table-sharp">
          <thead>
            <tr>
              <th>Solicitud</th>
              <th>Cliente</th>
              <th>Etapa actual</th>
              <th>Responsable</th>
              <th>Lleva</th>
              <th>Cotización</th>
              <th style={{ textAlign: "right" }}>Total</th>
              <th>Cobro</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={9} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {visibles?.map((f: FilaTablero) => {
              const c = ETAPA_COLOR[f.etapa];
              const lento = f.etapa !== "despachada" && f.dias_en_etapa >= 3;
              const reintentos = f.cotizaciones_rechazadas + f.pagos_rechazados;
              return [
                <tr key={f.solicitud_id}>
                  <td style={{ fontWeight: 600 }}>{f.numero}</td>
                  <td>{f.cliente_nombre}</td>
                  <td>
                    <span className="badge" style={{ background: c.bg, color: c.color }}>{f.etapa_titulo}</span>
                    {reintentos > 0 && (
                      <span className="badge reintento" title="Rechazos previos en esta solicitud">
                        <Icon name="refresh" size={11} />{reintentos}
                      </span>
                    )}
                  </td>
                  <td>{f.responsable ? ROL_LABEL[f.responsable] : "-"}</td>
                  <td style={lento ? { color: "#ef4444", fontWeight: 600 } : undefined}>
                    {f.etapa === "despachada" ? "-" : tiempoEnEtapa(f.dias_en_etapa)}
                  </td>
                  <td>{f.cotizacion_numero ?? "-"}</td>
                  <td style={{ textAlign: "right" }}>{moneda(f.total)}</td>
                  <td><Cobro f={f} /></td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn-ghost"
                      title="Ver bitácora"
                      onClick={() => setAbierta(abierta === f.solicitud_id ? null : f.solicitud_id)}
                    >
                      <Icon name={abierta === f.solicitud_id ? "expand_less" : "expand_more"} size={16} />
                    </button>
                  </td>
                </tr>,
                abierta === f.solicitud_id && (
                  <tr key={`${f.solicitud_id}-bitacora`} className="fila-bitacora">
                    <td colSpan={9}><Bitacora solicitudId={f.solicitud_id} /></td>
                  </tr>
                ),
              ];
            })}
            {!isLoading && visibles?.length === 0 && (
              <tr><td colSpan={9} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>
                Nada en esta etapa
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      <style>{`
        .tb-tenue { font-size: 11px; color: var(--text-muted); }
        .tb-num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
        .tb-cobro { display: flex; flex-direction: column; gap: 2px; min-width: 110px; }
        .tb-barra { display: flex; height: 6px; background: var(--bg-surface-2); gap: 2px; }
        .tb-barra i { display: block; height: 100%; }
        .tb-barra i.pagado { background: #16a34a; } .tb-barra i.oc { background: #7c3aed; }
        .tb-cartera { padding: 14px; margin-bottom: 18px; overflow-x: auto; }
        .tb-cartera-cab { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; margin-bottom: 10px; font-size: 12px; color: var(--text-secondary); }
        .tb-cartera-cab h2 { font-size: 13px; font-weight: 700; margin: 0; color: var(--text-primary); margin-right: auto; }
        .etapa-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
        .etapa-chip {
          background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-secondary);
          font-size: 12px; padding: 5px 10px; cursor: pointer; display: flex; align-items: center; gap: 6px;
          transition: background 0.15s, color 0.15s;
        }
        .etapa-chip:hover { background: var(--bg-surface-2); color: var(--text-primary); }
        .etapa-chip.activo { border-color: var(--text-primary); color: var(--text-primary); font-weight: 600; }
        .etapa-chip-n { font-size: 11px; opacity: 0.7; }
        .badge.reintento { background: #f9731622; color: #f97316; margin-left: 5px; }
        .fila-bitacora > td { background: var(--bg-surface-2); padding: 0; }
        .bitacora { padding: 12px 14px; }
        .bitacora-form { display: flex; gap: 8px; margin-bottom: 10px; }
        .bitacora-form .input-base { flex: 1; }
        .bitacora-vacia { font-size: 12px; color: var(--text-muted); margin: 0; }
        .bitacora-lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
        .bitacora-lista li { display: flex; gap: 8px; align-items: flex-start; font-size: 12.5px; }
        .bitacora-texto { display: block; color: var(--text-primary); }
        .bitacora-meta { display: block; font-size: 11px; color: var(--text-muted); margin-top: 1px; }
      `}</style>
    </div>
  );
}
