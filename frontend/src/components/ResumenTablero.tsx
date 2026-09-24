import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Icon } from "./ui/Icon";
import { getResumenTablero } from "../api/tablero";
import { pesos } from "../lib/cotizacion";

/** $12,3 M / $850 mil — para ejes y tarjetas, donde el valor exacto estorba. */
function corto(v: number) {
  if (Math.abs(v) >= 1e9) return `$${(v / 1e9).toLocaleString("es-CO", { maximumFractionDigits: 1 })} mil M`;
  if (Math.abs(v) >= 1e6) return `$${(v / 1e6).toLocaleString("es-CO", { maximumFractionDigits: 1 })} M`;
  if (Math.abs(v) >= 1e3) return `$${Math.round(v / 1e3).toLocaleString("es-CO")} mil`;
  return pesos(v);
}

function mesCorto(m: string) {
  const [y, mm] = m.split("-").map(Number);
  return new Date(y, mm - 1, 1).toLocaleDateString("es-CO", { month: "short" }).replace(".", "");
}

function Kpi({ icon, titulo, valor, detalle, alerta }: {
  icon: string; titulo: string; valor: string; detalle?: string; alerta?: boolean;
}) {
  return (
    <div className={`rt-kpi ${alerta ? "alerta" : ""}`}>
      <span className="rt-kpi-titulo"><Icon name={icon} size={14} />{titulo}</span>
      <strong>{valor}</strong>
      {detalle && <span className="rt-kpi-detalle">{detalle}</span>}
    </div>
  );
}

/** Barras horizontales de una sola serie; el valor va escrito, no hace falta leyenda. */
function Barras({ filas, formato }: { filas: { nombre: string; valor: number; texto?: string }[]; formato: (v: number) => string }) {
  const max = Math.max(...filas.map(f => f.valor), 1);
  if (filas.length === 0) return <p className="rt-vacio">Sin datos todavía.</p>;
  return (
    <ul className="rt-barras">
      {filas.map(f => (
        <li key={f.nombre} title={`${f.nombre}: ${f.texto ?? formato(f.valor)}`}>
          <span className="rt-barras-nombre">{f.nombre}</span>
          <span className="rt-barras-pista"><i style={{ width: `${(f.valor / max) * 100}%` }} /></span>
          <span className="rt-barras-valor">{f.texto ?? formato(f.valor)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Columnas por mes: ventas (pagos aprobados) al frente, lo cotizado detrás como contexto. */
function PorMes({ datos }: { datos: { mes: string; ventas: number; cotizado: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...datos.flatMap(d => [d.ventas, d.cotizado]), 1);
  return (
    <div>
      <div className="rt-leyenda">
        <span><i className="ventas" />Ventas (pagos aprobados)</span>
        <span><i className="cotizado" />Cotizado</span>
      </div>
      <div className="rt-columnas" onMouseLeave={() => setHover(null)}>
        {datos.map((d, i) => (
          <div key={d.mes} className={`rt-col ${hover === i ? "activa" : ""}`} onMouseEnter={() => setHover(i)}>
            {hover === i && (
              <div className="rt-tooltip">
                <strong>{mesCorto(d.mes)} {d.mes.slice(0, 4)}</strong>
                <span><i className="ventas" />Ventas {pesos(d.ventas)}</span>
                <span><i className="cotizado" />Cotizado {pesos(d.cotizado)}</span>
              </div>
            )}
            <div className="rt-col-barras">
              <i className="cotizado" style={{ height: `${(d.cotizado / max) * 100}%` }} />
              <i className="ventas" style={{ height: `${(d.ventas / max) * 100}%` }} />
            </div>
            <span className="rt-col-mes">{mesCorto(d.mes)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ResumenTablero() {
  const { data } = useQuery({ queryKey: ["tablero", "resumen"], queryFn: getResumenTablero });
  if (!data) return null;
  const k = data.kpis;
  const est = data.cotizaciones_por_estado;

  return (
    <section className="rt">
      <div className="rt-kpis">
        <Kpi icon="payments" titulo="Ventas del mes" valor={corto(Number(k.ventas_mes))} detalle="pagos aprobados" />
        <Kpi icon="request_quote" titulo="Cotizado del mes" valor={corto(Number(k.cotizado_mes))} detalle="sin contar rechazadas" />
        <Kpi icon="percent" titulo="Aprobación"
          valor={k.tasa_aprobacion == null ? "—" : `${k.tasa_aprobacion}%`}
          detalle={`${est.aprobada ?? 0} aprobadas · ${est.rechazada ?? 0} rechazadas`} />
        <Kpi icon="pending_actions" titulo="Por aprobar" valor={String(k.pendientes_aprobacion)}
          detalle={`${k.pagos_por_revisar} pago${k.pagos_por_revisar === 1 ? "" : "s"} por revisar`}
          alerta={k.pendientes_aprobacion + k.pagos_por_revisar > 0} />
        <Kpi icon="local_shipping" titulo="Despachado del mes"
          valor={Number(k.despachado_mes).toLocaleString("es-CO", { maximumFractionDigits: 1 })}
          detalle={`${k.solicitudes_en_curso} solicitudes en curso`} />
      </div>

      <div className="rt-graficas">
        <div className="rt-card rt-card-ancha">
          <h3>Últimos 6 meses</h3>
          <PorMes datos={data.por_mes.map(m => ({ mes: m.mes, ventas: Number(m.ventas), cotizado: Number(m.cotizado) }))} />
        </div>
        <div className="rt-card">
          <h3>Vendido por planta <small>cotizaciones aprobadas, sin IVA</small></h3>
          <Barras filas={data.por_planta.map(p => ({ nombre: p.nombre.replace("Planta ", ""), valor: Number(p.valor) }))} formato={corto} />
        </div>
        <div className="rt-card">
          <h3>Mejores clientes <small>cotizaciones aprobadas</small></h3>
          <Barras filas={data.top_clientes.map(c => ({ nombre: c.nombre, valor: Number(c.valor) }))} formato={corto} />
        </div>
        <div className="rt-card">
          <h3>Materiales más vendidos</h3>
          <Barras
            filas={data.top_materiales.map(m => {
              const v = Number(m.cantidad);
              return { nombre: m.nombre, valor: v, texto: `${v.toLocaleString("es-CO", { maximumFractionDigits: 1 })} ${m.unidad}` };
            })}
            formato={String} />
        </div>
      </div>

      <style>{`
        .rt { margin-bottom: 18px; }
        .rt-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin-bottom: 10px; }
        .rt-kpi { background: var(--bg-surface); border: 1px solid var(--border); padding: 12px 14px; display: flex; flex-direction: column; gap: 2px; }
        .rt-kpi.alerta { border-left: 3px solid #f59e0b; }
        .rt-kpi-titulo { display: flex; align-items: center; gap: 5px; font-size: 11.5px; color: var(--text-muted); }
        .rt-kpi strong { font-size: 22px; font-weight: 700; color: var(--text-primary); font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
        .rt-kpi-detalle { font-size: 11px; color: var(--text-muted); }
        .rt-graficas { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
        .rt-card { background: var(--bg-surface); border: 1px solid var(--border); padding: 14px; min-width: 0; }
        .rt-card-ancha { grid-column: 1 / -1; }
        .rt-card h3 { font-size: 13px; font-weight: 700; margin: 0 0 12px; color: var(--text-primary); }
        .rt-card h3 small { font-weight: 400; color: var(--text-muted); font-size: 11px; margin-left: 4px; }
        .rt-vacio { font-size: 12px; color: var(--text-muted); margin: 0; }
        .rt-barras { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
        .rt-barras li { display: grid; grid-template-columns: minmax(80px, 38%) 1fr auto; align-items: center; gap: 8px; font-size: 12px; }
        .rt-barras-nombre { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .rt-barras-pista { height: 10px; background: var(--bg-surface-2); }
        .rt-barras-pista i { display: block; height: 100%; background: var(--accent); border-radius: 0 4px 4px 0; min-width: 2px; }
        .rt-barras-valor { color: var(--text-primary); font-variant-numeric: tabular-nums; white-space: nowrap; }
        .rt-leyenda { display: flex; gap: 14px; font-size: 11.5px; color: var(--text-secondary); margin: -4px 0 10px; }
        .rt-leyenda span, .rt-tooltip span { display: inline-flex; align-items: center; gap: 5px; }
        .rt i.ventas, .rt i.cotizado { display: inline-block; width: 9px; height: 9px; border-radius: 2px; }
        .rt i.ventas { background: var(--accent); }
        .rt i.cotizado { background: #94a3b8; }
        .dark .rt i.cotizado { background: #64748b; }
        .rt-columnas { display: flex; align-items: stretch; gap: 6px; height: 170px; border-bottom: 1px solid var(--border); }
        .rt-col { flex: 1; display: flex; flex-direction: column; position: relative; cursor: default; }
        .rt-col.activa { background: var(--bg-surface-2); }
        .rt-col-barras { flex: 1; display: flex; align-items: flex-end; justify-content: center; gap: 2px; padding: 0 12%; }
        .rt-col-barras i { width: 100% !important; max-width: 28px; border-radius: 4px 4px 0 0 !important; }
        .rt-col-mes { text-align: center; font-size: 11px; color: var(--text-muted); padding: 4px 0 0; position: absolute; bottom: -20px; left: 0; right: 0; text-transform: capitalize; }
        .rt-columnas { margin-bottom: 22px; }
        .rt-tooltip {
          position: absolute; bottom: calc(100% - 20px); left: 50%; transform: translateX(-50%); z-index: 5;
          background: var(--bg-surface); border: 1px solid var(--border); box-shadow: 0 4px 14px rgba(0,0,0,0.15);
          padding: 8px 10px; font-size: 11.5px; display: flex; flex-direction: column; gap: 3px; white-space: nowrap;
          color: var(--text-primary); pointer-events: none;
        }
      `}</style>
    </section>
  );
}
