import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getDisponibilidad, actualizarDisponibilidad, actualizarNotaPlanta } from "../api/disponibilidad";
import { Icon } from "../components/ui/Icon";
import { mensajeError } from "../lib/errores";
import { DISPONIBILIDAD } from "../lib/disponibilidad";
import type { Disponibilidad, MaterialPlantaPrecio, PlantaDisponibilidad } from "../types";


function hace(iso: string | null) {
  if (!iso) return "sin actualizar";
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "ahora";
  if (min < 60) return `hace ${min} min`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h} h`;
  return new Date(iso).toLocaleDateString("es-CO", { day: "2-digit", month: "short" });
}

function FilaMaterial({ mp, editable }: { mp: MaterialPlantaPrecio; editable: boolean }) {
  const qc = useQueryClient();
  const mut = useMutation({
    mutationFn: (d: Parameters<typeof actualizarDisponibilidad>[1]) => actualizarDisponibilidad(mp.id, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["disponibilidad"] }); qc.invalidateQueries({ queryKey: ["materiales"] }); },
    onError: e => toast.error(mensajeError(e, "No se pudo actualizar")),
  });

  return (
    <div className={`dp-fila ${mp.disponibilidad}`}>
      <div className="dp-material">
        <strong>{mp.material_nombre}</strong>
        <span className="dp-sub">
          {hace(mp.disponibilidad_actualizada_at)}
          {mp.disponibilidad_actualizada_por_nombre && ` · ${mp.disponibilidad_actualizada_por_nombre}`}
        </span>
      </div>
      <div className="dp-estados" role="radiogroup" aria-label={`Disponibilidad de ${mp.material_nombre}`}>
        {(Object.keys(DISPONIBILIDAD) as Disponibilidad[]).map(e => {
          const d = DISPONIBILIDAD[e];
          const activo = mp.disponibilidad === e;
          return (
            <button key={e} type="button" disabled={!editable || mut.isPending}
              className={activo ? "activo" : ""}
              style={activo ? { background: d.color, borderColor: d.color, color: "#fff" } : undefined}
              onClick={() => !activo && mut.mutate({ disponibilidad: e })}>
              <Icon name={d.icon} size={14} />{d.label}
            </button>
          );
        })}
      </div>
      <label className="dp-cantidad">
        <input className="input-base" type="number" min="0" step="0.5" disabled={!editable}
          key={`${mp.id}-${mp.cantidad_disponible}`}
          defaultValue={mp.cantidad_disponible == null ? "" : Number(mp.cantidad_disponible)}
          placeholder="Cantidad"
          onBlur={e => {
            const v = e.target.value.trim();
            const antes = mp.cantidad_disponible == null ? "" : String(Number(mp.cantidad_disponible));
            if (v !== antes) mut.mutate({ cantidad_disponible: v || null });
          }}
          onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
        <span>{mp.unidad_medida}</span>
      </label>
      <input className="input-base dp-nota" disabled={!editable} placeholder="Nota (p. ej. llega más el lunes)"
        key={`${mp.id}-nota-${mp.disponibilidad_nota}`} defaultValue={mp.disponibilidad_nota ?? ""}
        onBlur={e => { if (e.target.value.trim() !== (mp.disponibilidad_nota ?? "")) mut.mutate({ disponibilidad_nota: e.target.value }); }}
        onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
    </div>
  );
}

function TarjetaPlanta({ p }: { p: PlantaDisponibilidad }) {
  const qc = useQueryClient();
  const [nota, setNota] = useState(p.nota_disponibilidad ?? "");
  const guardarNota = useMutation({
    mutationFn: () => actualizarNotaPlanta(p.id, nota),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["disponibilidad"] }); toast.success("Aviso actualizado"); },
    onError: e => toast.error(mensajeError(e, "No se pudo guardar el aviso")),
  });
  const agotados = p.materiales.filter(m => m.disponibilidad === "agotada").length;
  const pocos = p.materiales.filter(m => m.disponibilidad === "limitada").length;

  return (
    <section className="card dp-planta">
      <header>
        <h2><Icon name="factory" size={17} />{p.nombre}</h2>
        <span className="dp-resumen">
          {agotados > 0 && <span style={{ color: DISPONIBILIDAD.agotada.color }}>{agotados} agotado{agotados > 1 ? "s" : ""}</span>}
          {pocos > 0 && <span style={{ color: DISPONIBILIDAD.limitada.color }}>{pocos} con poca</span>}
          {!agotados && !pocos && <span style={{ color: DISPONIBILIDAD.disponible.color }}>Todo disponible</span>}
        </span>
        {!p.editable && <span className="dp-sub">Solo lectura</span>}
      </header>

      <form className="dp-aviso" onSubmit={e => { e.preventDefault(); guardarNota.mutate(); }}>
        <Icon name="campaign" size={16} />
        <input className="input-base" value={nota} disabled={!p.editable} onChange={e => setNota(e.target.value)}
          placeholder="Aviso general de la planta: horario, cierres, báscula…" />
        {p.editable && nota !== (p.nota_disponibilidad ?? "") && (
          <button className="btn-secondary" disabled={guardarNota.isPending}>Guardar</button>
        )}
        {p.nota_actualizada_at && <span className="dp-sub">{hace(p.nota_actualizada_at)}</span>}
      </form>

      <div className="dp-lista">
        {p.materiales.map(mp => <FilaMaterial key={mp.id} mp={mp} editable={p.editable} />)}
        {p.materiales.length === 0 && <p className="dp-sub" style={{ padding: 10 }}>Esta planta no tiene materiales con precio.</p>}
      </div>
    </section>
  );
}

export function DisponibilidadPage() {
  const [soloMias, setSoloMias] = useState(true);
  const { data: plantas, isLoading } = useQuery({
    queryKey: ["disponibilidad", soloMias],
    queryFn: () => getDisponibilidad(soloMias),
    refetchInterval: 60_000,
  });
  const hayAjenas = plantas?.some(p => !p.editable);

  return (
    <div className="dp">
      <div className="dp-cabecera">
        <div>
          <h1>Disponibilidad</h1>
          <p>Lo que marques aquí lo ve el área comercial al cotizar. Se guarda solo al cambiarlo.</p>
        </div>
        {(hayAjenas || !soloMias) && (
          <label className="dp-toggle">
            <input type="checkbox" checked={!soloMias} onChange={e => setSoloMias(!e.target.checked)} />
            Ver todas las plantas
          </label>
        )}
      </div>

      {isLoading && <p className="dp-sub">Cargando…</p>}
      {plantas?.map(p => <TarjetaPlanta key={p.id} p={p} />)}

      <style>{`
        .dp-cabecera { display: flex; justify-content: space-between; align-items: flex-end; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
        .dp-cabecera h1 { font-size: 18px; font-weight: 700; margin: 0; }
        .dp-cabecera p { font-size: 12px; color: var(--text-muted); margin: 3px 0 0; }
        .dp-toggle { display: flex; gap: 6px; align-items: center; font-size: 12.5px; }
        .dp-sub { font-size: 11px; color: var(--text-muted); }
        .dp-planta { padding: 14px; margin-bottom: 14px; }
        .dp-planta header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
        .dp-planta h2 { font-size: 15px; font-weight: 700; margin: 0; display: flex; align-items: center; gap: 6px; }
        .dp-resumen { display: flex; gap: 10px; font-size: 12px; font-weight: 600; }
        .dp-aviso { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; color: var(--text-muted); }
        .dp-aviso .input-base { flex: 1; }
        .dp-lista { display: flex; flex-direction: column; border: 1px solid var(--border); }
        .dp-fila {
          display: grid; grid-template-columns: minmax(160px, 1.3fr) auto 150px minmax(160px, 1fr);
          gap: 12px; align-items: center; padding: 9px 12px; border-left: 4px solid transparent;
        }
        .dp-fila + .dp-fila { border-top: 1px solid var(--border); }
        .dp-fila.disponible { border-left-color: #16a34a; }
        .dp-fila.limitada { border-left-color: #d97706; background: #d977060a; }
        .dp-fila.agotada { border-left-color: #dc2626; background: #dc26260d; }
        .dp-material strong { display: block; font-size: 13px; }
        .dp-estados { display: inline-flex; }
        .dp-estados button {
          display: inline-flex; align-items: center; gap: 4px; padding: 6px 10px; font: inherit; font-size: 12px;
          border: 1px solid var(--border); background: var(--bg-surface); color: var(--text-secondary); cursor: pointer;
        }
        .dp-estados button + button { border-left: none; }
        .dp-estados button:disabled { cursor: default; }
        .dp-estados button.activo { font-weight: 600; }
        .dp-cantidad { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-muted); }
        .dp-cantidad .input-base { width: 100%; text-align: right; }
        .dp-nota { width: 100%; }
        @media (max-width: 900px) {
          .dp-fila { grid-template-columns: 1fr 1fr; }
          .dp-material { grid-column: 1 / -1; }
          .dp-nota { grid-column: 1 / -1; }
        }
        @media (max-width: 520px) {
          .dp-fila { grid-template-columns: 1fr; }
          .dp-estados { width: 100%; }
          .dp-estados button { flex: 1; justify-content: center; padding: 10px 4px; }
        }
      `}</style>
    </div>
  );
}
