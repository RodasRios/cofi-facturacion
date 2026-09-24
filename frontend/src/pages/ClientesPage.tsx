import { useState } from "react";
import { puede } from "../lib/permisos";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getClientes, createCliente, marcarVinculado } from "../api/clientes";
import { Icon } from "../components/ui/Icon";
import { PdfViewerModal } from "../components/ui/PdfViewerModal";
import { LinksVinculacion } from "../components/LinksVinculacion";
import { ControlDespachosFiltro } from "../components/ControlDespachosFiltro";
import { crearSolicitudToken, urlPedidos } from "../api/solicitudTokens";
import { useAuth } from "../contexts/AuthContext";

export function ClientesPage() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const { data: clientes, isLoading } = useQuery({ queryKey: ["clientes"], queryFn: () => getClientes() });
  const [pdfViewer, setPdfViewer] = useState<{ url: string; filename: string } | null>(null);

  // Los links de vinculación los genera el comercial (o un admin).
  const puedeGenerarLinks = puede(user, "clientes");
  const [showLinks, setShowLinks] = useState(false);
  const [controlAbierto, setControlAbierto] = useState<number | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [nombre, setNombre] = useState("");
  const [nit, setNit] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [direccion, setDireccion] = useState("");
  const [tipoPrecio, setTipoPrecio] = useState<"especial" | "detal">("especial");

  const createMut = useMutation({
    mutationFn: () => createCliente({ nombre, nit, telefono, email, direccion, tipo_precio: tipoPrecio }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clientes"] });
      toast.success("Cliente creado — formato de vinculación generado automáticamente");
      setShowForm(false);
      setNombre(""); setNit(""); setTelefono(""); setEmail(""); setDireccion(""); setTipoPrecio("especial");
    },
    onError: () => toast.error("No se pudo crear el cliente"),
  });

  // Link de pedidos del cliente: uno solo por cliente, se reutiliza si ya existe.
  const linkPedidosMut = useMutation({
    mutationFn: (clienteId: number) => crearSolicitudToken(clienteId),
    onSuccess: async (t) => {
      const url = urlPedidos(t.token);
      try {
        await navigator.clipboard.writeText(url);
        toast.success("Link de pedidos copiado — envíaselo al cliente");
      } catch {
        toast.error(`Cópialo manualmente: ${url}`);
      }
    },
    onError: () => toast.error("No se pudo generar el link de pedidos"),
  });

  const vincularMut = useMutation({
    mutationFn: (id: number) => marcarVinculado(id, true),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["clientes"] });
      toast.success("Cliente marcado como vinculado");
    },
    onError: () => toast.error("No se pudo actualizar el cliente"),
  });

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Clientes</h1>
        <div style={{ display: "flex", gap: 8 }}>
          {puedeGenerarLinks && (
            <button className="btn-secondary" onClick={() => setShowLinks(v => !v)}>
              <Icon name="link" size={16} />Link para cliente
            </button>
          )}
          <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
            <Icon name="add" size={16} />Nuevo cliente
          </button>
        </div>
      </div>

      {showLinks && puedeGenerarLinks && <LinksVinculacion />}

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
          <div>
            <label className="section-label">Tarifa</label>
            <select className="input-base" style={{ width: "100%" }} value={tipoPrecio}
              onChange={e => setTipoPrecio(e.target.value as "especial" | "detal")}>
              <option value="especial">Venta especial</option>
              <option value="detal">Venta detal</option>
            </select>
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
              <th>N.° Vinculación</th>
              <th>Nombre</th>
              <th>NIT</th>
              <th>Teléfono</th>
              <th>Email</th>
              <th>Estado</th>
              <th>Creado por</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={8} style={{ textAlign: "center", padding: 20 }}>Cargando…</td></tr>}
            {clientes?.map(c => [
              <tr key={c.id}>
                <td>{c.numero_vinculacion || "-"}</td>
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
                    <span className="badge" style={{ background: "#f59e0b22", color: "#f59e0b" }}>Pendiente</span>
                  )}
                </td>
                <td>{c.creado_por_username || "-"}</td>
                <td>
                  <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                    {c.pdf_path && (
                      <button className="btn-ghost" title="Ver formato de vinculación"
                        onClick={() => setPdfViewer({ url: `/clientes/${c.id}/pdf/`, filename: `${c.numero_vinculacion}.pdf` })}>
                        <Icon name="picture_as_pdf" size={16} />
                      </button>
                    )}
                    <button className="btn-ghost" title="Control de despacho de materiales"
                      onClick={() => setControlAbierto(controlAbierto === c.id ? null : c.id)}>
                      <Icon name="receipt_long" size={16} />
                    </button>
                    {puedeGenerarLinks && (
                      <button className="btn-ghost" title="Copiar link para que el cliente pida cotizaciones"
                        onClick={() => linkPedidosMut.mutate(c.id)} disabled={linkPedidosMut.isPending}>
                        <Icon name="shopping_cart" size={16} />
                      </button>
                    )}
                    {!c.vinculado && (
                      <button className="btn-secondary" onClick={() => vincularMut.mutate(c.id)}>
                        <Icon name="check" size={14} />Marcar vinculado
                      </button>
                    )}
                  </div>
                </td>
              </tr>,
              controlAbierto === c.id && (
                <tr key={`${c.id}-control`}>
                  <td colSpan={8} style={{ background: "var(--bg-surface-2)", padding: 0 }}>
                    <ControlDespachosFiltro cliente={c} onVer={(url, filename) => setPdfViewer({ url, filename })} />
                  </td>
                </tr>
              ),
            ])}
            {!isLoading && clientes?.length === 0 && (
              <tr><td colSpan={8} style={{ textAlign: "center", padding: 20, color: "var(--text-muted)" }}>Sin clientes todavía</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {pdfViewer && <PdfViewerModal url={pdfViewer.url} filename={pdfViewer.filename} onClose={() => setPdfViewer(null)} />}
    </div>
  );
}
