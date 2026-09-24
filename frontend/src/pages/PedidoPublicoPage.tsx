import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { NeuralBackground } from "../components/ui/NeuralBackground";
import { Icon } from "../components/ui/Icon";
import { getPedidoInfo, enviarPedido } from "../api/solicitudTokens";

/**
 * El cliente arma su propia solicitud de cotización desde el link que le pasó
 * el comercial. Sin usuario: el token del link es la credencial.
 *
 * El catálogo llega sin precios a propósito — la cotización la arma la empresa
 * después, eligiendo planta y aplicando el precio que corresponda.
 */
export function PedidoPublicoPage() {
  const { token = "" } = useParams();

  const { data: info, isLoading, error } = useQuery({
    queryKey: ["pedido-publico", token],
    queryFn: () => getPedidoInfo(token),
    retry: false,
  });

  const [cantidades, setCantidades] = useState<Record<number, string>>({});
  const [obra, setObra] = useState("");
  const [notas, setNotas] = useState("");

  const seleccionados = Object.entries(cantidades)
    .filter(([, v]) => Number(v) > 0)
    .map(([material, v]) => ({ material: Number(material), cantidad: Number(v) }));

  const enviar = useMutation({
    mutationFn: () => enviarPedido(token, {
      items: seleccionados, obra: obra || undefined, notas: notas || undefined,
    }),
  });

  const detalleDe = (e: unknown, fallback: string) =>
    (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback;

  return (
    <div className="ped-root">
      <NeuralBackground />

      <div className="ped-panel">
        <div className="ped-brand">
          <img src="/logo.svg" alt="" className="ped-logo" />
          <div>
            <h1 className="ped-title">Solicitud de cotización</h1>
            <p className="ped-subtitle">
              {info ? info.cliente_nombre : "Triturados y Concretos Ltda"}
            </p>
          </div>
        </div>

        <div className="ped-divider" />

        {isLoading && (
          <p className="ped-muted"><Icon name="sync" size={14} className="spin" /> Cargando…</p>
        )}

        {error && (
          <div className="ped-alert ped-alert-error">
            <Icon name="error" size={16} />
            <span>{detalleDe(error, "No se pudo cargar el formulario. Revisa tu conexión.")}</span>
          </div>
        )}

        {enviar.isSuccess && (
          <div className="ped-alert ped-alert-ok">
            <Icon name="check_circle" size={16} />
            <div>
              <strong>Recibimos tu solicitud.</strong>
              <p style={{ margin: "4px 0 0" }}>
                Quedó registrada como <strong>{enviar.data.numero}</strong>. Un asesor comercial
                te enviará la cotización.
              </p>
              <button
                className="btn-secondary"
                style={{ marginTop: 10 }}
                onClick={() => { enviar.reset(); setCantidades({}); setObra(""); setNotas(""); }}
              >
                <Icon name="add" size={14} />Hacer otra solicitud
              </button>
            </div>
          </div>
        )}

        {info && !enviar.isSuccess && (
          <>
            <p className="ped-muted" style={{ marginBottom: 14 }}>
              Escribe las cantidades que necesitas. Te responderemos con la cotización y los precios.
            </p>

            <form onSubmit={(e) => { e.preventDefault(); enviar.mutate(); }}>
              <div className="ped-materiales">
                {info.materiales.map(m => (
                  <div key={m.id} className="ped-material">
                    <div>
                      <span className="ped-material-nombre">{m.nombre}</span>
                      <span className="ped-material-unidad">{m.unidad_medida}</span>
                    </div>
                    <input
                      className="input-base ped-cantidad"
                      type="number"
                      min="0"
                      step="0.01"
                      placeholder="0"
                      value={cantidades[m.id] ?? ""}
                      onChange={e => setCantidades(c => ({ ...c, [m.id]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>

              <div className="form-field" style={{ marginTop: 12 }}>
                <label className="form-label">Obra o proyecto</label>
                <input className="input-base" value={obra} onChange={e => setObra(e.target.value)} />
              </div>

              <div className="form-field" style={{ marginTop: 12 }}>
                <label className="form-label">Observaciones (fecha requerida, etc.)</label>
                <input className="input-base" value={notas} onChange={e => setNotas(e.target.value)} />
              </div>

              {enviar.isError && (
                <div className="ped-alert ped-alert-error" style={{ marginTop: 12 }}>
                  <Icon name="error" size={16} />
                  <span>{detalleDe(enviar.error, "No se pudo enviar la solicitud. Intenta de nuevo.")}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn-primary ped-btn"
                disabled={seleccionados.length === 0 || enviar.isPending}
              >
                {enviar.isPending
                  ? <><Icon name="sync" size={15} className="spin" />Enviando…</>
                  : <><Icon name="send" size={15} />
                      Enviar solicitud{seleccionados.length > 0 && ` (${seleccionados.length})`}</>}
              </button>
            </form>
          </>
        )}
      </div>

      <style>{`
        .ped-root { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-base); position: relative; padding: 20px; }
        .ped-panel { position: relative; z-index: 10; background: var(--bg-surface); border: 1px solid var(--border); box-shadow: var(--shadow-md); width: 100%; max-width: 460px; padding: 28px; }
        .ped-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .ped-logo { width: 40px; height: 40px; flex-shrink: 0; }
        .ped-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; letter-spacing: -0.02em; }
        .ped-subtitle { font-size: 12px; color: var(--text-muted); margin: 2px 0 0; }
        .ped-divider { height: 1px; background: var(--border); margin-bottom: 20px; }
        .ped-muted { font-size: 12.5px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; margin: 0; }
        .ped-materiales { display: flex; flex-direction: column; }
        .ped-material {
          display: flex; justify-content: space-between; align-items: center; gap: 12px;
          padding: 8px 0; border-bottom: 1px solid var(--border);
        }
        .ped-material:last-child { border-bottom: none; }
        .ped-material-nombre { display: block; font-size: 13px; color: var(--text-primary); }
        .ped-material-unidad { display: block; font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .ped-cantidad { width: 110px; flex-shrink: 0; }
        .form-field { display: flex; flex-direction: column; gap: 5px; }
        .form-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
        .ped-btn { width: 100%; justify-content: center; padding: 9px 14px; font-size: 13px; margin-top: 14px; }
        .ped-alert { display: flex; align-items: flex-start; gap: 8px; font-size: 12.5px; padding: 10px 12px; line-height: 1.45; }
        .ped-alert-error { background: #fef2f2; border: 1px solid #fca5a5; color: #dc2626; }
        .dark .ped-alert-error { background: #2d0f0f; border-color: #7f1d1d; color: #f87171; }
        .ped-alert-ok { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; }
        .dark .ped-alert-ok { background: #0c2313; border-color: #166534; color: #4ade80; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}
