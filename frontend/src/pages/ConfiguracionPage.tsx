import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "../components/ui/Icon";
import { ImageCropper } from "../components/ui/ImageCropper";
import { useAuth } from "../contexts/AuthContext";
import { actualizarPerfil, cambiarPassword, uploadFirma, borrarFirma, getFirmaBlob } from "../api/auth";
import { mensajeError } from "../lib/errores";
import { puede } from "../lib/permisos";


// ─── Mi cuenta ────────────────────────────────────────────────────────────────

function MiCuenta() {
  const { user, refreshUser } = useAuth();
  const [datos, setDatos] = useState({
    nombre: user?.nombre ?? "", cedula: user?.cedula ?? "", cargo: user?.cargo ?? "",
    telefono: user?.telefono ?? "", email: user?.email ?? "",
  });
  const campo = (k: keyof typeof datos) => ({
    value: datos[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDatos(d => ({ ...d, [k]: e.target.value })),
  });

  const guardar = useMutation({
    mutationFn: () => actualizarPerfil(Object.fromEntries(
      Object.entries(datos).map(([k, v]) => [k, v.trim() || null]),
    )),
    onSuccess: async () => { await refreshUser(); toast.success("Datos guardados"); },
    onError: e => toast.error(mensajeError(e, "No se pudieron guardar los datos")),
  });

  return (
    <div className="cfg-seccion">
      <header>
        <h3>Mis datos</h3>
        <p>Tu nombre, cédula, cargo, teléfono y correo salen impresos bajo tu firma en las cotizaciones que armes.</p>
      </header>
      <form className="cfg-form" onSubmit={e => { e.preventDefault(); guardar.mutate(); }}>
        <label className="cfg-ancho">Nombre completo
          <input className="input-base" {...campo("nombre")} placeholder="Paola Andrea Posso Ortiz" />
        </label>
        <label>Cédula<input className="input-base" {...campo("cedula")} placeholder="1.112.345.678" /></label>
        <label>Cargo<input className="input-base" {...campo("cargo")} placeholder="Departamento Comercial" /></label>
        <label>Teléfono / celular<input className="input-base" {...campo("telefono")} placeholder="312 834 2898" /></label>
        <label>Correo<input className="input-base" type="email" {...campo("email")} placeholder="nombre@triturados.com" /></label>
        <div className="cfg-ancho cfg-acciones">
          <span className="cfg-meta">Usuario: <strong>{user?.username}</strong></span>
          <button className="btn-primary" disabled={guardar.isPending}>
            <Icon name="save" size={14} />{guardar.isPending ? "Guardando…" : "Guardar datos"}
          </button>
        </div>
      </form>

      <header style={{ marginTop: 28 }}>
        <h3>Cambiar contraseña</h3>
      </header>
      <CambiarPassword />
    </div>
  );
}

/** También la usa la pantalla de primer ingreso, sin pedir la actual. */
export function CambiarPassword({ primerIngreso = false, onListo }: { primerIngreso?: boolean; onListo?: () => void }) {
  const { refreshUser } = useAuth();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetir, setRepetir] = useState("");
  const noCoinciden = repetir.length > 0 && nueva !== repetir;

  const mut = useMutation({
    mutationFn: () => cambiarPassword(nueva, primerIngreso ? undefined : actual),
    onSuccess: async () => {
      await refreshUser();
      setActual(""); setNueva(""); setRepetir("");
      toast.success("Contraseña actualizada");
      onListo?.();
    },
    onError: e => toast.error(mensajeError(e, "No se pudo cambiar la contraseña")),
  });

  return (
    <form className="cfg-form" onSubmit={e => { e.preventDefault(); mut.mutate(); }}>
      {!primerIngreso && (
        <label className="cfg-ancho">Contraseña actual
          <input className="input-base" type="password" autoComplete="current-password"
            value={actual} onChange={e => setActual(e.target.value)} required />
        </label>
      )}
      <label>Nueva contraseña
        <input className="input-base" type="password" autoComplete="new-password" minLength={8}
          value={nueva} onChange={e => setNueva(e.target.value)} placeholder="Mínimo 8 caracteres" required />
      </label>
      <label>Repítela
        <input className="input-base" type="password" autoComplete="new-password"
          value={repetir} onChange={e => setRepetir(e.target.value)} required />
      </label>
      {noCoinciden && <p className="cfg-error cfg-ancho">Las contraseñas no coinciden.</p>}
      <div className="cfg-ancho cfg-acciones" style={{ justifyContent: "flex-end" }}>
        <button className="btn-primary" disabled={mut.isPending || noCoinciden || nueva.length < 8}>
          <Icon name="lock_reset" size={14} />{mut.isPending ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </div>
    </form>
  );
}

// ─── Mi firma ────────────────────────────────────────────────────────────────

function MiFirmaSeccion() {
  const { user, refreshUser } = useAuth();
  const input = useRef<HTMLInputElement>(null);
  const [recortar, setRecortar] = useState<File | null>(null);
  const [version, setVersion] = useState(0);
  const [url, setUrl] = useState<string | null>(null);
  const tiene = !!user?.firma_path;

  useEffect(() => {
    if (!tiene) return;
    let creada: string | null = null;
    let vivo = true;
    getFirmaBlob()
      .then(b => { if (vivo) { creada = URL.createObjectURL(b); setUrl(creada); } })
      .catch(() => { if (vivo) setUrl(null); });
    return () => { vivo = false; if (creada) URL.revokeObjectURL(creada); };
  }, [tiene, version]);

  const subir = useMutation({
    mutationFn: (blob: Blob) => uploadFirma(new File([blob], "firma.png", { type: "image/png" })),
    onSuccess: async () => { await refreshUser(); setVersion(v => v + 1); toast.success("Firma guardada"); },
    onError: e => toast.error(mensajeError(e, "No se pudo subir la firma")),
  });
  const quitar = useMutation({
    mutationFn: borrarFirma,
    onSuccess: async () => { await refreshUser(); setUrl(null); toast.success("Firma eliminada"); },
    onError: () => toast.error("No se pudo eliminar la firma"),
  });

  return (
    <div className="cfg-seccion">
      <header>
        <h3>Mi firma</h3>
        <p>Sale en las cotizaciones FR-GC-08 que armes, sobre tu nombre. Puedes recortarla antes de guardarla.</p>
      </header>

      {recortar ? (
        <ImageCropper
          file={recortar}
          hint="Encuadra solo el trazo de la firma, sin bordes de la hoja."
          onConfirm={b => { setRecortar(null); subir.mutate(b); }}
          onCancel={() => setRecortar(null)}
        />
      ) : (
        <>
          {/* Vista previa tal como queda en el PDF */}
          <div className="cfg-firma-preview">
            <div className="cfg-firma-img">
              {tiene && url
                ? <img src={url} alt="Mi firma" />
                : <span><Icon name="draw" size={26} /><br />Sin firma</span>}
            </div>
            <strong>{(user?.nombre || user?.username || "").toUpperCase()}</strong>
            {user?.cedula && <span>C.C. {user.cedula}</span>}
            {user?.cargo && <span>{user.cargo}</span>}
            {user?.telefono && <span>Cel.: {user.telefono}</span>}
            {user?.email && <span>Correo: {user.email}</span>}
          </div>
          <p className="cfg-meta" style={{ margin: "6px 0 14px" }}>
            Así sale en la cotización. Los datos se editan en "Mis datos".
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-secondary" disabled={subir.isPending} onClick={() => input.current?.click()}>
              <Icon name="upload" size={14} />{subir.isPending ? "Subiendo…" : tiene ? "Cambiar firma" : "Subir firma"}
            </button>
            {tiene && (
              <button className="btn-ghost" style={{ color: "#dc2626" }} disabled={quitar.isPending}
                onClick={() => confirm("¿Eliminar tu firma? Las cotizaciones saldrán con el espacio en blanco.") && quitar.mutate()}>
                <Icon name="delete" size={14} />Eliminar
              </button>
            )}
          </div>
          <input ref={input} type="file" accept="image/png,image/jpeg" hidden
            onChange={e => { const f = e.target.files?.[0]; if (f) setRecortar(f); e.target.value = ""; }} />
          <p className="cfg-meta" style={{ marginTop: 10 }}>
            PNG o JPG. Lo ideal: firma en tinta oscura sobre hoja blanca, foto de frente y con buena luz.
          </p>
        </>
      )}
    </div>
  );
}

// ─── Página ──────────────────────────────────────────────────────────────────

type Tab = "cuenta" | "firma";

export function ConfiguracionPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tabs: { key: Tab; icon: string; label: string }[] = [
    { key: "cuenta", icon: "account_circle", label: "Mi cuenta" },
    { key: "firma", icon: "draw", label: "Mi firma" },
  ];
  const pedido = params.get("tab") as Tab | null;
  // Los usuarios se mudaron a su propio panel.
  if (params.get("tab") === "usuarios") return <Navigate to="/usuarios" replace />;
  const tab: Tab = tabs.some(t => t.key === pedido) ? pedido! : "cuenta";

  return (
    <div>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 14px" }}>Configuración</h1>
      <div className="cfg">
        <nav className="cfg-nav">
          {tabs.map(t => (
            <button key={t.key} className={tab === t.key ? "activo" : ""} onClick={() => setParams({ tab: t.key })}>
              <Icon name={t.icon} size={17} />{t.label}
            </button>
          ))}
          {puede(user, "usuarios") && (
            <Link to="/usuarios" className="cfg-nav-link"><Icon name="admin_panel_settings" size={17} />Usuarios y permisos</Link>
          )}
        </nav>
        <div className="cfg-contenido">
          {tab === "cuenta" && <MiCuenta key={user?.id} />}
          {tab === "firma" && <MiFirmaSeccion />}
        </div>
      </div>

      <style>{`
        .cfg { display: flex; border: 1px solid var(--border); background: var(--bg-surface); min-height: 460px; }
        .cfg-nav { width: 190px; flex-shrink: 0; border-right: 1px solid var(--border); background: var(--bg-surface-2); padding-top: 6px; }
        .cfg-nav button {
          width: 100%; display: flex; align-items: center; gap: 10px; padding: 11px 16px; border: none;
          border-left: 3px solid transparent; background: transparent; color: var(--text-secondary);
          font: inherit; font-size: 13px; cursor: pointer; text-align: left;
        }
        .cfg-nav button:hover, .cfg-nav-link:hover { color: var(--text-primary); }
        .cfg-nav-link { display: flex; align-items: center; gap: 10px; padding: 11px 16px; font-size: 13px; color: var(--text-secondary);
          text-decoration: none; border-top: 1px solid var(--border); margin-top: 6px; white-space: nowrap; }
        .cfg-nav button.activo { background: var(--accent-light); border-left-color: var(--accent); color: var(--accent-text); font-weight: 600; }
        .cfg-contenido { flex: 1; min-width: 0; padding: 24px 28px; }
        @media (max-width: 720px) {
          .cfg { flex-direction: column; }
          .cfg-nav { width: auto; display: flex; overflow-x: auto; border-right: none; border-bottom: 1px solid var(--border); padding: 0; }
          .cfg-nav button { width: auto; border-left: none; border-bottom: 3px solid transparent; white-space: nowrap; }
          .cfg-nav button.activo { border-bottom-color: var(--accent); }
          .cfg-contenido { padding: 16px; }
        }
        .cfg-seccion { max-width: 560px; }
        .cfg-seccion-ancha { max-width: none; }
        .cfg-seccion header h3 { font-size: 15px; font-weight: 700; margin: 0 0 4px; color: var(--text-primary); }
        .cfg-seccion header p { font-size: 12px; color: var(--text-muted); margin: 0 0 16px; }
        .cfg-header-fila { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
        .cfg-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        @media (max-width: 560px) { .cfg-form { grid-template-columns: 1fr; } }
        .cfg-form > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .cfg-form .input-base { width: 100%; font-weight: 400; }
        .cfg-ancho { grid-column: 1 / -1; }
        .cfg-acciones { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
        .cfg-meta { font-size: 11.5px; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px; margin: 0; }
        .cfg-error { font-size: 12px; color: #dc2626; margin: 0; }
        .cfg-firma-preview {
          display: flex; flex-direction: column; gap: 1px; padding: 16px 18px; max-width: 360px;
          background: #fff; color: #111; border: 1px solid var(--border); font-size: 12.5px;
        }
        .cfg-firma-img { height: 80px; display: flex; align-items: flex-end; margin-bottom: 4px; }
        .cfg-firma-img img { max-height: 76px; max-width: 220px; object-fit: contain; }
        .cfg-firma-img span { color: #9ca3af; font-size: 11px; text-align: center; }
        .cfg-panel { border: 1px solid var(--border); background: var(--bg-surface-2); padding: 16px; margin-bottom: 16px; }
        .cfg-panel-titulo { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .cfg-panel-titulo h4 { margin: 0; font-size: 14px; display: flex; align-items: center; gap: 6px; }
        .cfg-permisos { border: none; padding: 0; margin: 4px 0 0; }
        .cfg-permisos legend { font-size: 11.5px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; padding: 0; }
        .cfg-permisos legend small { font-weight: 400; color: var(--text-muted); }
        .cfg-grupo label.heredado { opacity: 0.55; }
        .cfg-exclusivo { color: #b45309; font-style: normal; font-weight: 600; }
        .cfg-plantillas { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; font-size: 12px; color: var(--text-muted); }
        .cfg-plantillas button {
          display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; font: inherit; font-size: 12px; cursor: pointer;
          border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-secondary);
        }
        .cfg-plantillas button.activo { border-color: var(--accent); background: var(--accent-light); color: var(--accent-text); font-weight: 600; }
        .cfg-grupos { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
        .cfg-grupo { border: 1px solid var(--border); background: var(--bg-surface); padding: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
        .cfg-grupo.activo { border-color: var(--accent); }
        .cfg-grupo strong { font-size: 12.5px; }
        .cfg-grupo label { display: flex; gap: 6px; align-items: flex-start; font-size: 11.5px; color: var(--text-secondary); cursor: pointer; }
        .cfg-pestanas { font-size: 11.5px; color: var(--text-secondary); }
        .cfg-roles, .cfg-privilegios { border: none; padding: 0; margin: 4px 0 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 8px; }
        .cfg-roles legend, .cfg-privilegios legend { font-size: 11.5px; font-weight: 600; color: var(--text-secondary); margin-bottom: 6px; padding: 0; }
        .cfg-roles label, .cfg-privilegios label {
          display: flex; gap: 8px; align-items: flex-start; padding: 8px 10px; cursor: pointer;
          border: 1px solid var(--border); background: var(--bg-surface); font-size: 12.5px;
        }
        .cfg-roles label.activo { border-color: var(--accent); background: var(--accent-light); }
        .cfg-roles small, .cfg-privilegios small { display: block; color: var(--text-muted); font-size: 11px; margin-top: 1px; }
        .cfg-clave { border-color: #22c55e; background: #f0fdf4; color: #14532d; }
        .dark .cfg-clave { background: #052e16; color: #bbf7d0; }
        .cfg-clave p { font-size: 12px; margin: 0 0 8px; }
        .cfg-clave pre { background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border); padding: 10px 12px; font-size: 13px; margin: 0 0 10px; white-space: pre-wrap; }
        .cfg-tabla-wrap { overflow-x: auto; }
        .cfg-tabla td { vertical-align: middle; }
        .cfg-tabla tr.inactivo { opacity: 0.55; }
        .cfg-sub { display: block; font-size: 11px; color: var(--text-muted); }
        .cfg-sub-celda { font-size: 12px; color: var(--text-secondary); }
        .cfg-sub-celda em { color: var(--text-muted); }
        .cfg-acciones-fila { text-align: right; white-space: nowrap; }
        .cfg-tabla .badge { margin-right: 4px; }
        .cfg-badge-super { background: #be123c1f; color: #be123c; }
        .cfg-badge-admin { background: #0596691f; color: #059669; }
        .cfg-badge-off { background: #94a3b822; color: #64748b; }
        .cfg-badge-clave { background: #f59e0b22; color: #b45309; }
        .cfg-vacio { text-align: center; padding: 20px; color: var(--text-muted); }
        .cfg-leyenda { display: flex; flex-wrap: wrap; gap: 6px 16px; margin-top: 16px; font-size: 11.5px; color: var(--text-muted); }
        .cfg-leyenda i { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
      `}</style>
    </div>
  );
}
