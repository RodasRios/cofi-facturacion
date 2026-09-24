import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { puede, rutaInicial } from "../../lib/permisos";
import type { Permiso } from "../../types";

export function ProtectedRoute({ children, permisos }: { children: React.ReactNode; permisos?: Permiso[] }) {
  const { user, loading } = useAuth();

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
      height: "100vh", color: "var(--text-muted)", fontSize: 13 }}>
      Cargando…
    </div>
  );

  if (!user) return <Navigate to="/login" replace />;
  // Contraseña temporal puesta por un administrador: primero hay que cambiarla.
  if (user.debe_cambiar_password) return <Navigate to="/primer-ingreso" replace />;
  // Sin permiso para esta pestaña: a la primera que sí tenga.
  if (permisos && !puede(user, ...permisos)) return <Navigate to={rutaInicial(user)} replace />;

  return <>{children}</>;
}
