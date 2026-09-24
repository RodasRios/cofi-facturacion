import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

type Rect = { x: number; y: number; w: number; h: number };

/**
 * Recorte de una imagen antes de subirla (traído de cofi-gestor-insumos).
 * Sirve para la firma: la gente la fotografía en una hoja y hay que dejar solo
 * el trazo, o sale enorme y descentrada en la cotización.
 * Usa pointer events, así funciona con mouse y con el dedo.
 */
export function ImageCropper({ file, hint, onConfirm, onCancel }: {
  file: File;
  hint?: string;
  onConfirm: (blob: Blob) => void;
  onCancel: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  // Data URL y no createObjectURL: en modo estricto el efecto de limpieza
  // revocaba la URL y la imagen quedaba rota.
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const [display, setDisplay] = useState({ w: 0, h: 0 });
  const [sel, setSel] = useState<Rect>({ x: 10, y: 10, w: 200, h: 80 });
  const drag = useRef<{ handle: string; x: number; y: number; rect: Rect } | null>(null);

  useEffect(() => {
    const lector = new FileReader();
    lector.onload = () => setImgUrl(String(lector.result));
    lector.readAsDataURL(file);
    return () => lector.abort();
  }, [file]);

  const clamp = (r: Rect, b: { w: number; h: number }): Rect => {
    const w = Math.min(Math.max(20, r.w), b.w);
    const h = Math.min(Math.max(20, r.h), b.h);
    return { x: Math.max(0, Math.min(r.x, b.w - w)), y: Math.max(0, Math.min(r.y, b.h - h)), w, h };
  };

  const onLoad = () => {
    const img = imgRef.current;
    if (!img) return;
    const dw = img.offsetWidth, dh = img.offsetHeight;
    setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    setDisplay({ w: dw, h: dh });
    const sw = Math.round(dw * 0.7), sh = Math.round(dh * 0.5);
    setSel({ x: Math.round((dw - sw) / 2), y: Math.round((dh - sh) / 2), w: sw, h: sh });
  };

  const empezar = (e: React.PointerEvent, handle: string) => {
    e.preventDefault();
    e.stopPropagation();
    drag.current = { handle, x: e.clientX, y: e.clientY, rect: { ...sel } };
  };

  useEffect(() => {
    const mover = (e: PointerEvent) => {
      const d = drag.current;
      if (!d || !display.w) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      const r = { ...d.rect };
      if (d.handle === "move") { r.x += dx; r.y += dy; }
      if (d.handle.includes("n")) { r.y += dy; r.h -= dy; }
      if (d.handle.includes("s")) { r.h += dy; }
      if (d.handle.includes("w")) { r.x += dx; r.w -= dx; }
      if (d.handle.includes("e")) { r.w += dx; }
      setSel(clamp(r, display));
    };
    const soltar = () => { drag.current = null; };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
    return () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
    };
  }, [display]);

  const confirmar = () => {
    if (!natural.w || !display.w || !imgRef.current) return;
    const sx = natural.w / display.w, sy = natural.h / display.h;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(sel.w * sx);
    canvas.height = Math.round(sel.h * sy);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(imgRef.current, Math.round(sel.x * sx), Math.round(sel.y * sy),
      canvas.width, canvas.height, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(b => { if (b) onConfirm(b); }, "image/png");
  };

  const HANDLES: Record<string, React.CSSProperties> = {
    nw: { top: -6, left: -6, cursor: "nw-resize" }, ne: { top: -6, right: -6, cursor: "ne-resize" },
    sw: { bottom: -6, left: -6, cursor: "sw-resize" }, se: { bottom: -6, right: -6, cursor: "se-resize" },
    n: { top: -6, left: "calc(50% - 6px)", cursor: "n-resize" }, s: { bottom: -6, left: "calc(50% - 6px)", cursor: "s-resize" },
    w: { top: "calc(50% - 6px)", left: -6, cursor: "w-resize" }, e: { top: "calc(50% - 6px)", right: -6, cursor: "e-resize" },
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {hint && <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0 }}>{hint}</p>}
      <div style={{ position: "relative", display: "inline-block", alignSelf: "flex-start", userSelect: "none", lineHeight: 0, touchAction: "none" }}>
        {imgUrl && <img ref={imgRef} src={imgUrl} alt="Imagen a recortar" onLoad={onLoad} draggable={false}
          style={{ maxWidth: "100%", maxHeight: 320, display: "block" }} />}
        {display.w > 0 && (
          <div onPointerDown={e => empezar(e, "move")} style={{
            position: "absolute", left: sel.x, top: sel.y, width: sel.w, height: sel.h,
            border: "2px solid #3b82f6", boxShadow: "0 0 0 9999px rgba(0,0,0,0.5)",
            cursor: "move", boxSizing: "border-box",
          }}>
            {Object.entries(HANDLES).map(([id, style]) => (
              <div key={id} onPointerDown={e => empezar(e, id)} style={{
                position: "absolute", width: 12, height: 12, background: "#3b82f6",
                border: "1px solid #fff", ...style,
              }} />
            ))}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn-primary" onClick={confirmar}>
          <Icon name="crop" size={15} />Usar esta área
        </button>
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancelar</button>
      </div>
    </div>
  );
}
