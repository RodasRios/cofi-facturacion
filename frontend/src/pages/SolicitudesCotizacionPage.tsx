import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getSolicitudes, createSolicitud } from "../api/solicitudes";
import { getClientes } from "../api/clientes";
import { getMateriales } from "../api/materiales";
import { Icon } from "../components/ui/Icon";
import type { SolicitudEstado } from "../types";

const ESTADO_LABEL: Record<SolicitudEstado, string> = {
  pendiente: "Pendiente",
  cotizada: "Cotizada",
  cerrada: "Cerrada",
};

const ESTADO_COLOR: Record<SolicitudEstado, string> = {
  pendiente: "#f59e0b",
  cotizada: "#0f6cbd",
  cerrada: "#64748b",
};

interface ItemRow { material: string; cantidad: string }

export function SolicitudesCotizacionPage() {
  const qc = useQueryClient();
  const { data: solicitudes, isLoading } = useQuery({ queryKey: ["solicitudes"], queryFn: () => getSolicitudes() });
  const { data: clientes } = useQuery({ queryKey: ["clientes"], queryFn: () => getClientes() });
  const { data: materiales } = useQuery({ queryKey: ["materiales"], queryFn: getMateriales });

  const [showForm, setShowForm] = useState(false);
  const [clienteId, setClienteId] = useState("");
  const [notas, setNotas] = useState("");
  const [items, setItems] = useState<ItemRow[]>([{ material: "", cantidad: "" }]);

  const createMut = useMutation({
    mutationFn: () => createSolicitud({
      cliente: Number(clienteId),
      notas,
      items: items.filter(i => i.material && i.cantidad).map(i => ({ material: Number(i.material), cantidad: Number(i.cantidad) })),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      toast.success("Solicitud de cotización creada");
      setShowForm(false);
      setClienteId(""); setNotas(""); setItems([{ material: "", cantidad: "" }]);
    },
    onError: () => toast.error("No se pudo crear la solicitud"),
  });

  const updateItem = (idx: number, field: keyof ItemRow, value: string) => {
    setItems(rows => rows.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Solicitudes de Cotización</h1>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Icon name="add" size={16} />Nueva solicitud
        </button>
      </div>

      {showForm && (
        <form className="card" style={{ padding: 16, marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label className="section-label">Cliente *</label>
              <select className="input-base" style={{ width: "100%" }} value={clienteId} onChange={e => setClienteId(e.target.value)} required>
                <option value="">Selecciona un cliente</option>
                {clientes?.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="section-label">Notas</label>
              <input className="input-base" style={{ width: "100%" }} value={notas} onChange={e => setNotas(e.target.value)} />
            </div>
          </div>

          <label className="section-label">Materiales</label>
          {items.map((row, idx) => (
            <div key={idx} style={{ display: "flex", gap: 8, marginBottom: 6 }}>
              <select className="input-base" style={{ flex: 2 }} value={row.material} onChange={e => updateItem(idx, "material", e.target.value)}>
                <option value="">Material</option>
                {materiales?.map(m => <option key={m.id} value={m.id}>{m.nombre} ({m.unidad_medida})</option>)}
              </select>
              <input className="input-base" style={{ flex: 1 }} type="number" min="0" step="0.01" placeholder="Cantidad"
                value={row.cantidad} onChange={e => updateItem(idx, "cantidad", e.target.value)} />
              <button type="button" className="btn-danger" onClick={() => setItems(rows => rows.filter((_, i) => i !== idx))}>
                <Icon name="close" size={14} />
              </button>
            </div>
          ))}
          <button type="button" className="btn-ghost" style={{ marginBottom: 12 }} onClick={() => setItems(rows => [...rows, { material: "", cantidad: "" }])}>
            <Icon name="add" size={14} />Agregar material
          </button>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>Guardar</button>
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
              <th>Materiales</th>
              <th>Estado</th>
              <th>Creado por</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {solicitudes?.map(s => (
              <tr key={s.id}>
                <td>{s.numero}</td>
                <td>{s.cliente_nombre}</td>
                <td>{s.items.map(i => `${i.material_nombre} (${i.cantidad} ${i.unidad_medida})`).join(", ")}</td>
                <td>
                  <span className="badge" style={{ background: `${ESTADO_COLOR[s.estado]}22`, color: ESTADO_COLOR[s.estado] }}>
                    {ESTADO_LABEL[s.estado]}
                  </span>
                </td>
                <td>{s.creado_por_username || "-"}</td>
              </tr>
            ))}
            {!isLoading && solicitudes?.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin solicitudes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
