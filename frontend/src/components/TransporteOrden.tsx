import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { actualizarOrdenSuministro } from "../api/ordenesSuministro";
import type { OrdenSuministro } from "../types";

/**
 * Datos de retiro de una orden: fecha de suministro, placas y observación.
 *
 * Se conocen después de emitida la orden — el cliente avisa qué vehículos
 * manda — y la planta solo deja entrar las placas que figuran en el formato,
 * así que al guardar se regenera el PDF.
 */
export function TransporteOrden({ orden, onGuardado }: { orden: OrdenSuministro; onGuardado?: () => void }) {
  const qc = useQueryClient();
  const [fecha, setFecha] = useState(orden.fecha_suministro ?? "");
  const [cliente, setCliente] = useState(orden.placas_cliente ?? "");
  const [empresa, setEmpresa] = useState(orden.placas_empresa ?? "");
  const [obs, setObs] = useState(orden.notas ?? "");

  const guardar = useMutation({
    mutationFn: () => actualizarOrdenSuministro(orden.id, {
      fecha_suministro: fecha || null,
      placas_cliente: cliente,
      placas_empresa: empresa,
      notas: obs,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ordenes-suministro"] });
      toast.success("Orden actualizada — el formato ya refleja los cambios");
      onGuardado?.();
    },
    onError: () => toast.error("No se pudo actualizar la orden"),
  });

  return (
    <form
      className="transporte"
      onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}
    >
      <div>
        <label className="section-label">Fecha de suministro</label>
        <input className="input-base" type="date" value={fecha} onChange={e => setFecha(e.target.value)} />
      </div>
      <div>
        <label className="section-label">Placas del cliente</label>
        <input className="input-base" value={cliente} placeholder="SPT880, WMB006"
          onChange={e => setCliente(e.target.value.toUpperCase())} />
      </div>
      <div>
        <label className="section-label">Placas Triturados y Concretos</label>
        <input className="input-base" value={empresa} placeholder="Si el transporte es propio"
          onChange={e => setEmpresa(e.target.value.toUpperCase())} />
      </div>
      <div className="transporte-obs">
        <label className="section-label">Observación</label>
        <input className="input-base" value={obs} onChange={e => setObs(e.target.value)} />
      </div>
      <div className="transporte-acciones">
        <button type="submit" className="btn-primary" disabled={guardar.isPending}>
          <Icon name="save" size={14} />{guardar.isPending ? "Guardando…" : "Guardar"}
        </button>
      </div>

      <style>{`
        .transporte {
          display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 10px; padding: 12px 14px; align-items: end;
        }
        .transporte .input-base { width: 100%; }
        .transporte-obs { grid-column: 1 / -2; }
        @media (max-width: 700px) { .transporte-obs { grid-column: 1 / -1; } }
        .transporte-acciones { display: flex; justify-content: flex-end; }
      `}</style>
    </form>
  );
}
