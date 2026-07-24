import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { AppShell } from "./components/layout/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { ClientesPage } from "./pages/ClientesPage";
import { SolicitudesCotizacionPage } from "./pages/SolicitudesCotizacionPage";
import { CotizacionesPage } from "./pages/CotizacionesPage";
import { PagosPage } from "./pages/PagosPage";
import { OrdenesSuministroPage } from "./pages/OrdenesSuministroPage";
import { DespachosPage } from "./pages/DespachosPage";
import { AdminPage } from "./pages/AdminPage";

function Shell({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><AppShell>{children}</AppShell></ProtectedRoute>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/" element={<Navigate to="/solicitudes" replace />} />
      <Route path="/clientes" element={<Shell><ClientesPage /></Shell>} />
      <Route path="/solicitudes" element={<Shell><SolicitudesCotizacionPage /></Shell>} />
      <Route path="/cotizaciones" element={<Shell><CotizacionesPage /></Shell>} />
      <Route path="/pagos" element={<Shell><PagosPage /></Shell>} />
      <Route path="/ordenes-suministro" element={<Shell><OrdenesSuministroPage /></Shell>} />
      <Route path="/despachos" element={<Shell><DespachosPage /></Shell>} />
      <Route path="/admin" element={<Shell><AdminPage /></Shell>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
