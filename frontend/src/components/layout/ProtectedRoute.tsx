import { Navigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
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

  return <>{children}</>;
}
