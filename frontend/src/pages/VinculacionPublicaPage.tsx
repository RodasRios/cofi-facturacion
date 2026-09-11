import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { NeuralBackground } from "../components/ui/NeuralBackground";
import { Icon } from "../components/ui/Icon";
import { getVinculacionInfo, enviarVinculacion } from "../api/clienteTokens";

/**
 * Formulario que abre el cliente con el link que le mandó el comercial.
 * No requiere usuario ni contraseña: el token del link es la credencial.
 */
export function VinculacionPublicaPage() {
  const { token = "" } = useParams();

  const { data: info, isLoading, error } = useQuery({
    queryKey: ["vinculacion-publica", token],
    queryFn: () => getVinculacionInfo(token),
    retry: false,
  });

  const [nombre, setNombre] = useState("");
  const [nit, setNit] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [direccion, setDireccion] = useState("");

  const enviar = useMutation({
    mutationFn: () => enviarVinculacion(token, { nombre, nit, telefono, email, direccion }),
  });

  const mensajeError = (() => {
    if (!error) return null;
    const e = error as { response?: { data?: { detail?: string } } };
    return e.response?.data?.detail ?? "No se pudo cargar el formulario. Revisa tu conexión.";
  })();

  return (
    <div className="vinc-root">
      <NeuralBackground />

      <div className="vinc-panel">
        <div className="vinc-brand">
          <img src="/logo.svg" alt="" className="vinc-logo" />
          <div>
            <h1 className="vinc-title">Vinculación de cliente</h1>
            <p className="vinc-subtitle">Triturados y Concretos Ltda</p>
          </div>
        </div>

        <div className="vinc-divider" />

        {isLoading && (
          <p className="vinc-muted"><Icon name="sync" size={14} className="spin" /> Verificando el link…</p>
        )}

        {mensajeError && (
          <div className="vinc-alert vinc-alert-error">
            <Icon name="error" size={16} />
            <span>{mensajeError}</span>
          </div>
        )}

        {enviar.isSuccess && (
          <div className="vinc-alert vinc-alert-ok">
            <Icon name="check_circle" size={16} />
            <div>
              <strong>¡Listo! Recibimos tus datos.</strong>
              <p style={{ margin: "4px 0 0" }}>
                Tu número de vinculación es <strong>{enviar.data.numero_vinculacion}</strong>.
                Un asesor comercial se comunicará contigo.
              </p>
            </div>
          </div>
        )}

        {info && !enviar.isSuccess && (
          <>
            <p className="vinc-muted" style={{ marginBottom: 16 }}>
              Completa tus datos para quedar registrado como cliente. Este link se puede usar una sola vez.
            </p>

            <form
              className="vinc-form"
              onSubmit={(e) => { e.preventDefault(); enviar.mutate(); }}
            >
              <div className="form-field">
                <label className="form-label">Nombre o razón social *</label>
                <input className="input-base" value={nombre} onChange={e => setNombre(e.target.value)} required autoFocus />
              </div>
              <div className="vinc-row">
                <div className="form-field">
                  <label className="form-label">NIT / Cédula</label>
                  <input className="input-base" value={nit} onChange={e => setNit(e.target.value)} />
                </div>
                <div className="form-field">
                  <label className="form-label">Teléfono</label>
                  <input className="input-base" value={telefono} onChange={e => setTelefono(e.target.value)} />
                </div>
              </div>
              <div className="form-field">
                <label className="form-label">Correo electrónico</label>
                <input className="input-base" type="email" value={email} onChange={e => setEmail(e.target.value)} />
              </div>
              <div className="form-field">
                <label className="form-label">Dirección</label>
                <input className="input-base" value={direccion} onChange={e => setDireccion(e.target.value)} />
              </div>

              {enviar.isError && (
                <div className="vinc-alert vinc-alert-error">
                  <Icon name="error" size={16} />
                  <span>
                    {(enviar.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                      ?? "No se pudieron enviar los datos. Intenta de nuevo."}
                  </span>
                </div>
              )}

              <button type="submit" className="btn-primary vinc-btn" disabled={enviar.isPending}>
                {enviar.isPending
                  ? <><Icon name="sync" size={15} className="spin" />Enviando…</>
                  : <><Icon name="send" size={15} />Enviar datos</>}
              </button>
            </form>
          </>
        )}
      </div>

      <style>{`
        .vinc-root { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-base); position: relative; padding: 20px; }
        .vinc-panel { position: relative; z-index: 10; background: var(--bg-surface); border: 1px solid var(--border); box-shadow: var(--shadow-md); width: 100%; max-width: 440px; padding: 28px; }
        .vinc-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .vinc-logo { width: 40px; height: 40px; flex-shrink: 0; }
        .vinc-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; letter-spacing: -0.02em; }
        .vinc-subtitle { font-size: 12px; color: var(--text-muted); margin: 2px 0 0; }
        .vinc-divider { height: 1px; background: var(--border); margin-bottom: 20px; }
        .vinc-muted { font-size: 12.5px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; margin: 0; }
        .vinc-form { display: flex; flex-direction: column; gap: 13px; }
        .vinc-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        @media (max-width: 430px) { .vinc-row { grid-template-columns: 1fr; } }
        .form-field { display: flex; flex-direction: column; gap: 5px; }
        .form-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
        .vinc-btn { width: 100%; justify-content: center; padding: 9px 14px; font-size: 13px; margin-top: 4px; }
        .vinc-alert { display: flex; align-items: flex-start; gap: 8px; font-size: 12.5px; padding: 10px 12px; line-height: 1.45; }
        .vinc-alert-error { background: #fef2f2; border: 1px solid #fca5a5; color: #dc2626; }
        .dark .vinc-alert-error { background: #2d0f0f; border-color: #7f1d1d; color: #f87171; }
        .vinc-alert-ok { background: #f0fdf4; border: 1px solid #86efac; color: #15803d; }
        .dark .vinc-alert-ok { background: #0c2313; border-color: #166534; color: #4ade80; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}
