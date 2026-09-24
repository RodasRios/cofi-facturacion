import { useRef, useState } from "react";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { uploadFirma } from "../api/auth";
import { useAuth } from "../contexts/AuthContext";

/**
 * Carga de la firma del usuario actual. Sale en la cotización FR-GC-08 que
 * él arma, sobre su nombre. Sin firma, el formato deja el espacio en blanco.
 */
export function MiFirma({ compacto = false }: { compacto?: boolean }) {
  const { user, refreshUser } = useAuth();
  const input = useRef<HTMLInputElement>(null);
  const [subiendo, setSubiendo] = useState(false);

  if (!user) return null;
  const tiene = !!user.firma_path;

  const subir = async (file: File) => {
    setSubiendo(true);
    try {
      await uploadFirma(file);
      await refreshUser();
      toast.success("Firma guardada — saldrá en las cotizaciones que armes");
    } catch {
      toast.error("No se pudo subir la firma. Usa PNG o JPG.");
    } finally {
      setSubiendo(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <div className={`mi-firma ${compacto ? "compacto" : ""} ${tiene ? "ok" : "falta"}`}>
      <Icon name={tiene ? "check_circle" : "draw"} size={16} />
      <span className="mi-firma-texto">
        {tiene
          ? "Tu firma está cargada y sale en tus cotizaciones."
          : "Sube tu firma para que salga en las cotizaciones que armes (PNG con fondo transparente, idealmente)."}
      </span>
      <button type="button" className="btn-secondary" disabled={subiendo} onClick={() => input.current?.click()}>
        <Icon name="upload" size={14} />{subiendo ? "Subiendo…" : tiene ? "Cambiar firma" : "Subir firma"}
      </button>
      <input ref={input} type="file" accept="image/png,image/jpeg" hidden
        onChange={e => e.target.files?.[0] && subir(e.target.files[0])} />

      <style>{`
        .mi-firma {
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
          padding: 10px 12px; margin-bottom: 14px; font-size: 12.5px; border: 1px solid;
        }
        .mi-firma-texto { flex: 1 1 240px; }
        .mi-firma .btn-secondary { white-space: nowrap; }
        .mi-firma.falta { background: #fffbeb; border-color: #fcd34d; color: #92400e; }
        .dark .mi-firma.falta { background: #2a1f05; border-color: #78580c; color: #fbbf24; }
        .mi-firma.ok { background: var(--bg-surface); border-color: var(--border); color: var(--text-secondary); }
      `}</style>
    </div>
  );
}
