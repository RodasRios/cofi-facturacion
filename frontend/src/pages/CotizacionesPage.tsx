import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getCotizaciones, createCotizacion, aprobarCotizacion } from "../api/cotizaciones";
import { getSolicitudes } from "../api/solicitudes";
import { getPlantas } from "../api/plantas";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { RepartoPlantas } from "../components/RepartoPlantas";
import { MiFirma } from "../components/MiFirma";
import { repartoInicial, repartoValido, repartoAItems, type Reparto } from "../lib/reparto";
import type { CotizacionEstado } from "../types";

const ESTADO_LABEL: Record<CotizacionEstado, string> = {
  pendiente_aprobacion: "Pendiente de aprobación",
  aprobada: "Aprobada",
  rechazada: "Rechazada",
};
const ESTADO_COLOR: Record<CotizacionEstado, string> = {
  pendiente_aprobacion: "#f59e0b",
  aprobada: "#16a34a",
  rechazada: "#dc2626",
};

export function CotizacionesPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: cotizaciones, isLoading } = useQuery({ queryKey: ["cotizaciones"], queryFn: () => getCotizaciones() });
  // Sin filtrar por estado: una solicitud rechazada queda "en_seguimiento" y
  // también se puede volver a cotizar. Lo que manda es no tener cotización viva.
  const { data: todasSolicitudes } = useQuery({ queryKey: ["solicitudes"], queryFn: () => getSolicitudes() });
  const solicitudes = useMemo(
    () => (todasSolicitudes ?? []).filter(s => !s.tiene_cotizacion && s.estado !== "cerrada"),
    [todasSolicitudes],
  );
  const { data: plantas } = useQuery({ queryKey: ["plantas"], queryFn: () => getPlantas() });

  const puedeAprobar = user?.is_admin || user?.rol === "aprobador";
  const [pdfViewer, setPdfViewer] = useState<{ url: string; filename: string } | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [solicitudId, setSolicitudId] = useState("");
  const [plantaId, setPlantaId] = useState("");
  const [notas, setNotas] = useState("");

  const solicitudSel = useMemo(() => solicitudes.find(s => String(s.id) === solicitudId), [solicitudes, solicitudId]);

  // Reparto de cada material entre plantas. Arranca con todo en la planta
  // principal; el comercial lo parte si hace falta.
  const [reparto, setReparto] = useState<Reparto>({});
  const [repartoBase, setRepartoBase] = useState("");
  const baseActual = `${solicitudId}|${plantaId}`;
  if (baseActual !== repartoBase) {
    setRepartoBase(baseActual);
    setReparto(solicitudSel ? repartoInicial(solicitudSel.items, plantaId) : {});
  }

  const repartoOk = !!solicitudSel && repartoValido(solicitudSel.items, reparto);

  const createMut = useMutation({
    mutationFn: () => createCotizacion({
      solicitud: Number(solicitudId), planta: Number(plantaId), notas,
      items: repartoAItems(reparto),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cotizaciones"] });
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success("Cotización generada");
      setShowForm(false);
      setSolicitudId(""); setPlantaId(""); setNotas("");
    },
    onError: () => toast.error("No se pudo generar la cotización"),
  });

  const aprobarMut = useMutation({
    mutationFn: ({ id, aprobar }: { id: number; aprobar: boolean }) => aprobarCotizacion(id, aprobar),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cotizaciones"] });
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success("Cotización actualizada");
    },
    onError: () => toast.error("No se pudo actualizar la cotización"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Cotizaciones</h1>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Icon name="add" size={16} />Nueva cotización
        </button>
      </div>

      {(user?.is_admin || user?.rol === "comercial") && !user?.firma_path && <MiFirma />}

      {showForm && (
        <form className="card" style={{ padding: 16, marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label className="section-label">Solicitud pendiente *</label>
              <select className="input-base" style={{ width: "100%" }} value={solicitudId} onChange={e => setSolicitudId(e.target.value)} required>
                <option value="">Selecciona una solicitud</option>
                {solicitudes.map(s => <option key={s.id} value={s.id}>{s.numero} — {s.cliente_nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="section-label">Planta principal *</label>
              <select className="input-base" style={{ width: "100%" }} value={plantaId} onChange={e => setPlantaId(e.target.value)} required>
                <option value="">Selecciona una planta</option>
                {plantas?.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
              </select>
            </div>
          </div>

          {solicitudSel && plantaId && (
            <RepartoPlantas
              items={solicitudSel.items}
              plantas={plantas ?? []}
              reparto={reparto}
              onChange={setReparto}
            />
          )}
          {solicitudSel && !plantaId && (
            <div style={{ marginBottom: 12, fontSize: 12, color: "var(--text-muted)" }}>
              Elige la planta principal para repartir los materiales.
            </div>
          )}

          <div style={{ marginBottom: 12 }}>
            <label className="section-label">Notas</label>
            <input className="input-base" style={{ width: "100%" }} value={notas} onChange={e => setNotas(e.target.value)} />
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn-primary" disabled={createMut.isPending || !repartoOk}>Generar</button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="card">
        <table className="table-sharp">
          <thead>
            <tr>
              <th>N.°</th>
              <th>Cliente</th>
              <th>Planta</th>
              <th>Subtotal</th>
              <th>IVA</th>
              <th>Total</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={8} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {cotizaciones?.map(c => (
              <tr key={c.id}>
                <td>{c.numero}</td>
                <td>{c.cliente_nombre}</td>
                <td>
                  {c.plantas_nombres.length > 1
                    ? <span title={c.plantas_nombres.join(", ")}>{c.plantas_nombres.length} plantas</span>
                    : (c.plantas_nombres[0] ?? c.planta_nombre ?? "-")}
                </td>
                <td>$ {Number(c.subtotal).toLocaleString("es-CO", { minimumFractionDigits: 2 })}</td>
                <td title={`IVA ${Number(c.iva_porcentaje)}%`}>
                  $ {Number(c.iva).toLocaleString("es-CO", { minimumFractionDigits: 2 })}
                </td>
                <td style={{ fontWeight: 600 }}>
                  $ {Number(c.total).toLocaleString("es-CO", { minimumFractionDigits: 2 })}
                </td>
                <td>
                  <span className="badge" style={{ background: `${ESTADO_COLOR[c.estado]}22`, color: ESTADO_COLOR[c.estado] }}>
                    {ESTADO_LABEL[c.estado]}
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                    {c.pdf_path && (
                      <button className="btn-ghost" title="Ver PDF" onClick={() => setPdfViewer({ url: `/cotizaciones/${c.id}/pdf/`, filename: `${c.numero}.pdf` })}>
                        <Icon name="picture_as_pdf" size={16} />
                      </button>
                    )}
                    {puedeAprobar && c.estado === "pendiente_aprobacion" && (
                      <>
                        <button className="btn-secondary" onClick={() => aprobarMut.mutate({ id: c.id, aprobar: true })}>
                          <Icon name="check" size={14} />Aprobar
                        </button>
                        <button className="btn-danger" onClick={() => aprobarMut.mutate({ id: c.id, aprobar: false })}>
                          <Icon name="close" size={14} />Rechazar
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!isLoading && cotizaciones?.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin cotizaciones todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {pdfViewer && <PdfViewerModal url={pdfViewer.url} filename={pdfViewer.filename} onClose={() => setPdfViewer(null)} />}
    </div>
  );
}
