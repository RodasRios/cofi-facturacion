import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import { rutaInicial } from "./lib/permisos";
import type { Permiso } from "./types";
import { DisponibilidadPage } from "./pages/DisponibilidadPage";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";
import { AppShell } from "./components/layout/AppShell";
import { LoginPage } from "./pages/LoginPage";
import { VinculacionPublicaPage } from "./pages/VinculacionPublicaPage";
import { PedidoPublicoPage } from "./pages/PedidoPublicoPage";
import { TableroPage } from "./pages/TableroPage";
import { ClientesPage } from "./pages/ClientesPage";
import { SolicitudesCotizacionPage } from "./pages/SolicitudesCotizacionPage";
import { CotizacionesPage } from "./pages/CotizacionesPage";
import { PagosPage } from "./pages/PagosPage";
import { OrdenesSuministroPage } from "./pages/OrdenesSuministroPage";
import { DespachosPage } from "./pages/DespachosPage";
import { AdminPage } from "./pages/AdminPage";
import { ConfiguracionPage } from "./pages/ConfiguracionPage";
import { PrimerIngresoPage } from "./pages/PrimerIngresoPage";

function Shell({ children, permisos }: { children: React.ReactNode; permisos?: Permiso[] }) {
  return <ProtectedRoute permisos={permisos}><AppShell>{children}</AppShell></ProtectedRoute>;
}

/** "/" lleva a la primera pestaña que el usuario tenga permitida. */
function Inicio() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user ? rutaInicial(user) : "/login"} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/primer-ingreso" element={<PrimerIngresoPage />} />

      {/* Pública: el cliente entra por el link que le manda el comercial, sin usuario */}
      <Route path="/vincular/:token" element={<VinculacionPublicaPage />} />
      <Route path="/pedir/:token" element={<PedidoPublicoPage />} />

      <Route path="/" element={<Inicio />} />
      <Route path="/tablero" element={<Shell permisos={["tablero"]}><TableroPage /></Shell>} />
      <Route path="/clientes" element={<Shell permisos={["clientes"]}><ClientesPage /></Shell>} />
      <Route path="/solicitudes" element={<Shell permisos={["solicitudes"]}><SolicitudesCotizacionPage /></Shell>} />
      <Route path="/cotizaciones" element={<Shell permisos={["cotizaciones", "aprobar_cotizaciones"]}><CotizacionesPage /></Shell>} />
      <Route path="/pagos" element={<Shell permisos={["pagos", "aprobar_pagos"]}><PagosPage /></Shell>} />
      <Route path="/ordenes-suministro" element={<Shell permisos={["ordenes"]}><OrdenesSuministroPage /></Shell>} />
      <Route path="/despachos" element={<Shell permisos={["despachos"]}><DespachosPage /></Shell>} />
      <Route path="/admin" element={<Shell permisos={["precios"]}><AdminPage /></Shell>} />
      <Route path="/disponibilidad" element={<Shell permisos={["disponibilidad"]}><DisponibilidadPage /></Shell>} />
      <Route path="/configuracion" element={<Shell><ConfiguracionPage /></Shell>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
