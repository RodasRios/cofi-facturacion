import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getSolicitudes, createSolicitud, actualizarSolicitud, eliminarSolicitud } from "../api/solicitudes";
import { getPlantas } from "../api/plantas";
import { puede } from "../lib/permisos";
import { mensajeError } from "../lib/errores";
import { useAuth } from "../contexts/AuthContext";
import { getClientes } from "../api/clientes";
import { getMateriales } from "../api/materiales";
import { Icon } from "../components/ui/Icon";
import type { SolicitudCotizacion, SolicitudEstado } from "../types";

const ESTADO_LABEL: Record<SolicitudEstado, string> = {
  pendiente: "Pendiente",
  cotizada: "Cotizada",
  en_seguimiento: "En seguimiento",
  cerrada: "Cerrada",
};

const ESTADO_COLOR: Record<SolicitudEstado, string> = {
  pendiente: "#f59e0b",
  cotizada: "#0f6cbd",
  en_seguimiento: "#f97316",
  cerrada: "#64748b",
};

interface ItemRow { material: string; cantidad: string }

export function SolicitudesCotizacionPage() {
  const qc = useQueryClient();
  const { data: solicitudes, isLoading } = useQuery({ queryKey: ["solicitudes"], queryFn: () => getSolicitudes() });
  const { data: clientes } = useQuery({ queryKey: ["clientes"], queryFn: () => getClientes() });
  const { data: todosMateriales } = useQuery({ queryKey: ["materiales"], queryFn: getMateriales });
  const { data: plantas } = useQuery({ queryKey: ["plantas"], queryFn: () => getPlantas() });
  const { user } = useAuth();
  const puedeEditar = puede(user, "solicitudes");
  const [editandoId, setEditandoId] = useState<number | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [clienteId, setClienteId] = useState("");
  const [obra, setObra] = useState("");
  const [notas, setNotas] = useState("");
  const [items, setItems] = useState<ItemRow[]>([{ material: "", cantidad: "" }]);

  // Solo los materiales que alguna planta activa vende: son los mismos nombres
  // que aparecen en Plantas y precios y en la cotización. El que ya tenga la
  // solicitud en edición se deja aunque no tenga precio, para no perderlo.
  const materiales = (todosMateriales ?? []).filter(m =>
    m.precios.some(p => plantas?.some(pl => pl.id === p.planta))
    || items.some(i => i.material === String(m.id)));

  const limpiar = () => {
    setShowForm(false); setEditandoId(null);
    setClienteId(""); setNotas(""); setObra(""); setItems([{ material: "", cantidad: "" }]);
  };

  const createMut = useMutation({
    mutationFn: () => {
      const datos = {
        cliente: Number(clienteId),
        obra,
        notas,
        items: items.filter(i => i.material && i.cantidad).map(i => ({ material: Number(i.material), cantidad: Number(i.cantidad) })),
      };
      return editandoId ? actualizarSolicitud(editandoId, datos) : createSolicitud(datos);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success(editandoId ? "Solicitud actualizada" : "Solicitud de cotización creada");
      limpiar();
    },
    onError: e => toast.error(mensajeError(e, "No se pudo guardar la solicitud")),
  });

  const eliminarMut = useMutation({
    mutationFn: (s: SolicitudCotizacion) => eliminarSolicitud(s.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success("Solicitud eliminada");
    },
    onError: e => toast.error(mensajeError(e, "No se pudo eliminar la solicitud")),
  });

  const editar = (s: SolicitudCotizacion) => {
    setEditandoId(s.id);
    setClienteId(String(s.cliente)); setObra(s.obra ?? ""); setNotas(s.notas ?? "");
    setItems(s.items.map(i => ({ material: String(i.material), cantidad: String(Number(i.cantidad)) })));
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const updateItem = (idx: number, field: keyof ItemRow, value: string) => {
    setItems(rows => rows.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Solicitudes de Cotización</h1>
        <button className="btn-primary" onClick={() => { if (showForm) limpiar(); else setShowForm(true); }}>
          <Icon name="add" size={16} />Nueva solicitud
        </button>
      </div>

      {showForm && (
        <form className="card" style={{ padding: 16, marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          {editandoId && (
            <p style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 600, display: "flex", gap: 6, alignItems: "center" }}>
              <Icon name="edit" size={15} />Editando {solicitudes?.find(s => s.id === editandoId)?.numero}
            </p>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label className="section-label">Cliente *</label>
              <select className="input-base" style={{ width: "100%" }} value={clienteId} onChange={e => setClienteId(e.target.value)} required>
                <option value="">Selecciona un cliente</option>
                {clientes?.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="section-label">Obra</label>
              <input className="input-base" style={{ width: "100%" }} value={obra} placeholder="Proyecto al que va el material"
                onChange={e => setObra(e.target.value)} />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="section-label">Notas</label>
              <input className="input-base" style={{ width: "100%" }} value={notas} onChange={e => setNotas(e.target.value)} />
            </div>
          </div>

          <label className="section-label">Materiales</label>
          {items.map((row, idx) => (
            <div key={idx} style={{ display: "flex", gap: 8, marginBottom: 6 }}>
              <select className="input-base" style={{ flex: 2 }} value={row.material} onChange={e => updateItem(idx, "material", e.target.value)}>
                <option value="">Material</option>
                {materiales.map(m => <option key={m.id} value={m.id}>{m.nombre} ({m.unidad_medida})</option>)}
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
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>{editandoId ? "Guardar cambios" : "Guardar"}</button>
            <button type="button" className="btn-secondary" onClick={limpiar}>Cancelar</button>
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
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
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
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {puedeEditar && !s.tiene_cotizacion && (
                    <>
                      <button className="btn-ghost" title="Editar" onClick={() => editar(s)}><Icon name="edit" size={16} /></button>
                      <button className="btn-ghost" title="Eliminar" style={{ color: "#dc2626" }}
                        onClick={() => confirm(`¿Eliminar la solicitud ${s.numero}?`) && eliminarMut.mutate(s)}>
                        <Icon name="delete" size={16} />
                      </button>
                    </>
                  )}
                  {puedeEditar && s.tiene_cotizacion && (
                    <span title="Tiene una cotización en curso: edita o elimina la cotización primero" style={{ color: "var(--text-muted)" }}>
                      <Icon name="lock" size={15} />
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!isLoading && solicitudes?.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin solicitudes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
