import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { CambiarPassword } from "./ConfiguracionPage";

/**
 * La contraseña la asignó un administrador (alta o restablecimiento): antes
 * de usar la app, el usuario pone una que solo él conozca.
 */
export function PrimerIngresoPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return <Navigate to="/login" replace />;
  if (!user.debe_cambiar_password) return <Navigate to="/" replace />;

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16, background: "var(--bg-base)" }}>
      <div className="card" style={{ width: "100%", maxWidth: 440, padding: 24 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 6px" }}>Hola{user.nombre ? `, ${user.nombre.split(" ")[0]}` : ""}</h1>
        <p style={{ fontSize: 12.5, color: "var(--text-muted)", margin: "0 0 18px" }}>
          Entraste con una contraseña temporal. Elige una nueva que solo tú conozcas para continuar.
        </p>
        <CambiarPassword primerIngreso onListo={() => navigate("/", { replace: true })} />
        <button className="btn-ghost" style={{ marginTop: 12, fontSize: 12 }} onClick={logout}>Salir</button>
      </div>
      <style>{`
        .cfg-form { display: grid; grid-template-columns: 1fr; gap: 12px; }
        .cfg-form > label { display: flex; flex-direction: column; gap: 4px; font-size: 11.5px; font-weight: 600; color: var(--text-secondary); }
        .cfg-form .input-base { width: 100%; }
        .cfg-acciones { display: flex; justify-content: flex-end; }
        .cfg-error { font-size: 12px; color: #dc2626; margin: 0; }
      `}</style>
    </div>
  );
}
