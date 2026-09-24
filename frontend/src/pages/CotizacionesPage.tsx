import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getCotizaciones, aprobarCotizacion } from "../api/cotizaciones";
import { getSolicitudes } from "../api/solicitudes";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { NuevaCotizacion } from "../components/NuevaCotizacion";
import { pesos } from "../lib/cotizacion";
import { MiFirma } from "../components/MiFirma";
import { puede } from "../lib/permisos";
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
  const puedeAprobar = puede(user, "aprobar_cotizaciones");
  const puedeArmar = puede(user, "cotizaciones");
  const { data: cotizaciones, isLoading } = useQuery({ queryKey: ["cotizaciones"], queryFn: () => getCotizaciones() });
  // Sin filtrar por estado: una solicitud rechazada queda "en_seguimiento" y
  // también se puede volver a cotizar. Lo que manda es no tener cotización viva.
  const { data: todasSolicitudes } = useQuery({ queryKey: ["solicitudes"], queryFn: () => getSolicitudes(), enabled: puedeArmar });
  const solicitudes = useMemo(
    () => (todasSolicitudes ?? []).filter(s => !s.tiene_cotizacion && s.estado !== "cerrada"),
    [todasSolicitudes],
  );

  const [pdfViewer, setPdfViewer] = useState<{ url: string; filename: string } | null>(null);

  const [showForm, setShowForm] = useState(false);
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
        {puedeArmar && (
          <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
            <Icon name="add" size={16} />Nueva cotización
          </button>
        )}
      </div>

      {puedeArmar && !user?.firma_path && <MiFirma />}

      {showForm && (
        <NuevaCotizacion
          solicitudes={solicitudes}
          onCreada={() => setShowForm(false)}
          onCancelar={() => setShowForm(false)}
        />
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
                <td className="nowrap">{c.numero}</td>
                <td>{c.cliente_nombre}</td>
                <td>
                  {c.plantas_nombres.length > 1
                    ? <span title={c.plantas_nombres.join(", ")}>{c.plantas_nombres.length} plantas</span>
                    : (c.plantas_nombres[0] ?? c.planta_nombre ?? "-")}
                </td>
                <td className="nowrap num">{pesos(Number(c.subtotal))}</td>
                <td className="nowrap num" title={`IVA ${Number(c.iva_porcentaje)}%`}>
                  {pesos(Number(c.iva))}
                </td>
                <td className="nowrap num" style={{ fontWeight: 600 }}>
                  {pesos(Number(c.total))}
                </td>
                <td>
                  <span className="badge" style={{ background: `${ESTADO_COLOR[c.estado]}22`, color: ESTADO_COLOR[c.estado] }}>
                    {ESTADO_LABEL[c.estado]}
                  </span>
                  {c.items.some(i => i.origen_precio === "manual") && (
                    <span className="badge" title="Tiene precios escritos a mano, fuera de la lista"
                      style={{ background: "#f59e0b22", color: "#b45309", marginLeft: 4 }}>precio manual</span>
                  )}
                  {c.ajustes.some(a => a.tipo === "descuento") && (
                    <span className="badge" title="Tiene descuentos" style={{ background: "#22c55e22", color: "#16a34a", marginLeft: 4 }}>descuento</span>
                  )}
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
