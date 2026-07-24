import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getPagos, createPago, uploadComprobante, aprobarPago } from "../api/pagos";
import { getCotizaciones } from "../api/cotizaciones";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";
import type { PagoEstado } from "../types";

const ESTADO_LABEL: Record<PagoEstado, string> = { pendiente: "Pendiente", aprobado: "Aprobado", rechazado: "Rechazado" };
const ESTADO_COLOR: Record<PagoEstado, string> = { pendiente: "#f59e0b", aprobado: "#16a34a", rechazado: "#dc2626" };

export function PagosPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: pagos, isLoading } = useQuery({ queryKey: ["pagos"], queryFn: () => getPagos() });
  const { data: cotizaciones } = useQuery({ queryKey: ["cotizaciones"], queryFn: () => getCotizaciones("aprobada") });

  const puedeAprobar = user?.is_admin || user?.rol === "financiera";

  const cotizacionesSinPago = useMemo(() => {
    const conPago = new Set((pagos ?? []).map(p => p.cotizacion));
    return (cotizaciones ?? []).filter(c => !conPago.has(c.id));
  }, [cotizaciones, pagos]);

  const [showForm, setShowForm] = useState(false);
  const [cotizacionId, setCotizacionId] = useState("");

  const createMut = useMutation({
    mutationFn: () => createPago({ cotizacion: Number(cotizacionId) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pagos"] });
      toast.success("Pago registrado — pendiente de comprobante y aprobación");
      setShowForm(false);
      setCotizacionId("");
    },
    onError: () => toast.error("No se pudo registrar el pago"),
  });

  const comprobanteMut = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => uploadComprobante(id, file),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pagos"] }); toast.success("Comprobante cargado"); },
    onError: () => toast.error("No se pudo cargar el comprobante"),
  });

  const aprobarMut = useMutation({
    mutationFn: ({ id, aprobar }: { id: number; aprobar: boolean }) => aprobarPago(id, aprobar),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pagos"] }); toast.success("Pago actualizado"); },
    onError: () => toast.error("No se pudo actualizar el pago"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Pagos</h1>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Icon name="add" size={16} />Registrar pago
        </button>
      </div>

      {showForm && (
        <form className="card" style={{ padding: 16, marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <label className="section-label">Cotización aprobada *</label>
          <select className="input-base" style={{ width: "100%", marginBottom: 12 }} value={cotizacionId} onChange={e => setCotizacionId(e.target.value)} required>
            <option value="">Selecciona una cotización</option>
            {cotizacionesSinPago.map(c => (
              <option key={c.id} value={c.id}>{c.numero} — {c.cliente_nombre} — $ {Number(c.total).toLocaleString("es-CO")}</option>
            ))}
          </select>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>Registrar</button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="card">
        <table className="table-sharp">
          <thead>
            <tr>
              <th>Cotización</th>
              <th>Monto</th>
              <th>Comprobante</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {pagos?.map(p => (
              <tr key={p.id}>
                <td>{p.cotizacion_numero}</td>
                <td>$ {Number(p.monto).toLocaleString("es-CO", { minimumFractionDigits: 2 })}</td>
                <td>
                  {p.comprobante_path ? (
                    <span className="badge" style={{ background: "var(--accent-light)", color: "var(--accent-text)" }}>
                      <Icon name="check_circle" size={12} />Cargado
                    </span>
                  ) : (
                    <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--accent-text)" }}>
                      <Icon name="upload_file" size={13} />Cargar comprobante
                      <input type="file" accept=".pdf,.png,.jpg,.jpeg" style={{ display: "none" }}
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (file) comprobanteMut.mutate({ id: p.id, file });
                          e.target.value = "";
                        }}
                      />
                    </label>
                  )}
                </td>
                <td>
                  <span className="badge" style={{ background: `${ESTADO_COLOR[p.estado]}22`, color: ESTADO_COLOR[p.estado] }}>
                    {ESTADO_LABEL[p.estado]}
                  </span>
                </td>
                <td>
                  {puedeAprobar && p.estado === "pendiente" && p.comprobante_path && (
                    <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                      <button className="btn-secondary" onClick={() => aprobarMut.mutate({ id: p.id, aprobar: true })}>
                        <Icon name="check" size={14} />Aprobar
                      </button>
                      <button className="btn-danger" onClick={() => aprobarMut.mutate({ id: p.id, aprobar: false })}>
                        <Icon name="close" size={14} />Rechazar
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {!isLoading && pagos?.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin pagos todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
