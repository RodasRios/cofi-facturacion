import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getDespachos, createDespacho } from "../api/despachos";
import { getOrdenesSuministro } from "../api/ordenesSuministro";
import { downloadAuthed } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { Icon } from "../components/ui/Icon";

export function DespachosPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data: despachos, isLoading } = useQuery({ queryKey: ["despachos"], queryFn: () => getDespachos() });
  const { data: ordenes } = useQuery({ queryKey: ["ordenes-suministro"], queryFn: () => getOrdenesSuministro() });

  const esPlanta = user?.is_admin || user?.rol === "planta";

  const [showForm, setShowForm] = useState(false);
  const [ordenId, setOrdenId] = useState("");
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [recibidoPor, setRecibidoPor] = useState("");
  const [placa, setPlaca] = useState("");
  const [clienteRetira, setClienteRetira] = useState(true);
  const [cantidades, setCantidades] = useState<Record<number, string>>({});

  const ordenSel = useMemo(() => ordenes?.find(o => String(o.id) === ordenId), [ordenes, ordenId]);

  const createMut = useMutation({
    mutationFn: () => createDespacho({
      orden_suministro: Number(ordenId), fecha, recibido_por: recibidoPor,
      placa_vehiculo: placa, cliente_retira: clienteRetira,
      items: (ordenSel?.items ?? [])
        .filter(i => Number(cantidades[i.material] ?? i.cantidad) > 0)
        .map(i => ({ material: i.material, cantidad: Number(cantidades[i.material] ?? i.cantidad) })),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["despachos"] });
      toast.success("Remisión de despacho generada");
      setShowForm(false);
      setOrdenId(""); setRecibidoPor(""); setPlaca(""); setCantidades({});
    },
    onError: () => toast.error("No se pudo generar el despacho"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Control de Despacho y Recibo de Material</h1>
        {esPlanta && (
          <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
            <Icon name="add" size={16} />Nuevo despacho
          </button>
        )}
      </div>

      {showForm && (
        <form className="card" style={{ padding: 16, marginBottom: 16 }} onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label className="section-label">Orden de suministro *</label>
              <select className="input-base" style={{ width: "100%" }} value={ordenId} onChange={e => setOrdenId(e.target.value)} required>
                <option value="">Selecciona una orden</option>
                {ordenes?.map(o => <option key={o.id} value={o.id}>{o.numero} — {o.cliente_nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="section-label">Fecha *</label>
              <input className="input-base" style={{ width: "100%" }} type="date" value={fecha} onChange={e => setFecha(e.target.value)} required />
            </div>
            <div>
              <label className="section-label">Placa vehículo</label>
              <input className="input-base" style={{ width: "100%" }} value={placa} onChange={e => setPlaca(e.target.value)} />
            </div>
          </div>

          {ordenSel && (
            <div style={{ marginBottom: 12 }}>
              <label className="section-label">Materiales a despachar</label>
              {ordenSel.items.map(i => (
                <div key={i.material} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ flex: 2, fontSize: 13 }}>{i.material_nombre}</span>
                  <input className="input-base" style={{ flex: 1 }} type="number" min="0" step="0.01"
                    value={cantidades[i.material] ?? i.cantidad}
                    onChange={e => setCantidades(c => ({ ...c, [i.material]: e.target.value }))} />
                  <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{i.unidad_medida}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <div>
              <label className="section-label">Recibido por</label>
              <input className="input-base" style={{ width: "100%" }} value={recibidoPor} onChange={e => setRecibidoPor(e.target.value)} />
            </div>
            <div style={{ display: "flex", alignItems: "flex-end", paddingBottom: 6 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
                <input type="checkbox" checked={clienteRetira} onChange={e => setClienteRetira(e.target.checked)} />
                El cliente retira el material
              </label>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" className="btn-primary" disabled={createMut.isPending || !ordenSel}>Generar remisión</button>
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
              <th>Fecha</th>
              <th>Retira</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {despachos?.map(d => (
              <tr key={d.id}>
                <td>{d.numero}</td>
                <td>{d.cliente_nombre}</td>
                <td>{d.planta_nombre}</td>
                <td>{d.fecha}</td>
                <td>{d.cliente_retira ? "Cliente" : "Transporte propio"}</td>
                <td>
                  <button className="btn-ghost" title="Descargar PDF" onClick={() => downloadAuthed(`/despachos/${d.id}/pdf/`, `${d.numero}.pdf`)}>
                    <Icon name="picture_as_pdf" size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {!isLoading && despachos?.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin despachos todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
