import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useTheme } from "../../contexts/ThemeContext";
import { Icon } from "../ui/Icon";
import { NeuralBackground } from "../ui/NeuralBackground";

const NAV_ITEMS = [
  { path: "/clientes", icon: "groups", label: "Clientes" },
  { path: "/solicitudes", icon: "request_quote", label: "Solicitudes" },
  { path: "/cotizaciones", icon: "description", label: "Cotizaciones" },
  { path: "/pagos", icon: "payments", label: "Pagos" },
  { path: "/ordenes-suministro", icon: "local_shipping", label: "Órdenes" },
  { path: "/despachos", icon: "inventory", label: "Despachos" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => { logout(); navigate("/login"); };

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  return (
    <div className="app-shell">
      <NeuralBackground />

      <header className="app-header">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <img src="/logo.svg" alt="" style={{ height: 26, width: 26 }} />
            <span className="logo-text">Facturación</span>
          </Link>

          <div className="header-sep" />

          <nav className="header-nav">
            {NAV_ITEMS.map(item => (
              <Link
                key={item.path}
                to={item.path}
                className="nav-item"
                style={isActive(item.path) ? { color: "#fff", fontWeight: 600, borderLeft: "2px solid rgba(255,255,255,0.8)" } : {}}
              >
                <Icon name={item.icon} size={16} />
                <span>{item.label}</span>
              </Link>
            ))}
            {user?.is_admin && (
              <Link
                to="/admin"
                className="nav-item"
                style={isActive("/admin") ? { color: "#fff", fontWeight: 600, borderLeft: "2px solid rgba(255,255,255,0.8)" } : {}}
              >
                <Icon name="settings" size={16} />
                <span>Administración</span>
              </Link>
            )}
          </nav>
        </div>

        <div className="header-right">
          {user?.is_admin ? (
            <span className="admin-badge"><Icon name="admin_panel_settings" size={12} />admin</span>
          ) : (
            <span className="rol-badge">{user?.rol}</span>
          )}
          <span className="header-username">{user?.username}</span>

          <button onClick={toggleTheme} className="header-icon-btn" title={isDark ? "Tema claro" : "Tema oscuro"}>
            <Icon name={isDark ? "light_mode" : "dark_mode"} size={17} />
          </button>

          <div className="header-sep" />

          <button onClick={handleLogout} className="header-icon-btn" title="Cerrar sesión">
            <Icon name="logout" size={17} />
            <span className="header-btn-label">Salir</span>
          </button>
        </div>
      </header>

      <main className="app-main">
        <div className="main-inner">
          {children}
        </div>
      </main>

      <style>{`
        .app-shell {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          background: var(--bg-base);
          position: relative;
        }

        .app-header {
          position: relative;
          z-index: 10;
          background: var(--bg-header);
          border-bottom: 1px solid rgba(255,255,255,0.08);
          display: flex;
          align-items: stretch;
          justify-content: space-between;
          height: 42px;
          padding: 0 12px;
          box-shadow: 0 1px 6px rgba(0,0,0,0.25);
        }

        .header-left { display: flex; align-items: stretch; gap: 0; }

        .logo-link {
          display: flex;
          align-items: center;
          gap: 8px;
          text-decoration: none;
          padding: 0 12px 0 4px;
          opacity: 1;
          transition: opacity 0.15s;
        }
        .logo-link:hover { opacity: 0.85; }

        .logo-text { font-size: 14px; font-weight: 700; color: #fff; letter-spacing: -0.01em; }

        .header-sep { width: 1px; background: rgba(255,255,255,0.12); margin: 8px 6px; }

        .header-nav { display: flex; align-items: stretch; gap: 0; }

        .nav-item {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 0 14px;
          font-size: 12.5px;
          font-weight: 500;
          color: rgba(255,255,255,0.65);
          text-decoration: none;
          border-left: 2px solid transparent;
          transition: background 0.12s, color 0.12s, border-color 0.12s;
          white-space: nowrap;
        }
        .nav-item:hover { background: rgba(255,255,255,0.08); color: #fff; }

        .header-right { display: flex; align-items: center; gap: 6px; }

        .admin-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          background: #7c3aed;
          color: #fff;
          font-size: 10px;
          font-weight: 700;
          padding: 2px 8px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .rol-badge {
          display: inline-flex;
          align-items: center;
          background: rgba(255,255,255,0.12);
          color: rgba(255,255,255,0.8);
          font-size: 10px;
          font-weight: 700;
          padding: 2px 8px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .header-username { font-size: 12px; color: rgba(255,255,255,0.55); }

        .header-icon-btn {
          display: flex;
          align-items: center;
          gap: 5px;
          background: transparent;
          border: none;
          color: rgba(255,255,255,0.65);
          cursor: pointer;
          padding: 4px 8px;
          font-size: 12px;
          font-family: inherit;
          transition: background 0.12s, color 0.12s;
        }
        .header-icon-btn:hover { background: rgba(255,255,255,0.1); color: #fff; }

        .header-btn-label { font-size: 12px; }

        .app-main { flex: 1; position: relative; z-index: 1; padding: 20px 16px; }
        .main-inner { max-width: 1200px; margin: 0 auto; }
      `}</style>
    </div>
  );
}
