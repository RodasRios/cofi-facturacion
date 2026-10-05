import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "../components/ui/Icon";
import { ChipsRoles } from "../components/usuarios/ChipsRoles";
import { EditorRoles } from "../components/usuarios/EditorRoles";
import { useAuth } from "../contexts/AuthContext";
import { getUsuarios, getPanelUsuarios, crearUsuario, actualizarUsuario, eliminarUsuario, type UsuarioDatos } from "../api/usuarios";
import { getPlantas } from "../api/plantas";
import { mensajeError } from "../lib/errores";
import { EXCLUSIVOS, PERMISOS, ROLES, permisosDeRoles, rangoDeRoles } from "../lib/permisos";
import type { Permiso, RolClave, User } from "../types";

/*
 * Panel de usuarios y permisos — el "panel de superadmin" de
 * cofi-gestor-insumos traído a facturación (una sola empresa).
 *
 *   Resumen   → ¿se puede trabar el flujo? (nadie aprueba pagos, gente sin rol…)
 *   Personas  → tabla con filtros; al hacer clic, panel lateral con todo lo de
 *               esa cuenta: datos, roles, permisos adicionales, plantas, acceso.
 *   Roles     → qué abre cada rol, en una matriz, y cuánta gente lo tiene.
 *
 * Lo usan el superusuario y los administradores (permiso `usuarios`); la
 * jerarquía (solo se gestiona hacia abajo) la valida el servidor, y aquí se
 * atenúa lo que no se puede tocar.
 */

const fecha = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("es-CO", { day: "2-digit", month: "short", year: "numeric" }) : "Nunca";

function hace(iso?: string | null) {
  if (!iso) return "Nunca ha entrado";
  const dias = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (dias <= 0) return "hoy";
  if (dias === 1) return "ayer";
  if (dias < 30) return `hace ${dias} días`;
  const meses = Math.floor(dias / 30);
  return meses === 1 ? "hace 1 mes" : `hace ${meses} meses`;
}

/** Contraseña temporal legible (sin 0/O ni 1/l) para dictarla o mandarla por chat. */
function claveTemporal() {
  const abc = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const n = crypto.getRandomValues(new Uint32Array(10));
  return Array.from(n, x => abc[x % abc.length]).join("");
}

const nombreDe = (u: User) => u.nombre || u.username;

/** Puede `yo` gestionar a `u`? Mismo criterio que user_views._objetivo. */
const gestionable = (yo: User | null, u: User) => !!yo && (yo.is_superadmin || u.rango < yo.rango);

function EstadoCuenta({ u }: { u: User }) {
  const [t, c, f, titulo] = !u.is_active
    ? ["Inactiva", "#991b1b", "#fee2e2", "No puede entrar"]
    : u.debe_cambiar_password
      ? ["Clave temporal", "#92400e", "#fef3c7", "Aún no ha cambiado la contraseña que se le asignó"]
      : ["Activa", "#166534", "#dcfce7", ""];
  return <span className="us-insignia" title={titulo} style={{ color: c, background: f }}>{t}</span>;
}

// ─── Resumen ─────────────────────────────────────────────────────────────────

function Resumen({ onFiltro }: { onFiltro: (f: { rol?: string; estado?: string; seccion?: string }) => void }) {
  const { data: p } = useQuery({ queryKey: ["usuarios-panel"], queryFn: getPanelUsuarios, refetchInterval: 60_000 });
  if (!p) return <div className="us-cifras us-cargando" />;
  const cifras = [
    { rotulo: "Personas activas", valor: p.activos, icono: "group" },
    { rotulo: "Administradores", valor: p.administradores, icono: "admin_panel_settings" },
    { rotulo: "Claves temporales", valor: p.clave_temporal, icono: "key" },
    { rotulo: "Esperando aprobación", valor: p.esperando_aprobacion.cotizaciones + p.esperando_aprobacion.pagos, icono: "approval",
      titulo: `${p.esperando_aprobacion.cotizaciones} cotizaciones · ${p.esperando_aprobacion.pagos} pagos` },
  ];
  const ESTILO = {
    grave: { borderColor: "#fca5a5", background: "#fef2f2", color: "#991b1b", icono: "gpp_bad" },
    aviso: { borderColor: "#fcd34d", background: "#fffbeb", color: "#92400e", icono: "badge" },
    info: { borderColor: "#bfdbfe", background: "#eff6ff", color: "#1e40af", icono: "key" },
  } as const;
  const accion = (tipo: string) =>
    tipo === "sin_rol" ? () => onFiltro({ rol: "sin_rol", seccion: "personas" })
      : tipo === "clave_temporal" ? () => onFiltro({ estado: "clave", seccion: "personas" })
        : () => onFiltro({ seccion: "roles" });

  return (
    <div style={{ marginBottom: 16 }}>
      <div className="us-cifras">
        {cifras.map(c => (
          <div key={c.rotulo} title={c.titulo}>
            <strong>{c.valor.toLocaleString("es-CO")}</strong>
            <span><Icon name={c.icono} size={13} /> {c.rotulo}</span>
          </div>
        ))}
      </div>
      {p.alertas.length > 0 && (
        <div className="us-alertas">
          {p.alertas.map(a => {
            const e = ESTILO[a.nivel];
            return (
              <button key={a.tipo} type="button" onClick={accion(a.tipo)} className="us-alerta"
                style={{ borderColor: e.borderColor, background: e.background, color: e.color }}>
                <Icon name={e.icono} size={15} />{a.texto}<span>· Ver</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Personas ────────────────────────────────────────────────────────────────

function Personas({ usuarios, cargando, filtroInicial, onGestionar }: {
  usuarios: User[]; cargando: boolean; filtroInicial: { rol: string; estado: string };
  onGestionar: (u: User) => void;
}) {
  const { user: yo } = useAuth();
  const { data: plantas } = useQuery({ queryKey: ["plantas"], queryFn: () => getPlantas() });
  const [busqueda, setBusqueda] = useState("");
  const [rol, setRol] = useState(filtroInicial.rol);
  const [estado, setEstado] = useState(filtroInicial.estado || "activas");

  const q = busqueda.trim().toLowerCase();
  const visibles = usuarios.filter(u =>
    (!q || [u.username, u.nombre, u.email, u.cargo, u.cedula].some(x => (x ?? "").toLowerCase().includes(q))) &&
    (!rol || (rol === "sin_rol" ? !u.is_superadmin && u.roles.length === 0 && u.permisos_extra.length === 0
      : rol === "superusuario" ? u.is_superadmin : u.roles.includes(rol as RolClave))) &&
    (!estado || (estado === "activas" && u.is_active) || (estado === "clave" && u.is_active && u.debe_cambiar_password)
      || (estado === "inactivas" && !u.is_active)),
  );
  const hayFiltros = !!(q || rol || estado !== "activas");

  return (
    <div>
      <div className="us-filtros">
        <input className="input-base" value={busqueda} onChange={e => setBusqueda(e.target.value)}
          placeholder="Buscar por nombre, usuario, correo, cargo o cédula…" style={{ flex: "1 1 240px" }} />
        <select className="input-base" value={rol} onChange={e => setRol(e.target.value)}>
          <option value="">Cualquier rol</option>
          <option value="superusuario">Superusuario</option>
          {ROLES.map(r => <option key={r.clave} value={r.clave}>{r.label}</option>)}
          <option value="sin_rol">Sin rol</option>
        </select>
        <select className="input-base" value={estado} onChange={e => setEstado(e.target.value)}>
          <option value="">Todas las cuentas</option>
          <option value="activas">Activas</option>
          <option value="clave">Con clave temporal</option>
          <option value="inactivas">Inactivas</option>
        </select>
        <span className="us-cuenta">
          {visibles.length} de {usuarios.length}
          {hayFiltros && <button className="btn-ghost" onClick={() => { setBusqueda(""); setRol(""); setEstado("activas"); }}>Limpiar</button>}
        </span>
      </div>

      <div className="us-tabla-wrap">
        <table className="table-sharp us-tabla">
          <thead><tr><th>Persona</th><th>Roles</th><th>Plantas</th><th>Estado</th><th>Último ingreso</th><th /></tr></thead>
          <tbody>
            {cargando && <tr><td colSpan={6} className="us-vacio">Cargando…</td></tr>}
            {!cargando && visibles.length === 0 && <tr><td colSpan={6} className="us-vacio">Nadie coincide con los filtros.</td></tr>}
            {visibles.map(u => {
              const puedo = gestionable(yo, u) || u.id === yo?.id;
              const nombresPlantas = (plantas ?? []).filter(p => u.plantas.includes(p.id)).map(p => p.nombre.replace("Planta ", ""));
              return (
                <tr key={u.id} className={`us-fila ${u.is_active ? "" : "inactiva"} ${puedo ? "clic" : ""}`}
                  onClick={() => puedo && onGestionar(u)}>
                  <td>
                    <strong>{nombreDe(u)}</strong>
                    <span className="us-sub">@{u.username}{u.id === yo?.id && " · tú"}{u.cargo && ` · ${u.cargo}`}</span>
                  </td>
                  <td><ChipsRoles roles={u.roles} superadmin={u.is_superadmin} extra={u.permisos_extra.length} /></td>
                  <td className="us-sub-celda">{u.rango > 0 ? "Todas" : nombresPlantas.join(", ") || "Todas"}</td>
                  <td><EstadoCuenta u={u} /></td>
                  <td className="us-sub-celda" title={u.last_login ? fecha(u.last_login) : undefined}>{hace(u.last_login)}</td>
                  <td style={{ textAlign: "right" }}>
                    {puedo ? (
                      <button className="btn-secondary us-btn" onClick={e => { e.stopPropagation(); onGestionar(u); }}>
                        <Icon name="manage_accounts" size={14} />Gestionar
                      </button>
                    ) : <span className="us-sub" title="Solo alguien de rango superior lo gestiona"><Icon name="lock" size={13} /></span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Roles: matriz ───────────────────────────────────────────────────────────

function MatrizRoles() {
  const { data: p } = useQuery({ queryKey: ["usuarios-panel"], queryFn: getPanelUsuarios });
  return (
    <div>
      <p className="us-ayuda">
        Qué abre cada rol. A una persona se le pueden combinar varios puestos y, si hace falta, sumarle permisos
        sueltos desde su ficha. <strong>Aprobar pagos</strong> no viene con ningún nivel de administración:
        se da con el rol Financiera o a propósito.
      </p>
      <div className="us-tabla-wrap">
        <table className="table-sharp us-matriz">
          <thead>
            <tr>
              <th>Permiso</th>
              {ROLES.map(r => (
                <th key={r.clave} title={r.desc}>
                  <i className="us-punto" style={{ background: r.color }} />{r.label}
                  <small>{p ? `${p.por_rol[r.clave] ?? 0} persona${(p.por_rol[r.clave] ?? 0) === 1 ? "" : "s"}` : ""}</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERMISOS.map(perm => (
              <tr key={perm.clave}>
                <td>
                  <strong>{perm.pestana}</strong>
                  <span className="us-sub">{perm.desc}{EXCLUSIVOS.includes(perm.clave) && <em> · exclusivo</em>}</span>
                </td>
                {ROLES.map(r => (
                  <td key={r.clave} className="us-celda">
                    {r.permisos.includes(perm.clave) ? <Icon name="check" size={16} style={{ color: r.color }} /> : <span>·</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="us-reglas">
        <li><strong>Superusuario</strong>: el dueño. Gestiona a todos, incluidos los administradores; siempre queda al menos uno.</li>
        <li><strong>Administrador nivel 1</strong>: gestiona a los de nivel 2 y a los puestos.</li>
        <li><strong>Administrador nivel 2</strong>: gestiona solo puestos, y no puede dar aprobaciones (no las tiene).</li>
        <li>Nadie se cambia sus propios roles ni se desactiva a sí mismo.</li>
      </ul>
    </div>
  );
}

// ─── Panel lateral: una persona ──────────────────────────────────────────────

const DE_PLANTA: Permiso[] = ["despachos", "disponibilidad", "ordenes"];

function ClaveEntregada({ titulo, username, clave }: { titulo: string; username: string; clave: string }) {
  const texto = `Usuario: ${username}\nContraseña temporal: ${clave}\nIngresa en ${window.location.origin}`;
  return (
    <div className="us-clave">
      <strong><Icon name="check_circle" size={16} /> {titulo}</strong>
      <p>Mándale estos datos. Es la única vez que se muestra la contraseña; al entrar deberá cambiarla.</p>
      <pre>{texto}</pre>
      <button className="btn-primary" onClick={() => { navigator.clipboard.writeText(texto); toast.success("Copiado"); }}>
        <Icon name="content_copy" size={14} />Copiar
      </button>
    </div>
  );
}

function PanelPersona({ inicial, onCerrar }: { inicial: User | null; onCerrar: () => void }) {
  const qc = useQueryClient();
  const { user: yo, refreshUser } = useAuth();
  const { data: plantas } = useQuery({ queryKey: ["plantas"], queryFn: () => getPlantas() });
  const [u, setU] = useState<User | null>(inicial);
  const esNuevo = !u;
  const esYo = !!u && u.id === yo?.id;
  const rangoYo = yo?.rango ?? 0;

  const [d, setD] = useState(() => ({
    username: inicial?.username ?? "", nombre: inicial?.nombre ?? "", cedula: inicial?.cedula ?? "",
    cargo: inicial?.cargo ?? "", telefono: inicial?.telefono ?? "", email: inicial?.email ?? "",
  }));
  const [roles, setRoles] = useState<RolClave[]>(inicial?.roles ?? []);
  const [extra, setExtra] = useState<Permiso[]>(inicial?.permisos_extra ?? []);
  const [misPlantas, setMisPlantas] = useState<number[]>(inicial?.plantas ?? []);
  const [superadmin, setSuperadmin] = useState(!!inicial?.is_superadmin);
  const [clave, setClave] = useState<{ titulo: string; username: string; clave: string } | null>(null);
  const cuerpo = useRef<HTMLFormElement>(null);
  // La contraseña temporal se muestra arriba: que quede a la vista.
  useEffect(() => { if (clave) cuerpo.current?.scrollTo({ top: 0, behavior: "smooth" }); }, [clave]);

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [onCerrar]);

  const porRol = permisosDeRoles(superadmin ? ["admin"] : roles);
  const efectivos = new Set<Permiso>([...porRol, ...extra]);
  const rangoNuevo = rangoDeRoles(roles, superadmin);
  const conPlantas = rangoNuevo === 0 && DE_PLANTA.some(c => efectivos.has(c));
  const pestanas = [...new Set(PERMISOS.filter(p => efectivos.has(p.clave)).map(p => p.pestana))];

  const bloqueoRoles = esYo ? "No puedes cambiar tus propios roles." : superadmin ? "El superusuario tiene todo." : undefined;
  const bloqueoPermiso = (c: Permiso) =>
    bloqueoRoles ?? (rangoYo < 2 && !(yo?.permisos ?? []).includes(c) ? "No puedes dar un permiso que no tienes." : null);

  const invalidar = (nuevo?: User) => {
    if (nuevo) setU(nuevo);
    qc.invalidateQueries({ queryKey: ["usuarios"] });
    qc.invalidateQueries({ queryKey: ["usuarios-panel"] });
    if (nuevo?.id === yo?.id) refreshUser();
  };

  const guardar = useMutation({
    mutationFn: (): Promise<{ n: User; c: string | null }> => {
      const datos: UsuarioDatos = Object.fromEntries(Object.entries(d).map(([k, v]) =>
        [k, v.trim() || (k === "username" ? "" : null)])) as UsuarioDatos;
      if (!esYo) {
        Object.assign(datos, { roles, permisos_extra: extra.filter(c => !porRol.has(c)), plantas: conPlantas ? misPlantas : [] });
        if (yo?.is_superadmin) datos.is_superadmin = superadmin;
      }
      if (esNuevo) {
        const c = claveTemporal();
        return crearUsuario({ ...datos, password: c }).then(n => ({ n, c }));
      }
      return actualizarUsuario(u!.id, datos).then(n => ({ n, c: null }));
    },
    onSuccess: ({ n, c }) => {
      invalidar(n);
      if (c) setClave({ titulo: "Usuario creado", username: n.username, clave: c });
      else toast.success("Cambios guardados");
    },
    onError: e => toast.error(mensajeError(e, "No se pudo guardar")),
  });
  const activar = useMutation({
    mutationFn: () => actualizarUsuario(u!.id, { is_active: !u!.is_active }),
    onSuccess: n => { invalidar(n); toast.success(n.is_active ? "Cuenta activada" : "Cuenta desactivada: ya no puede entrar"); },
    onError: e => toast.error(mensajeError(e, "No se pudo actualizar")),
  });
  const restablecer = useMutation({
    mutationFn: (c: string) => actualizarUsuario(u!.id, { password: c }).then(n => ({ n, c })),
    onSuccess: ({ n, c }) => { invalidar(n); setClave({ titulo: "Contraseña restablecida", username: n.username, clave: c }); },
    onError: e => toast.error(mensajeError(e, "No se pudo restablecer")),
  });
  const eliminar = useMutation({
    mutationFn: () => eliminarUsuario(u!.id),
    onSuccess: () => { invalidar(); toast.success("Usuario eliminado"); onCerrar(); },
    onError: e => {
      const msg = mensajeError(e, "No se pudo eliminar");
      if ((e as { response?: { status?: number } }).response?.status === 409 && u?.is_active) {
        if (confirm(`${msg}\n\n¿Desactivarlo ahora?`)) activar.mutate();
      } else toast.error(msg);
    },
  });

  const sinAcceso = !superadmin && efectivos.size === 0;

  return createPortal(
    <>
      <div className="us-velo" onClick={onCerrar} />
      <aside className="us-lateral" role="dialog" aria-label={esNuevo ? "Nuevo usuario" : `Gestionar a ${u!.username}`}>
        <header>
          <div>
            <h3>{esNuevo ? "Nuevo usuario" : nombreDe(u!)}</h3>
            {u && <p>@{u.username} · desde el {fecha(u.created_at)} · último ingreso: {hace(u.last_login).toLowerCase()}</p>}
            {u && <div className="us-chips"><ChipsRoles roles={u.roles} superadmin={u.is_superadmin} extra={u.permisos_extra.length} /><EstadoCuenta u={u} /></div>}
          </div>
          <button className="btn-ghost" onClick={onCerrar} aria-label="Cerrar"><Icon name="close" size={20} /></button>
        </header>

        <form ref={cuerpo} className="us-cuerpo" id="form-persona" onSubmit={e => { e.preventDefault(); guardar.mutate(); }}>
          {clave && <ClaveEntregada {...clave} />}

          <section>
            <h4>Datos</h4>
            <div className="us-grid">
              <label>Usuario (para entrar)
                <input className="input-base" value={d.username} required autoFocus={esNuevo}
                  onChange={e => setD(x => ({ ...x, username: e.target.value }))} placeholder="paola.posso" />
              </label>
              <label>Nombre completo<input className="input-base" value={d.nombre} onChange={e => setD(x => ({ ...x, nombre: e.target.value }))} /></label>
              <label>Cédula<input className="input-base" value={d.cedula} onChange={e => setD(x => ({ ...x, cedula: e.target.value }))} /></label>
              <label>Cargo<input className="input-base" value={d.cargo} onChange={e => setD(x => ({ ...x, cargo: e.target.value }))} /></label>
              <label>Teléfono<input className="input-base" value={d.telefono} onChange={e => setD(x => ({ ...x, telefono: e.target.value }))} /></label>
              <label>Correo<input className="input-base" type="email" value={d.email} onChange={e => setD(x => ({ ...x, email: e.target.value }))} /></label>
            </div>
          </section>

          <section>
            <h4>Roles</h4>
            {yo?.is_superadmin && !esYo && (
              <label className="us-super">
                <input type="checkbox" checked={superadmin} onChange={e => setSuperadmin(e.target.checked)} />
                <span><strong>Superusuario</strong><small>Dueño del sistema: gestiona a todos, incluidos los administradores.</small></span>
              </label>
            )}
            <EditorRoles value={superadmin ? ["admin"] : roles} onChange={setRoles} rangoActor={rangoYo}
              permisosActor={yo?.permisos ?? []} deshabilitado={bloqueoRoles} />
          </section>

          <section>
            <h4>Permisos adicionales <span>· se suman a los de sus roles</span></h4>
            <div className="us-permisos">
              {PERMISOS.map(p => {
                const delRol = porRol.has(p.clave);
                const b = delRol ? "Ya lo tiene por su rol." : bloqueoPermiso(p.clave);
                return (
                  <label key={p.clave} className={delRol ? "del-rol" : b ? "bloqueado" : ""} title={b ?? undefined}>
                    <input type="checkbox" disabled={!!b} checked={efectivos.has(p.clave)}
                      onChange={() => setExtra(x => x.includes(p.clave) ? x.filter(c => c !== p.clave) : [...x, p.clave])} />
                    <span><strong>{p.pestana}</strong> {p.desc}
                      {delRol && <em> · por su rol</em>}
                      {!delRol && EXCLUSIVOS.includes(p.clave) && <em className="excl"> · exclusivo</em>}
                    </span>
                  </label>
                );
              })}
            </div>
            <p className={`us-resultado ${sinAcceso ? "vacio" : ""}`}>
              <Icon name={sinAcceso ? "visibility_off" : "visibility"} size={14} />
              {superadmin ? "Verá todas las pestañas." : sinAcceso ? "Sin roles ni permisos no verá ninguna pestaña." : `Verá: ${pestanas.join(" · ")}`}
            </p>
          </section>

          {conPlantas && (
            <section>
              <h4>Plantas <span>· sin marcar ninguna, trabaja con todas</span></h4>
              <div className="us-plantas">
                {plantas?.map(p => {
                  const on = misPlantas.includes(p.id);
                  return (
                    <button type="button" key={p.id} className={on ? "activo" : ""} disabled={esYo}
                      onClick={() => setMisPlantas(x => on ? x.filter(i => i !== p.id) : [...x, p.id])}>
                      <Icon name={on ? "check_box" : "check_box_outline_blank"} size={14} />{p.nombre.replace("Planta ", "")}
                    </button>
                  );
                })}
              </div>
              <small className="us-sub">Solo verá las órdenes, despachos y disponibilidad de las plantas marcadas.</small>
            </section>
          )}

          {esNuevo && (
            <p className="us-sub"><Icon name="key" size={13} /> Se le asigna una contraseña temporal que verás al crearlo. Al entrar, el sistema le pedirá cambiarla.</p>
          )}

          {u && !esYo && (
            <section>
              <h4>Acceso</h4>
              <div className="us-acceso">
                <span>{u.is_active ? "La cuenta puede entrar." : "La cuenta está desactivada y no puede entrar."}</span>
                <button type="button" className="btn-secondary" disabled={activar.isPending} onClick={() => activar.mutate()}>
                  <Icon name={u.is_active ? "person_off" : "person_check"} size={14} />{u.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
              <div className="us-acceso">
                <span>Asignar una contraseña temporal nueva (la actual deja de servir).</span>
                <button type="button" className="btn-secondary" disabled={restablecer.isPending}
                  onClick={() => confirm(`¿Asignar una contraseña temporal nueva a ${u.username}?`) && restablecer.mutate(claveTemporal())}>
                  <Icon name="lock_reset" size={14} />Restablecer
                </button>
              </div>
            </section>
          )}

          {u && !esYo && (
            <section className="us-peligro">
              <h4>Eliminar la cuenta</h4>
              <p>No se puede deshacer. Si ya armó o aprobó documentos no se borra: desactívala, así conserva su nombre en ellos.</p>
              <button type="button" className="btn-secondary" style={{ color: "#dc2626", borderColor: "#fca5a5" }} disabled={eliminar.isPending}
                onClick={() => prompt(`Para eliminar la cuenta escribe el usuario: ${u.username}`) === u.username && eliminar.mutate()}>
                <Icon name="delete_forever" size={14} />Eliminar definitivamente
              </button>
            </section>
          )}
        </form>

        <footer>
          <button type="button" className="btn-secondary" onClick={onCerrar}>{clave && esNuevo ? "Cerrar" : "Cancelar"}</button>
          {!(clave && esNuevo) && (
            <button className="btn-primary" form="form-persona" disabled={guardar.isPending || !d.username.trim()}>
              <Icon name={esNuevo ? "person_add" : "save"} size={14} />
              {guardar.isPending ? "Guardando…" : esNuevo ? "Crear usuario" : "Guardar cambios"}
            </button>
          )}
        </footer>
      </aside>
    </>,
    document.body,
  );
}

// ─── Página ──────────────────────────────────────────────────────────────────

type Seccion = "personas" | "roles";

export function UsuariosPage() {
  const { user: yo } = useAuth();
  const [params, setParams] = useSearchParams();
  const seccion: Seccion = params.get("seccion") === "roles" ? "roles" : "personas";
  const [filtro, setFiltro] = useState({ rol: "", estado: "", n: 0 });
  const [abierto, setAbierto] = useState<User | "nuevo" | null>(null);
  const { data: usuarios = [], isLoading } = useQuery({ queryKey: ["usuarios"], queryFn: getUsuarios });

  // El panel lateral sigue a la persona aunque la lista se recargue.
  const abiertoActual = useMemo(
    () => abierto === "nuevo" || !abierto ? abierto : usuarios.find(u => u.id === abierto.id) ?? abierto,
    [abierto, usuarios],
  );

  const SECCIONES: [Seccion, string, string, number | null][] = [
    ["personas", "group", "Personas", usuarios.length],
    ["roles", "table_view", "Roles y permisos", null],
  ];

  return (
    <div className="us">
      <div className="us-cabecera">
        <div>
          <span className="us-marca"><Icon name="shield_person" size={14} />{yo?.is_superadmin ? "Superusuario" : "Administración"}</span>
          <h1>Usuarios y permisos</h1>
        </div>
        <button className="btn-primary" onClick={() => setAbierto("nuevo")}><Icon name="person_add" size={15} />Nuevo usuario</button>
      </div>

      <Resumen onFiltro={f => {
        setFiltro(x => ({ rol: f.rol ?? "", estado: f.estado ?? "", n: x.n + 1 }));
        setParams(f.seccion ? { seccion: f.seccion } : {}, { replace: true });
      }} />

      <div role="tablist" className="us-tabs">
        {SECCIONES.map(([s, ic, rot, n]) => (
          <button key={s} role="tab" aria-selected={seccion === s} className={seccion === s ? "activo" : ""}
            onClick={() => setParams({ seccion: s }, { replace: true })}>
            <Icon name={ic} size={17} />{rot}{n != null && <span>{n}</span>}
          </button>
        ))}
      </div>

      {seccion === "personas" && (
        <Personas key={filtro.n} usuarios={usuarios} cargando={isLoading} filtroInicial={filtro}
          onGestionar={u => setAbierto(u)} />
      )}
      {seccion === "roles" && <MatrizRoles />}

      {abiertoActual && (
        <PanelPersona key={abiertoActual === "nuevo" ? "nuevo" : abiertoActual.id}
          inicial={abiertoActual === "nuevo" ? null : abiertoActual} onCerrar={() => setAbierto(null)} />
      )}

      <style>{`
        .us { max-width: 1240px; margin: 0 auto; }
        .us-cabecera { display: flex; justify-content: space-between; align-items: flex-end; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .us-cabecera h1 { font-size: 20px; font-weight: 700; margin: 2px 0 0; letter-spacing: -0.02em; }
        .us-marca { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: #be123c; }
        .us-cifras { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); }
        .us-cifras.us-cargando { height: 62px; background: var(--bg-surface); }
        .us-cifras > div { background: var(--bg-surface); padding: 12px 14px; }
        .us-cifras strong { display: block; font-size: 22px; font-variant-numeric: tabular-nums; }
        .us-cifras span { font-size: 11.5px; color: var(--text-muted); display: flex; align-items: center; gap: 4px; }
        .us-alertas { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
        .us-alerta { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 12.5px; font-weight: 700; padding: 5px 10px; border: 1px solid; cursor: pointer; }
        .us-alerta span { font-weight: 500; }
        .dark .us-alerta { filter: brightness(.9); }
        .us-tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border); margin-bottom: 14px; overflow-x: auto; }
        .us-tabs button { display: flex; align-items: center; gap: 6px; background: transparent; border: none; border-bottom: 3px solid transparent;
          font: inherit; font-size: 14px; padding: 10px 14px 8px; cursor: pointer; color: var(--text-secondary); white-space: nowrap; }
        .us-tabs button.activo { border-bottom-color: var(--accent); color: var(--accent-text); font-weight: 700; }
        .us-tabs button span { font-size: 11.5px; color: var(--text-muted); }
        .us-filtros { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; }
        .us-cuenta { font-size: 12px; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px; }
        .us-tabla-wrap { overflow-x: auto; border: 1px solid var(--border); background: var(--bg-surface); }
        .us-tabla td { vertical-align: middle; font-size: 12.5px; }
        .us-fila.clic { cursor: pointer; }
        .us-fila.clic:hover td { background: var(--bg-surface-2); }
        .us-fila.inactiva { opacity: .55; }
        .us-sub { display: block; font-size: 11px; color: var(--text-muted); }
        .us-sub-celda { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }
        .us-vacio { text-align: center; padding: 20px; color: var(--text-muted); }
        .us-btn { font-size: 12px; white-space: nowrap; }
        .us-insignia { font-size: 10.5px; font-weight: 700; padding: 2px 7px; white-space: nowrap; }
        .us-ayuda { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 12px; max-width: 760px; }
        .us-matriz th { text-align: center; font-size: 11.5px; vertical-align: bottom; min-width: 92px; }
        .us-matriz th:first-child { text-align: left; min-width: 230px; }
        .us-matriz th small { display: block; font-weight: 400; color: var(--text-muted); font-size: 10.5px; }
        .us-matriz td { font-size: 12.5px; }
        .us-matriz em { color: #b45309; font-style: normal; font-weight: 600; }
        .us-punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
        .us-matriz th small { color: rgba(255,255,255,.65); }
        .us-celda { text-align: center; color: var(--text-muted); }
        .us-reglas { font-size: 12px; color: var(--text-secondary); margin: 12px 0 0; padding-left: 18px; line-height: 1.7; }

        .us-velo { position: fixed; inset: 0; background: rgba(0,0,0,.3); z-index: 950; }
        .us-lateral { position: fixed; top: 0; right: 0; bottom: 0; width: min(560px, 100vw); z-index: 951; display: flex; flex-direction: column;
          background: var(--bg-surface); border-left: 1px solid var(--border); box-shadow: -12px 0 32px rgba(0,0,0,.2); }
        .us-lateral > header { display: flex; align-items: flex-start; gap: 10px; padding: 14px 16px; border-bottom: 1px solid var(--border); }
        .us-lateral > header > div { flex: 1; min-width: 0; }
        .us-lateral h3 { margin: 0; font-size: 17px; }
        .us-lateral header p { margin: 2px 0 6px; font-size: 12px; color: var(--text-muted); }
        .us-chips { display: flex; gap: 6px; flex-wrap: wrap; }
        .us-cuerpo { flex: 1; overflow-y: auto; padding: 16px; display: grid; gap: 22px; align-content: start; }
        .us-cuerpo h4 { margin: 0 0 8px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--text-secondary); }
        .us-cuerpo h4 span { font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--text-muted); }
        .us-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        @media (max-width: 520px) { .us-grid { grid-template-columns: 1fr; } }
        .us-grid label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .us-grid .input-base { width: 100%; font-weight: 400; }
        .us-super { display: flex; gap: 8px; align-items: flex-start; padding: 8px 10px; margin-bottom: 10px; border: 1px solid #fecdd3; background: #be123c0d; font-size: 12.5px; cursor: pointer; }
        .us-super small { display: block; color: var(--text-muted); font-size: 11px; }
        .us-permisos { display: grid; gap: 4px; }
        .us-permisos label { display: flex; gap: 8px; align-items: flex-start; font-size: 12px; color: var(--text-secondary); cursor: pointer; padding: 3px 0; }
        .us-permisos label strong { color: var(--text-primary); margin-right: 3px; }
        .us-permisos label.del-rol { opacity: .7; cursor: default; }
        .us-permisos label.bloqueado { opacity: .45; cursor: default; }
        .us-permisos em { font-style: normal; color: var(--text-muted); }
        .us-permisos em.excl { color: #b45309; font-weight: 600; }
        .us-resultado { display: flex; gap: 6px; align-items: flex-start; font-size: 12px; margin: 10px 0 0; padding: 8px 10px;
          background: var(--bg-surface-2); color: var(--text-secondary); }
        .us-resultado.vacio { background: #fffbeb; color: #92400e; }
        .us-plantas { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
        .us-plantas button { display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px; font: inherit; font-size: 12px; cursor: pointer;
          border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-secondary); }
        .us-plantas button.activo { border-color: var(--accent); background: var(--accent-light); color: var(--accent-text); font-weight: 600; }
        .us-acceso { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12.5px; margin-bottom: 8px; }
        .us-acceso span { flex: 1; min-width: 200px; }
        .us-peligro { border: 1px solid #fca5a5; padding: 12px; }
        .us-peligro h4 { color: #991b1b; }
        .us-peligro p { font-size: 12px; margin: 0 0 8px; color: var(--text-secondary); }
        .us-clave { border: 1px solid #22c55e; background: #f0fdf4; color: #14532d; padding: 12px; }
        .dark .us-clave { background: #052e16; color: #bbf7d0; }
        .us-clave strong { display: flex; align-items: center; gap: 6px; font-size: 13.5px; }
        .us-clave p { font-size: 12px; margin: 4px 0 8px; }
        .us-clave pre { background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border); padding: 10px 12px; font-size: 13px; margin: 0 0 10px; white-space: pre-wrap; }
        .us-lateral > footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); background: var(--bg-surface-2); }
        @media (max-width: 760px) { .us-cifras { grid-template-columns: repeat(2, 1fr); } }
      `}</style>
    </div>
  );
}
