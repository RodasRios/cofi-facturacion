import { useState, useEffect } from "react";
import { Icon } from "./Icon";
import client from "../../api/client";

interface PdfViewerModalProps {
  url: string;          // ruta relativa a la API, ej: /cotizaciones/3/pdf/
  filename: string;     // nombre para la descarga
  onClose: () => void;
}

export function PdfViewerModal({ url, filename, onClose }: PdfViewerModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const isImage = filename.match(/\.(jpg|jpeg|png|webp)$/i);

  useEffect(() => {
    let objectUrl: string;
    client.get(url, { responseType: "blob" })
      .then(res => {
        const mime = isImage ? res.data.type || "image/jpeg" : "application/pdf";
        objectUrl = URL.createObjectURL(new Blob([res.data], { type: mime }));
        setBlobUrl(objectUrl);
      })
      .catch(() => setError("No se pudo cargar el archivo."))
      .finally(() => setLoading(false));

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  const handleDownload = () => {
    if (!blobUrl) return;
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    a.click();
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.7)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          display: "flex", flexDirection: "column",
          width: "min(860px, 96vw)",
          height: "min(92vh, 1100px)",
          boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        }}
      >
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-surface-2)",
          flexShrink: 0,
        }}>
          <Icon name={isImage ? "image" : "picture_as_pdf"} size={16} style={{ color: isImage ? "#2563eb" : "#dc2626" }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {filename}
          </span>
          <button
            onClick={handleDownload}
            disabled={!blobUrl}
            className="btn-ghost"
            style={{ fontSize: 12, padding: "4px 10px" }}
            title="Descargar"
          >
            <Icon name="download" size={15} /> Descargar
          </button>
          <button
            onClick={onClose}
            className="btn-ghost"
            style={{ padding: "4px 8px" }}
            title="Cerrar"
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        {/* Contenido */}
        <div style={{ flex: 1, overflow: "hidden", position: "relative", background: "#525659" }}>
          {loading && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", gap: 10 }}>
              <Icon name="hourglass_empty" size={20} />
              <span style={{ fontSize: 14 }}>{isImage ? "Cargando imagen…" : "Cargando PDF…"}</span>
            </div>
          )}
          {error && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#fca5a5", gap: 8, flexDirection: "column" }}>
              <Icon name="error" size={32} />
              <span style={{ fontSize: 14 }}>{error}</span>
            </div>
          )}
          {blobUrl && isImage && (
            <div style={{ width: "100%", height: "100%", overflow: "auto", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: 16 }}>
              <img src={blobUrl} alt={filename} style={{ maxWidth: "100%", height: "auto", display: "block" }} />
            </div>
          )}
          {blobUrl && !isImage && (
            <iframe
              src={blobUrl}
              style={{ width: "100%", height: "100%", border: "none", display: "block" }}
              title={filename}
            />
          )}
        </div>
      </div>
    </div>
  );
}
