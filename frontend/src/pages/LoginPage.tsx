import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { NeuralBackground } from "../components/ui/NeuralBackground";
import { Icon } from "../components/ui/Icon";

export function LoginPage() {
  const { login } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      navigate("/");
    } catch {
      setError("Usuario o contraseña incorrectos");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-root">
      <NeuralBackground />

      <button onClick={toggleTheme} className="login-theme-toggle" title={isDark ? "Tema claro" : "Tema oscuro"}>
        <Icon name={isDark ? "light_mode" : "dark_mode"} size={18} />
      </button>

      <div className="login-panel">
        <div className="login-brand">
          <img src="/logo.svg" alt="" className="login-logo" />
          <div>
            <h1 className="login-title">COFI Facturación</h1>
            <p className="login-subtitle">Triturados y Concretos Ltda</p>
          </div>
        </div>

        <div className="login-divider" />

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-field">
            <label className="form-label">Usuario</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-base login-input"
              required
              autoFocus
              autoComplete="username"
            />
          </div>
          <div className="form-field">
            <label className="form-label">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-base login-input"
              required
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="login-error">
              <Icon name="error" size={14} />
              {error}
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary login-btn">
            {loading ? (
              <><Icon name="sync" size={15} className="spin" />Ingresando…</>
            ) : (
              <><Icon name="login" size={15} />Ingresar</>
            )}
          </button>
        </form>
      </div>

      <style>{`
        .login-root { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-base); position: relative; }
        .login-theme-toggle {
          position: fixed; top: 14px; right: 14px; z-index: 20;
          background: var(--bg-surface); border: 1px solid var(--border); color: var(--text-secondary);
          cursor: pointer; padding: 6px 8px; display: flex; align-items: center; transition: background 0.15s, color 0.15s;
        }
        .login-theme-toggle:hover { background: var(--bg-surface-2); color: var(--text-primary); }
        .login-panel { position: relative; z-index: 10; background: var(--bg-surface); border: 1px solid var(--border); box-shadow: var(--shadow-md); width: 340px; padding: 28px 28px 24px; }
        .login-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .login-logo { width: 40px; height: 40px; flex-shrink: 0; }
        .login-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0; letter-spacing: -0.02em; }
        .login-subtitle { font-size: 12px; color: var(--text-muted); margin: 2px 0 0; }
        .login-divider { height: 1px; background: var(--border); margin-bottom: 20px; }
        .login-form { display: flex; flex-direction: column; gap: 14px; }
        .form-field { display: flex; flex-direction: column; gap: 5px; }
        .form-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
        .login-input { width: 100%; }
        .login-error { display: flex; align-items: center; gap: 6px; background: #fef2f2; border: 1px solid #fca5a5; color: #dc2626; font-size: 12px; padding: 6px 10px; }
        .dark .login-error { background: #2d0f0f; border-color: #7f1d1d; color: #f87171; }
        .login-btn { width: 100%; justify-content: center; padding: 8px 14px; font-size: 13px; margin-top: 4px; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}
