import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getOrdenesSuministro, notificarOrdenSuministro } from "../api/ordenesSuministro";
import { downloadAuthed } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";

export function OrdenesSuministroPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: ordenes, isLoading } = useQuery({ queryKey: ["ordenes-suministro"], queryFn: () => getOrdenesSuministro() });

  const esPlanta = user?.is_admin || user?.rol === "planta";

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
              <th>Notificación</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {ordenes?.map(o => (
              <tr key={o.id}>
                <td>{o.numero}</td>
                <td>{o.cliente_nombre}</td>
                <td>{o.planta_nombre}</td>
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
                    <button className="btn-ghost" title="Descargar PDF" onClick={() => downloadAuthed(`/ordenes-suministro/${o.id}/pdf/`, `${o.numero}.pdf`)}>
                      <Icon name="picture_as_pdf" size={16} />
                    </button>
                    {esPlanta && !o.notificada_planta && (
                      <button className="btn-secondary" onClick={() => notificarMut.mutate(o.id)}>
                        <Icon name="notifications_active" size={14} />Notificar a planta
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!isLoading && ordenes?.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin órdenes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
