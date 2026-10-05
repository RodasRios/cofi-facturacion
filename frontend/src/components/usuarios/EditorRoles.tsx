import { Icon } from "../ui/Icon";
import { ADMINISTRACION, PUESTOS, infoRol, rangoDeRoles, type RolInfo } from "../../lib/permisos";
import type { Permiso, RolClave } from "../../types";

/**
 * Elegir los roles de una persona (traído de cofi-gestor-insumos).
 *
 * - **Administración: una opción o ninguna.** Ya incluye todo lo de los
 *   puestos, así que va sola.
 * - **Puestos: los que hagan falta.** La misma persona puede ser Comercial y
 *   Logística, o Despacho y Disponibilidad.
 *
 * Lo que quien edita no puede dar (un rol de su rango o superior, o permisos
 * que él no tiene) se ve atenuado con la razón, en vez de dejar marcar algo
 * que el servidor va a rechazar.
 */
export function EditorRoles({ value, onChange, rangoActor, permisosActor, deshabilitado }: {
  value: RolClave[];
  onChange: (roles: RolClave[]) => void;
  rangoActor: number;
  permisosActor: Permiso[];
  deshabilitado?: string;
}) {
  const nivel = value.find(r => ADMINISTRACION.some(a => a.clave === r));
  const puestos = value.filter(r => PUESTOS.some(p => p.clave === r));

  const bloqueo = (r: RolInfo): string | null => {
    if (deshabilitado) return deshabilitado;
    if (rangoActor < 3 && rangoDeRoles([r.clave]) >= rangoActor) return "Solo alguien de rango superior lo asigna.";
    if (rangoActor < 2 && r.permisos.some(p => !permisosActor.includes(p))) return "Incluye permisos que tú no tienes.";
    return null;
  };

  return (
    <div className="er">
      <fieldset>
        <legend>Administración <span>· una sola opción</span></legend>
        <Opcion tipo="radio" marcada={!nivel} titulo="Ninguna" desc="Trabaja con los puestos que marques abajo."
          bloqueada={deshabilitado ?? null} onClick={() => onChange(puestos)} />
        {ADMINISTRACION.map(r => {
          const b = nivel === r.clave ? (deshabilitado ?? null) : bloqueo(r);
          return <Opcion key={r.clave} tipo="radio" marcada={nivel === r.clave} titulo={r.label} desc={b ?? r.desc}
            color={r.color} bloqueada={b} onClick={() => onChange([r.clave])} />;
        })}
      </fieldset>
      <fieldset>
        <legend>Puestos <span>· {nivel ? `ya incluidos en ${infoRol(nivel).label}` : "puedes marcar varios"}</span></legend>
        <div className="er-puestos">
          {PUESTOS.map(r => {
            const b = nivel ? "Incluido en el nivel de administración." : bloqueo(r);
            const marcada = !!nivel || puestos.includes(r.clave);
            return <Opcion key={r.clave} tipo="check" marcada={marcada} titulo={r.label} desc={b && !nivel ? b : r.desc}
              color={r.color} bloqueada={b}
              onClick={() => onChange(puestos.includes(r.clave) ? puestos.filter(x => x !== r.clave) : [...puestos, r.clave])} />;
          })}
        </div>
      </fieldset>
      <style>{`
        .er { display: grid; gap: 14px; }
        .er fieldset { border: none; margin: 0; padding: 0; display: grid; gap: 6px; }
        .er legend { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; color: var(--text-secondary); margin-bottom: 6px; padding: 0; }
        .er legend span { font-weight: 500; text-transform: none; letter-spacing: 0; color: var(--text-muted); }
        .er-puestos { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 6px; }
        .er-op { display: flex; align-items: flex-start; gap: 9px; text-align: left; font: inherit; padding: 8px 10px; cursor: pointer;
          background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-primary); }
        .er-op[aria-disabled="true"] { cursor: default; opacity: .55; }
        .er-op b { display: block; font-size: 13px; }
        .er-op small { display: block; font-size: 11.5px; color: var(--text-muted); line-height: 1.4; }
      `}</style>
    </div>
  );
}

function Opcion({ tipo, marcada, titulo, desc, color, bloqueada, onClick }: {
  tipo: "radio" | "check"; marcada: boolean; titulo: string; desc: string; color?: string;
  bloqueada: string | null; onClick: () => void;
}) {
  const icono = tipo === "radio"
    ? (marcada ? "radio_button_checked" : "radio_button_unchecked")
    : (marcada ? "check_box" : "check_box_outline_blank");
  const c = color ?? "var(--accent)";
  return (
    <button type="button" className="er-op" role={tipo === "radio" ? "radio" : "checkbox"} aria-checked={marcada}
      aria-disabled={!!bloqueada} title={bloqueada ?? undefined} onClick={() => !bloqueada && onClick()}
      style={marcada && !bloqueada ? { borderColor: c, background: color ? `${color}12` : "var(--accent-light)" } : undefined}>
      <Icon name={icono} size={18} style={{ color: marcada ? c : "var(--text-muted)", flexShrink: 0, marginTop: 1 }} />
      <span><b>{titulo}</b><small>{desc}</small></span>
    </button>
  );
}
