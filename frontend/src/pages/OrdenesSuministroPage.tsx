import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getOrdenesSuministro, notificarOrdenSuministro } from "../api/ordenesSuministro";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { TransporteOrden } from "../components/TransporteOrden";

export function OrdenesSuministroPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: ordenes, isLoading } = useQuery({ queryKey: ["ordenes-suministro"], queryFn: () => getOrdenesSuministro() });
  const [pdfViewer, setPdfViewer] = useState<{ url: string; filename: string } | null>(null);

  const esPlanta = user?.is_admin || user?.rol === "planta";
  // Placas y fecha de retiro: las recibe el comercial, la planta las corrige.
  const puedeEditar = esPlanta || user?.rol === "comercial";
  const [abierta, setAbierta] = useState<number | null>(null);

  const notificarMut = useMutation({
    mutationFn: (id: number) => notificarOrdenSuministro(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["ordenes-suministro"] }); toast.success("Planta notificada"); },
    onError: () => toast.error("No se pudo notificar a la planta"),
  });

  return (
    <div>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 14px" }}>Órdenes de Suministro</h1>

      <div className="card">
        <table className="table-sharp">
          <thead>
            <tr>
              <th>N.°</th>
              <th>Cliente</th>
              <th>Planta</th>
              <th>Obra</th>
              <th>Retiro</th>
              <th>Notificación</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {ordenes?.map(o => [
              <tr key={o.id}>
                <td>{o.numero}</td>
                <td>{o.cliente_nombre}</td>
                <td>{o.planta_nombre}</td>
                <td>{o.obra || "-"}</td>
                <td>
                  {o.fecha_suministro
                    ? new Date(o.fecha_suministro + "T00:00:00").toLocaleDateString("es-CO")
                    : "-"}
                  {o.placas_cliente && (
                    <span style={{ display: "block", fontSize: 11, color: "var(--text-muted)" }}>{o.placas_cliente}</span>
                  )}
                </td>
                <td>
                  {o.notificada_planta ? (
                    <span className="badge" style={{ background: "var(--accent-light)", color: "var(--accent-text)" }}>
                      <Icon name="check_circle" size={12} />Notificada
                    </span>
                  ) : (
                    <span className="badge" style={{ background: "#f59e0b22", color: "#f59e0b" }}>Pendiente</span>
                  )}
                </td>
                <td>
                  <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                    <button className="btn-ghost" title="Ver PDF" onClick={() => setPdfViewer({ url: `/ordenes-suministro/${o.id}/pdf/`, filename: `${o.numero}.pdf` })}>
                      <Icon name="picture_as_pdf" size={16} />
                    </button>
                    {puedeEditar && (
                      <button className="btn-secondary" title="Fecha de retiro, placas y observación"
                        onClick={() => setAbierta(abierta === o.id ? null : o.id)}>
                        <Icon name="local_shipping" size={14} />Transporte
                      </button>
                    )}
                    {esPlanta && !o.notificada_planta && (
                      <button className="btn-secondary" onClick={() => notificarMut.mutate(o.id)}>
                        <Icon name="notifications_active" size={14} />Notificar a planta
                      </button>
                    )}
                  </div>
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
            {!isLoading && ordenes?.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin órdenes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {pdfViewer && <PdfViewerModal url={pdfViewer.url} filename={pdfViewer.filename} onClose={() => setPdfViewer(null)} />}
    </div>
  );
}
