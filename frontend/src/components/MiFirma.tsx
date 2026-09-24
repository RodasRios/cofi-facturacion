import { Link } from "react-router-dom";
import { Icon } from "./ui/Icon";

/**
 * Aviso para quien arma cotizaciones sin firma cargada. La carga (con recorte)
 * y los datos que van bajo la firma están en Configuración.
 */
export function MiFirma() {
  return (
    <div className="mi-firma">
      <Icon name="draw" size={16} />
      <span className="mi-firma-texto">
        Sube tu firma y completa tu cédula y cargo para que salgan en las cotizaciones que armes.
      </span>
      <Link to="/configuracion?tab=firma" className="btn-secondary">
        <Icon name="upload" size={14} />Subir firma
      </Link>

      <style>{`
        .mi-firma {
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
          padding: 10px 12px; margin-bottom: 14px; font-size: 12.5px; border: 1px solid;
          background: #fffbeb; border-color: #fcd34d; color: #92400e;
        }
        .dark .mi-firma { background: #2a1f05; border-color: #78580c; color: #fbbf24; }
        .mi-firma-texto { flex: 1 1 240px; }
        .mi-firma .btn-secondary { white-space: nowrap; text-decoration: none; }
      `}</style>
    </div>
  );
}
