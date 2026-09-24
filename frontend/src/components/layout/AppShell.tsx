import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";
import { useTheme } from "../../contexts/ThemeContext";
import { Icon } from "../ui/Icon";
import { NeuralBackground } from "../ui/NeuralBackground";
import { NAV, puede, rutaInicial } from "../../lib/permisos";


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
          <Link to={rutaInicial(user)} className="logo-link">
            <img src="/logo.svg" alt="" style={{ height: 26, width: 26 }} />
            <span className="logo-text">Facturación</span>
          </Link>

          <div className="header-sep" />

          <nav className="header-nav">
            {NAV.filter(item => puede(user, ...item.permisos)).map(item => (
              <Link
                key={item.path}
                to={item.path}
                className="nav-item"
                title={item.label}
                style={isActive(item.path) ? { color: "#fff", fontWeight: 600, borderLeft: "2px solid rgba(255,255,255,0.8)" } : {}}
              >
                <Icon name={item.icon} size={16} />
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
        </div>

        <div className="header-right">
          {user?.is_superadmin ? (
            <span className="admin-badge" title="Superusuario"><Icon name="shield_person" size={13} /><span className="admin-badge-txt">superusuario</span></span>
          ) : user?.is_admin ? (
            <span className="admin-badge" title="Administrador"><Icon name="admin_panel_settings" size={13} /><span className="admin-badge-txt">admin</span></span>
          ) : (
            null
          )}
          <Link to="/configuracion" className="header-icon-btn header-user" title="Configuración: mis datos, firma y usuarios"
            style={isActive("/configuracion") ? { background: "rgba(255,255,255,0.12)" } : undefined}>
            <Icon name="settings" size={16} />
            <span className="header-username">{user?.nombre?.split(" ")[0] || user?.username}</span>
          </Link>

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
          padding: 0 11px;
          font-size: 12.5px;
          font-weight: 500;
          color: rgba(255,255,255,0.65);
          text-decoration: none;
          border-left: 2px solid transparent;
          transition: background 0.12s, color 0.12s, border-color 0.12s;
          white-space: nowrap;
        }
        .nav-item:hover { background: rgba(255,255,255,0.08); color: #fff; }
        /* Con muchas pestañas no caben los nombres: primero se va el texto del
           distintivo, después el de las pestañas (queda el ícono con su título). */
        @media (max-width: 1500px) { .admin-badge-txt { display: none; } }
        @media (max-width: 1340px) {
          .nav-item { padding: 0 8px; font-size: 12px; }
          .header-username, .header-btn-label { display: none; }
        }
        @media (max-width: 1180px) { .nav-item span:not(.material-symbols-outlined) { display: none; } .nav-item { padding: 0 12px; } }

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
        .header-user { text-decoration: none; gap: 6px; }

        .app-main { flex: 1; position: relative; z-index: 1; padding: 20px 16px; }
        .main-inner { max-width: 1200px; margin: 0 auto; }
      `}</style>
    </div>
  );
}
