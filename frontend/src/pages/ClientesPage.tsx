import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getClientes, createCliente, uploadVinculacion } from "../api/clientes";
import { Icon } from "../components/ui/Icon";

export function ClientesPage() {
  const qc = useQueryClient();
  const { data: clientes, isLoading } = useQuery({ queryKey: ["clientes"], queryFn: () => getClientes() });

  const [showForm, setShowForm] = useState(false);
  const [nombre, setNombre] = useState("");
  const [nit, setNit] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [direccion, setDireccion] = useState("");

  const createMut = useMutation({
    mutationFn: () => createCliente({ nombre, nit, telefono, email, direccion }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clientes"] });
      toast.success("Cliente creado");
      setShowForm(false);
      setNombre(""); setNit(""); setTelefono(""); setEmail(""); setDireccion("");
    },
    onError: () => toast.error("No se pudo crear el cliente"),
  });

  const vincularMut = useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => uploadVinculacion(id, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clientes"] });
      toast.success("Formato de vinculación cargado");
    },
    onError: () => toast.error("No se pudo cargar el archivo"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Clientes</h1>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Icon name="add" size={16} />Nuevo cliente
        </button>
      </div>

      {showForm && (
        <form
          className="card"
          style={{ padding: 16, marginBottom: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
          onSubmit={(e) => { e.preventDefault(); createMut.mutate(); }}
        >
          <div>
            <label className="section-label">Nombre *</label>
            <input className="input-base" style={{ width: "100%" }} value={nombre} onChange={e => setNombre(e.target.value)} required />
          </div>
          <div>
            <label className="section-label">NIT / Cédula</label>
            <input className="input-base" style={{ width: "100%" }} value={nit} onChange={e => setNit(e.target.value)} />
          </div>
          <div>
            <label className="section-label">Teléfono</label>
            <input className="input-base" style={{ width: "100%" }} value={telefono} onChange={e => setTelefono(e.target.value)} />
          </div>
          <div>
            <label className="section-label">Email</label>
            <input className="input-base" style={{ width: "100%" }} type="email" value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label className="section-label">Dirección</label>
            <input className="input-base" style={{ width: "100%" }} value={direccion} onChange={e => setDireccion(e.target.value)} />
          </div>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8 }}>
            <button type="submit" className="btn-primary" disabled={createMut.isPending}>Guardar</button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
          </div>
        </form>
      )}

      <div className="card">
        <table className="table-sharp">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>NIT</th>
              <th>Teléfono</th>
              <th>Email</th>
              <th>Vinculación</th>
              <th>Creado por</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {clientes?.map(c => (
              <tr key={c.id}>
                <td>{c.nombre}</td>
                <td>{c.nit || "-"}</td>
                <td>{c.telefono || "-"}</td>
                <td>{c.email || "-"}</td>
                <td>
                  {c.vinculado ? (
                    <span className="badge" style={{ background: "var(--accent-light)", color: "var(--accent-text)" }}>
                      <Icon name="check_circle" size={12} />Vinculado
                    </span>
                  ) : (
                    <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--accent-text)" }}>
                      <Icon name="upload_file" size={13} />
                      Cargar formato
                      <input type="file" accept=".pdf,.png,.jpg,.jpeg" style={{ display: "none" }}
                        onChange={e => {
                          const file = e.target.files?.[0];
                          if (file) vincularMut.mutate({ id: c.id, file });
                          e.target.value = "";
                        }}
                      />
                    </label>
                  )}
                </td>
                <td>{c.creado_por_username || "-"}</td>
              </tr>
            ))}
            {!isLoading && clientes?.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin clientes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
