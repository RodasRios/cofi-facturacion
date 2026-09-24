import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "../components/ui/Icon";
import { ImageCropper } from "../components/ui/ImageCropper";
import { useAuth } from "../contexts/AuthContext";
import { actualizarPerfil, cambiarPassword, uploadFirma, borrarFirma, getFirmaBlob } from "../api/auth";
import { getUsuarios, crearUsuario, actualizarUsuario, eliminarUsuario, type UsuarioDatos } from "../api/usuarios";
import { mensajeError } from "../lib/errores";
import type { Rol, User } from "../types";

const ROLES: { value: Rol; label: string; desc: string; color: string }[] = [
  { value: "comercial",  label: "Comercial",  desc: "Clientes, solicitudes, cotizaciones y pagos", color: "#2563eb" },
  { value: "aprobador",  label: "Aprobador",  desc: "Aprueba o rechaza cotizaciones",               color: "#7c3aed" },
  { value: "financiera", label: "Financiera", desc: "Aprueba o rechaza pagos",                      color: "#0891b2" },
  { value: "planta",     label: "Planta",     desc: "Notifica órdenes y registra despachos",        color: "#d97706" },
];

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

// ─── Usuarios (admin y superusuario) ─────────────────────────────────────────

/** Contraseña temporal legible (sin 0/O ni 1/l) para dictarla o mandarla por chat. */
function claveTemporal() {
  const abc = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const n = crypto.getRandomValues(new Uint32Array(10));
  return Array.from(n, x => abc[x % abc.length]).join("");
}

const VACIO: UsuarioDatos = { username: "", nombre: "", cedula: "", cargo: "", telefono: "", email: "", rol: "comercial", is_admin: false, is_superadmin: false };

function FormUsuario({ inicial, onCerrar }: { inicial: User | null; onCerrar: () => void }) {
  const qc = useQueryClient();
  const { user: yo } = useAuth();
  const esNuevo = !inicial;
  const [d, setD] = useState<UsuarioDatos>(() => inicial ? {
    username: inicial.username, nombre: inicial.nombre ?? "", cedula: inicial.cedula ?? "",
    cargo: inicial.cargo ?? "", telefono: inicial.telefono ?? "", email: inicial.email ?? "",
    rol: inicial.rol, is_admin: inicial.is_admin, is_superadmin: inicial.is_superadmin,
  } : { ...VACIO });
  const [clave] = useState(claveTemporal);
  const [creado, setCreado] = useState<{ username: string; clave: string } | null>(null);
  const set = (k: keyof UsuarioDatos, v: unknown) => setD(x => ({ ...x, [k]: v }));
  const esYo = inicial?.id === yo?.id;

  const mut = useMutation({
    mutationFn: () => {
      const limpio: UsuarioDatos = Object.fromEntries(Object.entries(d).map(([k, v]) =>
        [k, typeof v === "string" ? (v.trim() || (k === "username" ? "" : null)) : v]));
      if (!yo?.is_superadmin) { delete limpio.is_admin; delete limpio.is_superadmin; }
      return esNuevo ? crearUsuario({ ...limpio, password: clave }) : actualizarUsuario(inicial.id, limpio);
    },
    onSuccess: u => {
      qc.invalidateQueries({ queryKey: ["usuarios"] });
      if (esNuevo) setCreado({ username: u.username, clave });
      else { toast.success("Usuario actualizado"); onCerrar(); }
    },
    onError: e => toast.error(mensajeError(e, "No se pudo guardar el usuario")),
  });

  if (creado) return <ClaveEntregada titulo="Usuario creado" {...creado} onCerrar={onCerrar} />;

  return (
    <form className="cfg-panel" onSubmit={e => { e.preventDefault(); mut.mutate(); }}>
      <div className="cfg-panel-titulo">
        <h4>{esNuevo ? "Nuevo usuario" : `Editar ${inicial.username}`}</h4>
        <button type="button" className="btn-ghost" onClick={onCerrar} title="Cerrar"><Icon name="close" size={16} /></button>
      </div>
      <div className="cfg-form">
        <label>Usuario (para entrar)
          <input className="input-base" value={d.username} onChange={e => set("username", e.target.value)}
            placeholder="paola.posso" required autoFocus={esNuevo} />
        </label>
        <label>Nombre completo<input className="input-base" value={d.nombre ?? ""} onChange={e => set("nombre", e.target.value)} /></label>
        <label>Cédula<input className="input-base" value={d.cedula ?? ""} onChange={e => set("cedula", e.target.value)} /></label>
        <label>Cargo<input className="input-base" value={d.cargo ?? ""} onChange={e => set("cargo", e.target.value)} /></label>
        <label>Teléfono<input className="input-base" value={d.telefono ?? ""} onChange={e => set("telefono", e.target.value)} /></label>
        <label>Correo<input className="input-base" type="email" value={d.email ?? ""} onChange={e => set("email", e.target.value)} /></label>

        <fieldset className="cfg-ancho cfg-roles">
          <legend>Rol</legend>
          {ROLES.map(r => (
            <label key={r.value} className={d.rol === r.value ? "activo" : ""}>
              <input type="radio" name="rol" checked={d.rol === r.value} onChange={() => set("rol", r.value)} />
              <span><strong style={{ color: r.color }}>{r.label}</strong><small>{r.desc}</small></span>
            </label>
          ))}
        </fieldset>

        {yo?.is_superadmin && (
          <fieldset className="cfg-ancho cfg-privilegios">
            <legend>Permisos especiales</legend>
            <label>
              <input type="checkbox" checked={!!d.is_admin || !!d.is_superadmin} disabled={!!d.is_superadmin || esYo}
                onChange={e => set("is_admin", e.target.checked)} />
              <span><strong>Administrador</strong><small>Hace cualquier paso del flujo, maneja plantas, precios y usuarios normales.</small></span>
            </label>
            <label>
              <input type="checkbox" checked={!!d.is_superadmin} disabled={esYo}
                onChange={e => set("is_superadmin", e.target.checked)} />
              <span><strong>Superusuario</strong><small>Además crea, edita y elimina administradores.</small></span>
            </label>
            {esYo && <small className="cfg-meta">No puedes quitarte tus propios permisos.</small>}
          </fieldset>
        )}

        {esNuevo && (
          <p className="cfg-ancho cfg-meta">
            <Icon name="key" size={13} /> Se le asigna una contraseña temporal que verás al crear el usuario.
            Al entrar por primera vez, el sistema le pedirá cambiarla.
          </p>
        )}
      </div>
      <div className="cfg-acciones" style={{ justifyContent: "flex-end", marginTop: 12 }}>
        <button type="button" className="btn-secondary" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primary" disabled={mut.isPending}>
          <Icon name={esNuevo ? "person_add" : "save"} size={14} />
          {mut.isPending ? "Guardando…" : esNuevo ? "Crear usuario" : "Guardar cambios"}
        </button>
      </div>
    </form>
  );
}

function ClaveEntregada({ titulo, username, clave, onCerrar }: { titulo: string; username: string; clave: string; onCerrar: () => void }) {
  const texto = `Usuario: ${username}\nContraseña temporal: ${clave}\nIngresa en ${window.location.origin}`;
  return (
    <div className="cfg-panel cfg-clave">
      <div className="cfg-panel-titulo">
        <h4><Icon name="check_circle" size={16} /> {titulo}</h4>
        <button type="button" className="btn-ghost" onClick={onCerrar}><Icon name="close" size={16} /></button>
      </div>
      <p>Mándale estos datos. Es la única vez que se muestra la contraseña; al entrar deberá cambiarla.</p>
      <pre>{texto}</pre>
      <button className="btn-primary" onClick={() => { navigator.clipboard.writeText(texto); toast.success("Copiado"); }}>
        <Icon name="content_copy" size={14} />Copiar
      </button>
    </div>
  );
}

function Usuarios() {
  const qc = useQueryClient();
  const { user: yo } = useAuth();
  const { data: usuarios, isLoading } = useQuery({ queryKey: ["usuarios"], queryFn: getUsuarios });
  const [editando, setEditando] = useState<User | "nuevo" | null>(null);
  const [clave, setClave] = useState<{ username: string; clave: string } | null>(null);
  const [verInactivos, setVerInactivos] = useState(false);

  const puedeTocar = (u: User) => yo?.is_superadmin || !(u.is_admin || u.is_superadmin);

  const invalidar = () => qc.invalidateQueries({ queryKey: ["usuarios"] });
  const activar = useMutation({
    mutationFn: (u: User) => actualizarUsuario(u.id, { is_active: !u.is_active }),
    onSuccess: u => { invalidar(); toast.success(u.is_active ? "Usuario activado" : "Usuario desactivado: ya no puede entrar"); },
    onError: e => toast.error(mensajeError(e, "No se pudo actualizar")),
  });
  const restablecer = useMutation({
    mutationFn: ({ u, clave }: { u: User; clave: string }) => actualizarUsuario(u.id, { password: clave }),
    onSuccess: (u, { clave }) => { invalidar(); setClave({ username: u.username, clave }); },
    onError: e => toast.error(mensajeError(e, "No se pudo restablecer la contraseña")),
  });
  const eliminar = useMutation({
    mutationFn: (u: User) => eliminarUsuario(u.id),
    onSuccess: () => { invalidar(); toast.success("Usuario eliminado"); },
    onError: (e, u) => {
      const msg = mensajeError(e, "No se pudo eliminar");
      // Con documentos a su nombre no se borra: se ofrece desactivarlo.
      if ((e as { response?: { status?: number } }).response?.status === 409 && u.is_active) {
        if (confirm(`${msg}\n\n¿Desactivarlo ahora?`)) activar.mutate(u);
      } else toast.error(msg);
    },
  });

  const inactivos = (usuarios ?? []).filter(u => !u.is_active).length;
  const lista = (usuarios ?? []).filter(u => verInactivos || u.is_active);

  return (
    <div className="cfg-seccion cfg-seccion-ancha">
      <header className="cfg-header-fila">
        <div>
          <h3>Usuarios</h3>
          <p>
            {yo?.is_superadmin
              ? "Como superusuario puedes crear, editar y eliminar a cualquier usuario, incluidos los administradores."
              : "Puedes crear y editar usuarios normales. Los administradores solo los modifica el superusuario."}
          </p>
        </div>
        {!editando && (
          <button className="btn-primary" onClick={() => { setClave(null); setEditando("nuevo"); }}>
            <Icon name="person_add" size={15} />Nuevo usuario
          </button>
        )}
      </header>

      {clave && <ClaveEntregada titulo="Contraseña restablecida" {...clave} onCerrar={() => setClave(null)} />}
      {editando && (
        <FormUsuario key={editando === "nuevo" ? "nuevo" : editando.id}
          inicial={editando === "nuevo" ? null : editando} onCerrar={() => setEditando(null)} />
      )}

      <div className="cfg-tabla-wrap">
        <table className="table-sharp cfg-tabla">
          <thead>
            <tr><th>Usuario</th><th>Rol</th><th>Datos para la firma</th><th>Último ingreso</th><th /></tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} className="cfg-vacio">Cargando…</td></tr>}
            {lista.map(u => {
              const rol = ROLES.find(r => r.value === u.rol);
              const esYo = u.id === yo?.id;
              const tocable = puedeTocar(u);
              return (
                <tr key={u.id} className={u.is_active ? "" : "inactivo"}>
                  <td>
                    <strong>{u.nombre || u.username}</strong>
                    <span className="cfg-sub">@{u.username}{esYo && " · tú"}</span>
                  </td>
                  <td>
                    <span className="badge" style={{ background: `${rol?.color}1f`, color: rol?.color }}>{rol?.label}</span>
                    {u.is_superadmin
                      ? <span className="badge cfg-badge-super">superusuario</span>
                      : u.is_admin && <span className="badge cfg-badge-admin">admin</span>}
                    {!u.is_active && <span className="badge cfg-badge-off">inactivo</span>}
                    {u.debe_cambiar_password && u.is_active && (
                      <span className="badge cfg-badge-clave" title="Aún no ha cambiado la contraseña temporal">clave temporal</span>
                    )}
                  </td>
                  <td className="cfg-sub-celda">
                    {[u.cedula && `C.C. ${u.cedula}`, u.cargo, u.telefono, u.email].filter(Boolean).join(" · ") || <em>Sin datos</em>}
                    <span className="cfg-sub">{u.firma_path ? "✓ Firma cargada" : "Sin firma"}</span>
                  </td>
                  <td className="cfg-sub-celda nowrap">
                    {u.last_login ? new Date(u.last_login).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" }) : "Nunca"}
                  </td>
                  <td className="cfg-acciones-fila">
                    {tocable && (
                      <>
                        <button className="btn-ghost" title="Editar" onClick={() => { setClave(null); setEditando(u); }}>
                          <Icon name="edit" size={16} />
                        </button>
                        {!esYo && (
                          <>
                            <button className="btn-ghost" title="Restablecer contraseña"
                              onClick={() => confirm(`¿Asignar una contraseña temporal nueva a ${u.username}? La actual deja de servir.`)
                                && restablecer.mutate({ u, clave: claveTemporal() })}>
                              <Icon name="lock_reset" size={16} />
                            </button>
                            <button className="btn-ghost" title={u.is_active ? "Desactivar (no podrá entrar)" : "Activar"}
                              onClick={() => activar.mutate(u)}>
                              <Icon name={u.is_active ? "person_off" : "person_check"} size={16} />
                            </button>
                            <button className="btn-ghost" title="Eliminar" style={{ color: "#dc2626" }}
                              onClick={() => confirm(`¿Eliminar a ${u.username}? No se puede deshacer.`) && eliminar.mutate(u)}>
                              <Icon name="delete" size={16} />
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {inactivos > 0 && (
        <button className="btn-ghost" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setVerInactivos(v => !v)}>
          <Icon name={verInactivos ? "visibility_off" : "visibility"} size={14} />
          {verInactivos ? "Ocultar inactivos" : `Mostrar inactivos (${inactivos})`}
        </button>
      )}

      <div className="cfg-leyenda">
        {ROLES.map(r => <span key={r.value}><i style={{ background: r.color }} /><strong>{r.label}:</strong> {r.desc}</span>)}
        <span><i style={{ background: "#059669" }} /><strong>Admin:</strong> todo lo anterior, plantas, precios y usuarios</span>
        <span><i style={{ background: "#be123c" }} /><strong>Superusuario:</strong> además gestiona administradores</span>
      </div>
    </div>
  );
}

// ─── Página ──────────────────────────────────────────────────────────────────

type Tab = "cuenta" | "firma" | "usuarios";

export function ConfiguracionPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const esAdmin = !!user?.is_admin;
  const tabs: { key: Tab; icon: string; label: string }[] = [
    { key: "cuenta", icon: "account_circle", label: "Mi cuenta" },
    { key: "firma", icon: "draw", label: "Mi firma" },
    ...(esAdmin ? [{ key: "usuarios" as Tab, icon: "manage_accounts", label: "Usuarios" }] : []),
  ];
  const pedido = params.get("tab") as Tab | null;
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
        </nav>
        <div className="cfg-contenido">
          {tab === "cuenta" && <MiCuenta key={user?.id} />}
          {tab === "firma" && <MiFirmaSeccion />}
          {tab === "usuarios" && esAdmin && <Usuarios />}
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
        .cfg-nav button:hover { color: var(--text-primary); }
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
