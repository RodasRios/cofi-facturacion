import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon } from "./ui/Icon";
import { getMateriales } from "../api/materiales";
import { getPlantas } from "../api/plantas";
import { createCotizacion, getNotasAclaratorias } from "../api/cotizaciones";
import {
  type Ajuste, type Linea, type Reparto,
  plantasConPrecio, precioDeTarifa, precioLinea, repartoInicial, sumaCantidades,
  calcularTotales, pesos, IVA_PORCENTAJE,
} from "../lib/cotizacion";
import type { SolicitudCotizacion, TipoPrecio } from "../types";

interface Props {
  solicitudes: SolicitudCotizacion[];
  onCreada: () => void;
  onCancelar: () => void;
}

/**
 * Armado de una cotización, con control sobre lo que sale en el FR-GC-08:
 * de qué planta sale cada material y a qué precio (tarifa o a mano), cargos
 * y descuentos, y qué notas aclaratorias se imprimen.
 */
export function NuevaCotizacion({ solicitudes, onCreada, onCancelar }: Props) {
  const qc = useQueryClient();
  const { data: materiales = [] } = useQuery({ queryKey: ["materiales"], queryFn: getMateriales });
  const { data: plantas = [] } = useQuery({ queryKey: ["plantas"], queryFn: () => getPlantas() });
  const { data: notas = [] } = useQuery({ queryKey: ["notas-aclaratorias"], queryFn: getNotasAclaratorias });

  const [solicitudId, setSolicitudId] = useState("");
  const [tarifa, setTarifa] = useState<TipoPrecio>("especial");
  const [reparto, setReparto] = useState<Reparto>({});
  const [ajustes, setAjustes] = useState<Ajuste[]>([]);
  // null = todas las notas (el valor por defecto del formato).
  const [notasSel, setNotasSel] = useState<Set<string> | null>(null);
  const [notasAbiertas, setNotasAbiertas] = useState<Set<string>>(new Set());
  const [notasExtra, setNotasExtra] = useState("");

  const solicitud = useMemo(() => solicitudes.find(s => String(s.id) === solicitudId), [solicitudes, solicitudId]);

  // Al elegir solicitud (o cuando llegan los catálogos), se arma el reparto
  // inicial con la tarifa del cliente. Patrón de React para ajustar estado
  // cuando cambian los datos, sin useEffect.
  const base = `${solicitudId}|${materiales.length}|${plantas.length}`;
  const [baseActual, setBaseActual] = useState("");
  if (base !== baseActual) {
    setBaseActual(base);
    const t = solicitud?.cliente_tipo_precio ?? "especial";
    setTarifa(t);
    setReparto(solicitud ? repartoInicial(solicitud.items, materiales, plantas, t) : {});
  }

  const elegidas = notasSel ?? new Set(notas.map(n => n.clave));

  // ── Cálculos ────────────────────────────────────────────────────────
  const bloques = (solicitud?.items ?? []).map(item => {
    const material = materiales.find(m => m.id === item.material);
    const opciones = plantasConPrecio(material, plantas, tarifa);
    const lineas = reparto[item.material] ?? [];
    const pedido = Number(item.cantidad);
    const suma = sumaCantidades(lineas);
    const detalle = lineas.map(l => {
      const precio = precioLinea(l, opciones);
      return { precio, subtotal: precio != null ? precio * (Number(l.cantidad) || 0) : 0 };
    });
    return { item, material, opciones, lineas, pedido, suma, detalle };
  });

  const subtotalMateriales = bloques.reduce((t, b) => t + b.detalle.reduce((s, d) => s + d.subtotal, 0), 0);
  const totales = calcularTotales(subtotalMateriales, ajustes);

  const problemas: string[] = [];
  for (const b of bloques) {
    const nombre = b.item.material_nombre;
    if (b.opciones.length === 0) problemas.push(`Ninguna planta activa tiene precio para ${nombre}.`);
    else if (Math.abs(b.suma - b.pedido) >= 0.01) problemas.push(`${nombre}: el reparto no suma lo pedido.`);
    if (b.lineas.some(l => !l.planta)) problemas.push(`${nombre}: falta elegir planta.`);
    if (b.detalle.some(d => d.precio == null)) problemas.push(`${nombre}: falta un precio.`);
  }
  ajustes.forEach(a => {
    if (!a.descripcion.trim() || !(Number(a.valor) > 0)) problemas.push("Completa la descripción y el valor de cada cargo o descuento.");
    if (a.modo === "porcentaje" && Number(a.valor) > 100) problemas.push(`"${a.descripcion}" supera el 100%.`);
  });
  const listo = !!solicitud && problemas.length === 0;

  // ── Edición ─────────────────────────────────────────────────────────
  const editarLinea = (materialId: number, idx: number, cambio: Partial<Linea>) => {
    const lineas = [...(reparto[materialId] ?? [])];
    lineas[idx] = { ...lineas[idx], ...cambio };
    setReparto({ ...reparto, [materialId]: lineas });
  };
  const agregarLinea = (materialId: number, pedido: number) => {
    const lineas = reparto[materialId] ?? [];
    const restante = Math.max(pedido - sumaCantidades(lineas), 0);
    setReparto({ ...reparto, [materialId]: [...lineas, { planta: "", cantidad: String(restante), origen: tarifa, precioManual: "" }] });
  };
  const quitarLinea = (materialId: number, idx: number) =>
    setReparto({ ...reparto, [materialId]: (reparto[materialId] ?? []).filter((_, i) => i !== idx) });

  const cambiarTarifa = (t: TipoPrecio) => {
    setTarifa(t);
    // Las líneas de tarifa siguen a la nueva; las escritas a mano se respetan.
    setReparto(Object.fromEntries(Object.entries(reparto).map(([k, ls]) =>
      [k, ls.map(l => l.origen === "manual" ? l : { ...l, origen: t })])));
  };

  const agregarAjuste = (tipo: Ajuste["tipo"]) => setAjustes([...ajustes, tipo === "cargo"
    ? { tipo, modo: "monto", descripcion: "Flete", valor: "", aplicaIva: true }
    : { tipo, modo: "porcentaje", descripcion: "Descuento comercial", valor: "", aplicaIva: true }]);
  const editarAjuste = (i: number, cambio: Partial<Ajuste>) =>
    setAjustes(ajustes.map((a, j) => j === i ? { ...a, ...cambio } : a));

  const alternarNota = (clave: string) => {
    const s = new Set(elegidas);
    if (s.has(clave)) s.delete(clave); else s.add(clave);
    setNotasSel(s);
  };
  const alternarTexto = (clave: string) => {
    const s = new Set(notasAbiertas);
    if (s.has(clave)) s.delete(clave); else s.add(clave);
    setNotasAbiertas(s);
  };

  const crear = useMutation({
    mutationFn: () => {
      const items = bloques.flatMap(b => b.lineas.map(l => ({
        material: b.item.material,
        planta: Number(l.planta),
        cantidad: Number(l.cantidad),
        origen_precio: l.origen,
        ...(l.origen === "manual" ? { precio_unitario: Number(l.precioManual) } : {}),
      })));
      return createCotizacion({
        solicitud: Number(solicitudId),
        planta: items[0].planta,
        tipo_precio: tarifa,
        items,
        ajustes: ajustes.map(a => ({
          tipo: a.tipo, modo: a.modo, descripcion: a.descripcion.trim(),
          valor: Number(a.valor), aplica_iva: a.aplicaIva,
        })),
        // En el orden del formato, no en el orden en que se marcaron.
        notas_aclaratorias: notas.filter(n => elegidas.has(n.clave)).map(n => n.clave),
        notas: notasExtra.trim() || undefined,
      });
    },
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["cotizaciones"] });
      qc.invalidateQueries({ queryKey: ["solicitudes"] });
      qc.invalidateQueries({ queryKey: ["tablero"] });
      toast.success(`Cotización ${c.numero} generada`);
      onCreada();
    },
    onError: (e: unknown) => {
      const detalle = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detalle ?? "No se pudo generar la cotización");
    },
  });

  return (
    <form className="card nc" onSubmit={(e) => { e.preventDefault(); if (listo) crear.mutate(); }}>
      <div className="nc-cabecera">
        <div className="nc-campo">
          <label className="section-label">Solicitud *</label>
          <select className="input-base" value={solicitudId} onChange={e => setSolicitudId(e.target.value)} required>
            <option value="">Selecciona una solicitud</option>
            {solicitudes.map(s => (
              <option key={s.id} value={s.id}>{s.numero} — {s.cliente_nombre}{s.obra ? ` · ${s.obra}` : ""}</option>
            ))}
          </select>
        </div>
        <div className="nc-campo">
          <label className="section-label">Tarifa</label>
          <div className="nc-segmento" role="radiogroup">
            {(["especial", "detal"] as const).map(t => (
              <button key={t} type="button" role="radio" aria-checked={tarifa === t}
                className={tarifa === t ? "activo" : ""} onClick={() => cambiarTarifa(t)} disabled={!solicitud}>
                {t === "especial" ? "Venta especial" : "Venta detal"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {!solicitud && (
        <p className="nc-vacio">Elige una solicitud para armar la cotización.</p>
      )}

      {solicitud && (
        <div className="nc-cuerpo">
          <div className="nc-principal">
            {/* ── Materiales ─────────────────────────────────────── */}
            <section>
              <h3 className="nc-titulo">Materiales, plantas y precios</h3>
              <p className="nc-ayuda">
                Solo aparecen las plantas que tienen precio para cada material, de la más barata a la más cara.
                Puedes repartir un material entre varias plantas y cambiar el precio de cada línea.
              </p>

              {bloques.map(b => {
                const descuadre = Math.abs(b.suma - b.pedido) >= 0.01;
                return (
                  <div key={b.item.material} className="nc-material">
                    <div className="nc-material-cab">
                      <strong>{b.item.material_nombre}</strong>
                      <span className={descuadre ? "nc-mal" : "nc-tenue"}>
                        {b.suma.toLocaleString("es-CO")} de {b.pedido.toLocaleString("es-CO")} {b.item.unidad_medida}
                        {descuadre && (b.suma > b.pedido ? " — sobra" : " — falta")}
                      </span>
                    </div>

                    {b.opciones.length === 0 ? (
                      <div className="nc-alerta">
                        <Icon name="error" size={14} />
                        Ninguna planta activa tiene precio para este material. Agrégalo en Administración → Precios.
                      </div>
                    ) : (
                      <>
                        <div className="nc-linea nc-linea-cab">
                          <span>Planta</span><span>Cantidad</span><span>Precio (sin IVA)</span><span className="der">Subtotal</span><span />
                        </div>
                        {b.lineas.map((l, idx) => {
                          const op = b.opciones.find(o => String(o.planta.id) === l.planta);
                          const pct = b.pedido > 0 ? Math.round((Number(l.cantidad) || 0) / b.pedido * 100) : 0;
                          return (
                            <div key={idx} className="nc-linea">
                              <select className="input-base" value={l.planta}
                                onChange={e => editarLinea(b.item.material, idx, { planta: e.target.value })}>
                                <option value="">Elige planta</option>
                                {b.opciones.map(o => (
                                  <option key={o.planta.id} value={o.planta.id}
                                    disabled={b.lineas.some((otra, j) => j !== idx && otra.planta === String(o.planta.id))}>
                                    {o.planta.nombre.replace("Planta ", "")} · {pesos(precioDeTarifa(o, tarifa))}
                                  </option>
                                ))}
                              </select>

                              <div className="nc-cantidad">
                                <input className="input-base" type="number" min="0" step="0.01" value={l.cantidad}
                                  onChange={e => editarLinea(b.item.material, idx, { cantidad: e.target.value })} />
                                {b.lineas.length > 1 && <span className="nc-tenue">{pct}%</span>}
                              </div>

                              <div className="nc-precio">
                                <select className="input-base" value={l.origen} disabled={!op && l.origen !== "manual"}
                                  onChange={e => editarLinea(b.item.material, idx, { origen: e.target.value as Linea["origen"] })}>
                                  <option value="especial">Especial{op ? ` · ${pesos(op.especial)}` : ""}</option>
                                  <option value="detal" disabled={!!op && op.detal == null}>
                                    Detal{op ? (op.detal != null ? ` · ${pesos(op.detal)}` : " · no maneja") : ""}
                                  </option>
                                  <option value="manual">Otro precio…</option>
                                </select>
                                {l.origen === "manual" && (
                                  <input className="input-base" type="number" min="0" step="1" placeholder="$ por unidad"
                                    value={l.precioManual} autoFocus
                                    onChange={e => editarLinea(b.item.material, idx, { precioManual: e.target.value })} />
                                )}
                              </div>

                              <span className="der nc-subtotal">{pesos(b.detalle[idx]?.subtotal ?? 0)}</span>

                              {b.lineas.length > 1 ? (
                                <button type="button" className="btn-ghost" title="Quitar esta línea"
                                  onClick={() => quitarLinea(b.item.material, idx)}>
                                  <Icon name="close" size={15} />
                                </button>
                              ) : <span />}
                            </div>
                          );
                        })}
                        {b.opciones.length > b.lineas.length && (
                          <button type="button" className="btn-ghost nc-mini" onClick={() => agregarLinea(b.item.material, b.pedido)}>
                            <Icon name="call_split" size={14} />Repartir con otra planta
                          </button>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </section>

            {/* ── Cargos y descuentos ────────────────────────────── */}
            <section>
              <h3 className="nc-titulo">Cargos y descuentos</h3>
              {ajustes.length === 0 && (
                <p className="nc-ayuda">Flete, transporte, descuentos comerciales… Los porcentajes se calculan sobre el valor de los materiales.</p>
              )}
              {ajustes.map((a, i) => (
                <div key={i} className="nc-ajuste">
                  <span className={`nc-chip ${a.tipo}`}>{a.tipo === "cargo" ? "Cargo" : "Descuento"}</span>
                  <input className="input-base" value={a.descripcion} placeholder="Descripción"
                    onChange={e => editarAjuste(i, { descripcion: e.target.value })} />
                  <div className="nc-segmento chico">
                    <button type="button" className={a.modo === "monto" ? "activo" : ""} onClick={() => editarAjuste(i, { modo: "monto" })}>$</button>
                    <button type="button" className={a.modo === "porcentaje" ? "activo" : ""} onClick={() => editarAjuste(i, { modo: "porcentaje" })}>%</button>
                  </div>
                  <input className="input-base nc-valor" type="number" min="0" step={a.modo === "porcentaje" ? "0.1" : "1"}
                    placeholder={a.modo === "porcentaje" ? "%" : "$"} value={a.valor}
                    onChange={e => editarAjuste(i, { valor: e.target.value })} />
                  <label className="nc-check" title="Si se desmarca, este valor no suma a la base del IVA">
                    <input type="checkbox" checked={a.aplicaIva} onChange={e => editarAjuste(i, { aplicaIva: e.target.checked })} />
                    IVA
                  </label>
                  <span className="der nc-subtotal">{pesos(totales.valores[i] ?? 0)}</span>
                  <button type="button" className="btn-ghost" title="Quitar" onClick={() => setAjustes(ajustes.filter((_, j) => j !== i))}>
                    <Icon name="close" size={15} />
                  </button>
                </div>
              ))}
              <div className="nc-botones">
                <button type="button" className="btn-secondary" onClick={() => agregarAjuste("cargo")}>
                  <Icon name="local_shipping" size={14} />Agregar cargo (flete…)
                </button>
                <button type="button" className="btn-secondary" onClick={() => agregarAjuste("descuento")}>
                  <Icon name="percent" size={14} />Agregar descuento
                </button>
              </div>
            </section>

            {/* ── Notas aclaratorias ─────────────────────────────── */}
            <section>
              <div className="nc-titulo-fila">
                <h3 className="nc-titulo">Notas aclaratorias <span className="nc-tenue">({elegidas.size} de {notas.length})</span></h3>
                <div className="nc-botones">
                  <button type="button" className="btn-ghost nc-mini" onClick={() => setNotasSel(null)}>Todas</button>
                  <button type="button" className="btn-ghost nc-mini" onClick={() => setNotasSel(new Set())}>Ninguna</button>
                </div>
              </div>
              <p className="nc-ayuda">La ubicación de cada planta se agrega sola. Toca el título para leer la nota completa.</p>
              <ul className="nc-notas">
                {notas.map(n => {
                  const abierta = notasAbiertas.has(n.clave);
                  return (
                    <li key={n.clave} className={elegidas.has(n.clave) ? "" : "apagada"}>
                      <input type="checkbox" checked={elegidas.has(n.clave)} onChange={() => alternarNota(n.clave)}
                        aria-label={n.titulo} />
                      <div>
                        <button type="button" className="nc-nota-titulo" onClick={() => alternarTexto(n.clave)} aria-expanded={abierta}>
                          {n.titulo}
                          <Icon name={abierta ? "expand_less" : "expand_more"} size={16} />
                        </button>
                        {/* El texto viene del catálogo fijo del servidor (con <b>), no de un usuario. */}
                        {abierta && <p className="nc-nota-texto" dangerouslySetInnerHTML={{ __html: n.texto }} />}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <label className="section-label" style={{ marginTop: 10, display: "block" }}>Notas adicionales (una por línea)</label>
              <textarea className="input-base nc-textarea" rows={3} value={notasExtra}
                placeholder={"Ej.: Entrega sujeta a disponibilidad de planta\nPrecio válido para despachos en la semana del 30 de septiembre"}
                onChange={e => setNotasExtra(e.target.value)} />
            </section>
          </div>

          {/* ── Resumen ──────────────────────────────────────────── */}
          <aside className="nc-resumen">
            <h3 className="nc-titulo">Resumen</h3>
            <dl>
              <div><dt>Materiales</dt><dd>{pesos(subtotalMateriales)}</dd></div>
              {ajustes.map((a, i) => (
                <div key={i} className="nc-tenue">
                  <dt>{a.descripcion || (a.tipo === "cargo" ? "Cargo" : "Descuento")}{a.modo === "porcentaje" && a.valor ? ` (${a.valor}%)` : ""}</dt>
                  <dd>{pesos(totales.valores[i] ?? 0)}</dd>
                </div>
              ))}
              <div><dt>Subtotal</dt><dd>{pesos(totales.subtotal)}</dd></div>
              <div><dt>IVA {IVA_PORCENTAJE}%</dt><dd>{pesos(totales.iva)}</dd></div>
              <div className="nc-total"><dt>Total</dt><dd>{pesos(totales.total)}</dd></div>
            </dl>

            {problemas.length > 0 && (
              <ul className="nc-problemas">
                {[...new Set(problemas)].map(p => <li key={p}>{p}</li>)}
              </ul>
            )}

            <button type="submit" className="btn-primary nc-generar" disabled={!listo || crear.isPending}>
              <Icon name="description" size={15} />{crear.isPending ? "Generando…" : "Generar cotización"}
            </button>
            <button type="button" className="btn-secondary nc-generar" onClick={onCancelar}>Cancelar</button>
          </aside>
        </div>
      )}

      <style>{`
        .nc { padding: 16px; margin-bottom: 16px; }
        .nc-cabecera { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; }
        @media (max-width: 720px) { .nc-cabecera { grid-template-columns: 1fr; } }
        .nc-campo .input-base { width: 100%; }
        .nc-vacio { font-size: 12.5px; color: var(--text-muted); margin: 14px 0 0; }
        .nc-cuerpo { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 18px; margin-top: 16px; align-items: start; }
        @media (max-width: 980px) { .nc-cuerpo { grid-template-columns: 1fr; } }
        .nc-principal { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
        .nc-titulo { font-size: 13px; font-weight: 700; margin: 0 0 4px; }
        .nc-titulo-fila { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .nc-ayuda { font-size: 12px; color: var(--text-muted); margin: 0 0 10px; }
        .nc-tenue { color: var(--text-muted); font-weight: 400; }
        .nc-mal { color: #ef4444; font-weight: 600; font-size: 12px; }
        .nc-material { border: 1px solid var(--border); padding: 10px 12px; margin-bottom: 10px; }
        .nc-material-cab { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 12.5px; margin-bottom: 8px; }
        .nc-material-cab .nc-tenue { font-size: 12px; }
        .nc-linea {
          display: grid; grid-template-columns: minmax(150px, 1.4fr) 120px minmax(170px, 1.4fr) 110px 32px;
          gap: 8px; align-items: center; margin-bottom: 6px;
        }
        .nc-linea-cab { font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-muted); margin-bottom: 4px; }
        @media (max-width: 720px) {
          .nc-linea { grid-template-columns: 1fr 1fr; }
          .nc-linea-cab { display: none; }
        }
        .nc-linea .input-base { width: 100%; min-width: 0; }
        .nc-cantidad, .nc-precio { display: flex; gap: 6px; align-items: center; min-width: 0; }
        .nc-cantidad .nc-tenue { font-size: 11px; min-width: 30px; }
        .der { text-align: right; }
        .nc-subtotal { font-size: 12.5px; font-variant-numeric: tabular-nums; }
        .nc-mini { font-size: 11.5px; padding: 3px 6px; }
        .nc-alerta { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #b91c1c; background: #fef2f2; border: 1px solid #fca5a5; padding: 8px 10px; }
        .dark .nc-alerta { background: #2d0f0f; border-color: #7f1d1d; color: #f87171; }
        .nc-ajuste {
          display: grid; grid-template-columns: 82px minmax(140px, 1fr) 64px 110px 54px 110px 32px;
          gap: 8px; align-items: center; margin-bottom: 6px;
        }
        @media (max-width: 720px) { .nc-ajuste { grid-template-columns: 1fr 1fr; } }
        .nc-ajuste .input-base { width: 100%; min-width: 0; }
        .nc-chip { font-size: 11px; font-weight: 600; padding: 3px 6px; text-align: center; }
        .nc-chip.cargo { background: #3b82f622; color: #2563eb; }
        .nc-chip.descuento { background: #22c55e22; color: #16a34a; }
        .nc-check { display: flex; gap: 4px; align-items: center; font-size: 12px; }
        .nc-botones { display: flex; gap: 8px; flex-wrap: wrap; }
        .nc-segmento { display: flex; border: 1px solid var(--border); }
        .nc-segmento button {
          flex: 1; background: var(--bg-surface); border: none; padding: 7px 10px; font-size: 12.5px;
          cursor: pointer; color: var(--text-secondary);
        }
        .nc-segmento button + button { border-left: 1px solid var(--border); }
        .nc-segmento button.activo { background: var(--accent-light); color: var(--accent-text); font-weight: 600; }
        .nc-segmento button:disabled { cursor: default; opacity: 0.6; }
        .nc-segmento.chico button { padding: 6px 0; }
        .nc-notas { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 4px 16px; }
        .nc-notas li { display: flex; gap: 8px; align-items: flex-start; padding: 4px 0; }
        .nc-notas li input { margin-top: 3px; }
        .nc-notas li.apagada .nc-nota-titulo { color: var(--text-muted); text-decoration: line-through; }
        .nc-nota-titulo {
          background: none; border: none; padding: 0; cursor: pointer; text-align: left;
          font-size: 12.5px; color: var(--text-primary); display: inline; line-height: 1.4;
        }
        .nc-nota-titulo .material-symbols-outlined { vertical-align: middle; }
        .nc-nota-texto { font-size: 11.5px; color: var(--text-secondary); margin: 4px 0 2px; line-height: 1.45; }
        .nc-textarea { width: 100%; resize: vertical; font-family: inherit; }
        .nc-resumen { position: sticky; top: 12px; border: 1px solid var(--border); padding: 12px 14px; background: var(--bg-surface); }
        .nc-resumen dl { margin: 8px 0 12px; }
        .nc-resumen dl > div { display: flex; justify-content: space-between; gap: 8px; font-size: 12.5px; padding: 3px 0; }
        .nc-resumen dt { min-width: 0; overflow: hidden; text-overflow: ellipsis; }
        .nc-resumen dd { margin: 0; font-variant-numeric: tabular-nums; white-space: nowrap; }
        .nc-total { border-top: 1px solid var(--border); margin-top: 4px; padding-top: 6px !important; font-weight: 700; font-size: 14px !important; }
        .nc-problemas { margin: 0 0 12px; padding-left: 16px; font-size: 11.5px; color: #b45309; }
        .dark .nc-problemas { color: #fbbf24; }
        .nc-generar { width: 100%; justify-content: center; margin-top: 6px; }
      `}</style>
    </form>
  );
}
