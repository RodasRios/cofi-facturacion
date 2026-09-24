import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getUsuarios, actualizarUsuario } from "../api/usuarios";
import type { User } from "../types";

const ROL_LABEL: Record<User["rol"], string> = {
  comercial: "Comercial", aprobador: "Aprobador", financiera: "Financiera", planta: "Planta",
};

type Campo = "nombre" | "cargo" | "telefono";

/**
 * Nombre, cargo y teléfono de cada usuario: es lo que se imprime bajo la firma
 * en la cotización ("PAOLA ANDREA POSSO ORTIZ / Departamento Comercial / Cel."),
 * en el "Autorizó" de la orden y en Elaboró/Revisó del control de despachos.
 */
export function UsuariosAdmin() {
  const qc = useQueryClient();
  const { data: usuarios } = useQuery({ queryKey: ["usuarios"], queryFn: getUsuarios });

  const mut = useMutation({
    mutationFn: ({ id, campo, valor }: { id: number; campo: Campo; valor: string }) =>
      actualizarUsuario(id, { [campo]: valor || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["usuarios"] }); toast.success("Usuario actualizado"); },
    onError: () => toast.error("No se pudo actualizar el usuario"),
  });

  const celda = (u: User, campo: Campo, placeholder: string) => (
    <input
      className="input-base"
      style={{ width: "100%" }}
      defaultValue={u[campo] ?? ""}
      placeholder={placeholder}
      onBlur={e => {
        const valor = e.target.value.trim();
        if (valor !== (u[campo] ?? "")) mut.mutate({ id: u.id, campo, valor });
      }}
    />
  );

  return (
    <section className="card" style={{ padding: 16 }}>
      <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 4px" }}>Usuarios</h2>
      <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 12px" }}>
        El nombre, cargo y teléfono salen impresos bajo la firma en la cotización, la orden de
        suministro y el control de despachos. Cada usuario sube su propia firma desde Cotizaciones.
      </p>
      <table className="table-sharp">
        <thead>
          <tr><th>Usuario</th><th>Rol</th><th>Nombre completo</th><th>Cargo</th><th>Teléfono</th><th>Firma</th></tr>
        </thead>
        <tbody>
          {usuarios?.map(u => (
            <tr key={u.id} style={u.is_active ? undefined : { opacity: 0.55 }}>
              <td>{u.username}</td>
              <td>{ROL_LABEL[u.rol]}{u.is_admin && " · admin"}</td>
              <td>{celda(u, "nombre", "Paola Andrea Posso Ortiz")}</td>
              <td>{celda(u, "cargo", "Departamento Comercial")}</td>
              <td>{celda(u, "telefono", "312 834 2898")}</td>
              <td>{u.firma_path ? "Cargada" : <span style={{ color: "var(--text-muted)" }}>Sin firma</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
