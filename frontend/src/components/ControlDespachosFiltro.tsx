import { useState } from "react";
import { Icon } from "./ui/Icon";
import { urlControlDespachos } from "../api/controlDespachos";
import type { Cliente } from "../types";

/**
 * Rango y obra para armar el control de despacho de materiales de un cliente.
 * El PDF no se guarda: se arma con lo que se pida y se abre en el visor.
 */
export function ControlDespachosFiltro({ cliente, onVer }: {
  cliente: Cliente;
  onVer: (url: string, filename: string) => void;
}) {
  const hoy = new Date();
  const primeroDelMes = new Date(hoy.getFullYear(), hoy.getMonth(), 1).toISOString().slice(0, 10);
  const [desde, setDesde] = useState(primeroDelMes);
  const [hasta, setHasta] = useState(hoy.toISOString().slice(0, 10));
  const [obra, setObra] = useState("");

  return (
    <form
      className="ctrl-desp"
      onSubmit={(e) => {
        e.preventDefault();
        onVer(
          urlControlDespachos({ cliente: cliente.id, desde, hasta, obra: obra.trim() || undefined }),
          `Control despachos ${cliente.nombre}.pdf`,
        );
      }}
    >
      <div>
        <label className="section-label">Desde</label>
        <input className="input-base" type="date" value={desde} onChange={e => setDesde(e.target.value)} />
      </div>
      <div>
        <label className="section-label">Hasta</label>
        <input className="input-base" type="date" value={hasta} onChange={e => setHasta(e.target.value)} />
      </div>
      <div>
        <label className="section-label">Obra (opcional)</label>
        <input className="input-base" value={obra} placeholder="Todas" onChange={e => setObra(e.target.value)} />
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button type="submit" className="btn-primary">
          <Icon name="picture_as_pdf" size={14} />Ver control de despachos
        </button>
      </div>

      <style>{`
        .ctrl-desp {
          display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
          gap: 10px; padding: 12px 14px; align-items: end;
        }
        .ctrl-desp .input-base { width: 100%; }
      `}</style>
    </form>
  );
}
