import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getOrdenesSuministro, getPorOrdenar, anularOrdenSuministro } from "../api/ordenesSuministro";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { TransporteOrden } from "../components/TransporteOrden";
import { NuevaOrden } from "../components/NuevaOrden";
import { NotificarPlanta } from "../components/NotificarPlanta";
import { pesos } from "../lib/cotizacion";
import { mensajeError } from "../lib/errores";
import type { OrdenSuministro } from "../types";

const n = (v: string | number | null | undefined) => Number(v ?? 0);
const cant = (v: number) => v.toLocaleString("es-CO", { maximumFractionDigits: 2 });
const CANAL: Record<string, string> = { whatsapp: "WhatsApp", email: "correo", manual: "otro medio" };

function Despachado({ o }: { o: OrdenSuministro }) {
  return (
    <div className="os-items">
      {o.items.map(i => {
        const pct = Math.min(100, (n(i.cantidad_despachada) / (n(i.cantidad) || 1)) * 100);
        return (
          <div key={i.id} title={`Despachado ${cant(n(i.cantidad_despachada))} de ${cant(n(i.cantidad))} ${i.unidad_medida}`}>
            <span>{i.material_nombre} · <strong>{cant(n(i.cantidad))} {i.unidad_medida}</strong></span>
            <span className="os-pista"><i style={{ width: `${pct}%` }} /></span>
          </div>
        );
      })}
    </div>
  );
}

export function OrdenesSuministroPage() {
  const qc = useQueryClient();
  const { data: ordenes, isLoading } = useQuery({ queryKey: ["ordenes-suministro"], queryFn: () => getOrdenesSuministro() });
  const { data: porOrdenar } = useQuery({ queryKey: ["por-ordenar"], queryFn: getPorOrdenar });
  const [pdfViewer, setPdfViewer] = useState<{ url: string; filename: string } | null>(null);
  const [form, setForm] = useState<{ cot: number | null } | null>(null);
  const [recien, setRecien] = useState<OrdenSuministro | null>(null);
  const [abierta, setAbierta] = useState<number | null>(null);

  const anular = useMutation({
    mutationFn: (o: OrdenSuministro) => anularOrdenSuministro(o.id),
    onSuccess: () => {
      ["ordenes-suministro", "por-ordenar", "tablero"].forEach(k => qc.invalidateQueries({ queryKey: [k] }));
      toast.success("Orden anulada");
    },
    onError: e => toast.error(mensajeError(e, "No se pudo anular")),
  });

  // La recién emitida, con los datos al día (p. ej. ya notificada).
  const recienActual = recien ? ordenes?.find(o => o.id === recien.id) ?? recien : null;

  return (
    <div className="os">
      <div className="os-cabecera">
        <h1>Órdenes de suministro</h1>
        {!form && (
          <button className="btn-primary" onClick={() => { setRecien(null); setForm({ cot: null }); }} disabled={!porOrdenar?.length}>
            <Icon name="add" size={16} />Nueva orden
          </button>
        )}
      </div>

      {form && porOrdenar && (
        <NuevaOrden key={form.cot ?? "nueva"} cotizaciones={porOrdenar} inicial={form.cot}
          onCreada={o => { setForm(null); setRecien(o); }} onCancelar={() => setForm(null)} />
      )}

      {recienActual && (
        <div className="card os-recien">
          <Icon name="check_circle" size={20} />
          <div>
            <strong>Orden {recienActual.numero} emitida para {recienActual.planta_nombre}.</strong>
            <span>{recienActual.notificada_planta ? "Planta notificada." : "Avísale a la planta:"}</span>
          </div>
          <NotificarPlanta orden={recienActual} />
          <button className="btn-ghost" onClick={() => setRecien(null)}><Icon name="close" size={16} /></button>
        </div>
      )}

      {(porOrdenar?.length ?? 0) > 0 && !form && (
        <section className="card os-seccion">
          <h2>Listas para ordenar <span className="os-conteo">{porOrdenar!.length}</span></h2>
          <p className="os-ayuda">Cotizaciones aprobadas con pago u orden de compra que aún tienen material sin ordenar.</p>
          <table className="table-sharp">
            <thead><tr><th>Cotización</th><th>Obra</th><th>Respaldo</th><th>Ordenado</th><th /></tr></thead>
            <tbody>
              {porOrdenar!.map(c => (
                <tr key={c.id}>
                  <td><strong>{c.numero}</strong><span className="os-sub">{c.cliente_nombre}</span></td>
                  <td>{c.obra || "—"}</td>
                  <td className="os-sub-celda">
                    {pesos(n(c.total_pagado))} pagado
                    {n(c.total_por_confirmar) > 0 && <span className="os-sub">+ {pesos(n(c.total_por_confirmar))} en orden de compra</span>}
                  </td>
                  <td>
                    <span className="os-pista ancha"><i style={{ width: `${c.porcentaje_ordenado}%` }} /></span>
                    <span className="os-sub">{c.porcentaje_ordenado}%</span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn-secondary" onClick={() => { setRecien(null); setForm({ cot: c.id }); }}>
                      <Icon name="add" size={14} />Emitir orden
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="card os-seccion">
        <h2>Órdenes emitidas</h2>
        <table className="table-sharp">
          <thead>
            <tr><th>N.°</th><th>Cliente / obra</th><th>Planta</th><th>Material (despachado)</th><th>Retiro</th><th>Aviso a planta</th><th /></tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="os-vacio">Cargando…</td></tr>}
            {ordenes?.map(o => [
              <tr key={o.id}>
                <td className="nowrap"><strong>{o.numero}</strong><span className="os-sub">{o.cotizacion_numero}</span></td>
                <td>{o.cliente_nombre}<span className="os-sub">{o.obra || "—"}</span></td>
                <td>{o.planta_nombre.replace("Planta ", "")}</td>
                <td><Despachado o={o} /></td>
                <td className="os-sub-celda">
                  {o.fecha_suministro ? new Date(o.fecha_suministro + "T00:00:00").toLocaleDateString("es-CO") : "Sin fecha"}
                  {(o.placas_cliente || o.placas_empresa) && (
                    <span className="os-sub">{[o.placas_cliente, o.placas_empresa].filter(Boolean).join(", ")}</span>
                  )}
                </td>
                <td>
                  {o.notificada_planta ? (
                    <span className="os-sub-celda">
                      <span className="badge" style={{ background: "#16a34a1f", color: "#16a34a" }}>Avisada</span>
                      <span className="os-sub">por {o.canales_notificacion.map(c => CANAL[c]).join(" y ")}
                        {o.fecha_notificacion && ` · ${new Date(o.fecha_notificacion).toLocaleDateString("es-CO")}`}</span>
                    </span>
                  ) : <NotificarPlanta orden={o} compacto />}
                </td>
                <td className="os-acciones">
                  {o.notificada_planta && <NotificarPlanta orden={o} compacto />}
                  <button className="btn-ghost" title="Ver PDF"
                    onClick={() => setPdfViewer({ url: `/ordenes-suministro/${o.id}/pdf/`, filename: `${o.numero}.pdf` })}>
                    <Icon name="picture_as_pdf" size={16} />
                  </button>
                  <button className="btn-ghost" title="Fecha de retiro, placas y observación"
                    onClick={() => setAbierta(abierta === o.id ? null : o.id)}>
                    <Icon name="edit" size={16} />
                  </button>
                  {o.items.every(i => n(i.cantidad_despachada) === 0) && (
                    <button className="btn-ghost" title="Anular orden" style={{ color: "#dc2626" }}
                      onClick={() => confirm(`¿Anular la orden ${o.numero}? El material vuelve a quedar por ordenar.`) && anular.mutate(o)}>
                      <Icon name="delete" size={16} />
                    </button>
                  )}
                </td>
              </tr>,
              abierta === o.id && (
                <tr key={`${o.id}-transporte`}>
                  <td colSpan={7} style={{ background: "var(--bg-surface-2)", padding: 0 }}>
                    <TransporteOrden orden={o} onGuardado={() => setAbierta(null)} />
                  </td>
                </tr>
              ),
            ])}
            {!isLoading && ordenes?.length === 0 && <tr><td colSpan={7} className="os-vacio">Sin órdenes todavía</td></tr>}
          </tbody>
        </table>
      </section>

      {pdfViewer && <PdfViewerModal url={pdfViewer.url} filename={pdfViewer.filename} onClose={() => setPdfViewer(null)} />}

      <style>{`
        .os-cabecera { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; gap: 10px; flex-wrap: wrap; }
        .os-cabecera h1 { font-size: 18px; font-weight: 700; margin: 0; }
        .os-seccion { padding: 14px; margin-bottom: 14px; overflow-x: auto; }
        .os-seccion h2 { font-size: 14px; font-weight: 700; margin: 0 0 4px; display: flex; gap: 6px; align-items: center; }
        .os-ayuda { font-size: 12px; color: var(--text-muted); margin: 0 0 10px; }
        .os-conteo { font-size: 11px; background: var(--bg-surface-2); color: var(--text-muted); padding: 1px 7px; border-radius: 8px; }
        .os-sub { display: block; font-size: 11px; color: var(--text-muted); }
        .os-sub-celda { font-size: 12px; }
        .os-vacio { text-align: center; padding: 18px; color: var(--text-muted); }
        .os-items { display: flex; flex-direction: column; gap: 5px; font-size: 12px; min-width: 180px; }
        .os-pista { display: block; height: 5px; background: var(--bg-surface-2); margin-top: 2px; }
        .os-pista.ancha { width: 120px; height: 7px; }
        .os-pista i { display: block; height: 100%; background: var(--accent); }
        .os-acciones { text-align: right; white-space: nowrap; }
        .os-acciones > * { margin-left: 2px; vertical-align: middle; }
        .os-recien { display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin-bottom: 14px;
          border-color: #16a34a; background: #f0fdf4; color: #14532d; flex-wrap: wrap; }
        .dark .os-recien { background: #052e16; color: #bbf7d0; }
        .os-recien > div:first-of-type { flex: 1; display: flex; flex-direction: column; font-size: 13px; min-width: 200px; }
        .os-recien span { font-size: 12px; }
      `}</style>
    </div>
  );
}
