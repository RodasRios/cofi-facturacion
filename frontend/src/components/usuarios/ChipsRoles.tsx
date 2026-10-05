import { infoRol } from "../../lib/permisos";

/** Los roles de una persona como etiquetas de color (idea de cofi-gestor-insumos). */
export function ChipsRoles({ roles, superadmin, extra = 0 }: { roles: string[]; superadmin?: boolean; extra?: number }) {
  if (superadmin) return <Chip texto="Superusuario" color="#be123c" titulo="Dueño del sistema: gestiona a todos, incluidos los administradores." />;
  return (
    <span className="chips-roles">
      {roles.map(r => { const i = infoRol(r); return <Chip key={r} texto={i.label} color={i.color} titulo={i.desc} />; })}
      {roles.length === 0 && extra === 0 && <Chip texto="Sin rol" color="#94a3b8" titulo="No ve ninguna pestaña." />}
      {extra > 0 && <Chip texto={`+${extra} permiso${extra > 1 ? "s" : ""}`} color="#64748b" titulo="Permisos adicionales a los de sus roles" />}
      <style>{`.chips-roles { display: inline-flex; flex-wrap: wrap; gap: 4px; align-items: center; }`}</style>
    </span>
  );
}

function Chip({ texto, color, titulo }: { texto: string; color: string; titulo?: string }) {
  return (
    <span title={titulo} style={{
      fontSize: 10, fontWeight: 700, padding: "2px 7px", textTransform: "uppercase", letterSpacing: "0.03em",
      whiteSpace: "nowrap", background: `${color}1f`, color,
    }}>{texto}</span>
  );
}
