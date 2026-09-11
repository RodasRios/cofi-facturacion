import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import {
  getClienteTokens, createClienteToken, revocarClienteToken, urlVinculacion,
} from "../api/clienteTokens";
import type { ClienteToken, ClienteTokenEstado } from "../types";

const ESTILO_ESTADO: Record<ClienteTokenEstado, { texto: string; bg: string; color: string }> = {
  activo:   { texto: "Activo",   bg: "var(--accent-light)", color: "var(--accent-text)" },
  usado:    { texto: "Usado",    bg: "#3b82f622",           color: "#3b82f6" },
  vencido:  { texto: "Vencido",  bg: "#f59e0b22",           color: "#f59e0b" },
  revocado: { texto: "Anulado",  bg: "#ef444422",           color: "#ef4444" },
};

function fechaCorta(iso: string) {
  return new Date(iso).toLocaleString("es-CO", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

async function copiar(texto: string) {
  try {
    await navigator.clipboard.writeText(texto);
    toast.success("Link copiado — ya puedes enviárselo al cliente");
  } catch {
    // Algunos navegadores bloquean el portapapeles; mostrar el link para copiarlo a mano.
    toast.error("No se pudo copiar automáticamente. Copia el link manualmente.");
  }
}

export function LinksVinculacion() {
  const qc = useQueryClient();
  const [etiqueta, setEtiqueta] = useState("");
  const [ultimo, setUltimo] = useState<ClienteToken | null>(null);

  const { data: tokens, isLoading } = useQuery({
    queryKey: ["cliente-tokens"],
    queryFn: getClienteTokens,
  });

  const generar = useMutation({
    mutationFn: () => createClienteToken(etiqueta.trim() || undefined),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["cliente-tokens"] });
      setUltimo(t);
      setEtiqueta("");
      copiar(urlVinculacion(t.token));
    },
    onError: () => toast.error("No se pudo generar el link"),
  });

  const revocar = useMutation({
    mutationFn: (id: number) => revocarClienteToken(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cliente-tokens"] });
      toast.success("Link anulado");
    },
    onError: () => toast.error("No se pudo anular el link"),
  });

  return (
    <div className="card" style={{ padding: 16, marginBottom: 16 }}>
      <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 4px" }}>
        Links de vinculación
      </h2>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 14px" }}>
        Genera un link y envíaselo al cliente para que llene sus propios datos. Sirve una sola
        vez y vence a los 3 días. Al enviarlo, el cliente y su formato de vinculación se crean solos.
      </p>

      <form
        style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 14, flexWrap: "wrap" }}
        onSubmit={(e) => { e.preventDefault(); generar.mutate(); }}
      >
        <div style={{ flex: "1 1 220px" }}>
          <label className="section-label">Referencia (opcional)</label>
          <input
            className="input-base"
            style={{ width: "100%" }}
            placeholder="Para saber a quién se lo mandaste"
            value={etiqueta}
            onChange={e => setEtiqueta(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={generar.isPending}>
          <Icon name="link" size={15} />
          {generar.isPending ? "Generando…" : "Generar link nuevo"}
        </button>
      </form>

      {ultimo && (
        <div className="link-nuevo">
          <Icon name="check_circle" size={16} />
          <code className="link-nuevo-url">{urlVinculacion(ultimo.token)}</code>
          <button className="btn-secondary" onClick={() => copiar(urlVinculacion(ultimo.token))}>
            <Icon name="content_copy" size={14} />Copiar
          </button>
        </div>
      )}

      <table className="table-sharp">
        <thead>
          <tr>
            <th>Referencia</th>
            <th>Estado</th>
            <th>Vence</th>
            <th>Cliente registrado</th>
            <th>Generado por</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {isLoading && <tr><td colSpan={6} style={{ textAlign: "center", padding: 16 }}>Cargando…</td></tr>}
          {tokens?.map(t => {
            const est = ESTILO_ESTADO[t.estado];
            return (
              <tr key={t.id}>
                <td>{t.etiqueta || <span style={{ color: "var(--text-muted)" }}>Sin referencia</span>}</td>
                <td><span className="badge" style={{ background: est.bg, color: est.color }}>{est.texto}</span></td>
                <td>{fechaCorta(t.expira_at)}</td>
                <td>{t.cliente_nombre || "-"}</td>
                <td>{t.creado_por_username || "-"}</td>
                <td>
                  <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                    {t.estado === "activo" && (
                      <>
                        <button className="btn-ghost" title="Copiar link"
                          onClick={() => copiar(urlVinculacion(t.token))}>
                          <Icon name="content_copy" size={16} />
                        </button>
                        <button className="btn-ghost" title="Anular link"
                          onClick={() => revocar.mutate(t.id)} disabled={revocar.isPending}>
                          <Icon name="link_off" size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
          {!isLoading && tokens?.length === 0 && (
            <tr><td colSpan={6} style={{ textAlign: "center", padding: 16, color: "var(--text-muted)" }}>
              Todavía no has generado ningún link
            </td></tr>
          )}
        </tbody>
      </table>

      <style>{`
        .link-nuevo {
          display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
          background: #f0fdf4; border: 1px solid #86efac; color: #15803d;
          padding: 10px 12px; margin-bottom: 14px; font-size: 12.5px;
        }
        .dark .link-nuevo { background: #0c2313; border-color: #166534; color: #4ade80; }
        .link-nuevo-url {
          flex: 1 1 240px; font-family: ui-monospace, monospace; font-size: 11.5px;
          overflow-wrap: anywhere;
        }
      `}</style>
    </div>
  );
}
