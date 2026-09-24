import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getPlantas, createPlanta, setPlantaActiva } from "../api/plantas";
import { getMateriales, createMaterial, setPrecioMaterial } from "../api/materiales";
import { Icon } from "../components/ui/Icon";
import { UsuariosAdmin } from "../components/UsuariosAdmin";
import { MiFirma } from "../components/MiFirma";
import type { MaterialTipo } from "../types";

export function AdminPage() {
  const qc = useQueryClient();
  const { data: plantas } = useQuery({ queryKey: ["plantas", "todas"], queryFn: () => getPlantas(true) });
  const { data: materiales } = useQuery({ queryKey: ["materiales"], queryFn: getMateriales });

  const [nombrePlanta, setNombrePlanta] = useState("");
  const [ubicacionPlanta, setUbicacionPlanta] = useState("");
  const activarPlantaMut = useMutation({
    mutationFn: ({ id, activa }: { id: number; activa: boolean }) => setPlantaActiva(id, activa),
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ["plantas"] });
      toast.success(p.activa ? "Planta activada" : "Planta desactivada — ya no aparece al cotizar");
    },
    onError: () => toast.error("No se pudo actualizar la planta"),
  });

  const crearPlantaMut = useMutation({
    mutationFn: () => createPlanta({ nombre: nombrePlanta, ubicacion: ubicacionPlanta }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["plantas"] }); toast.success("Planta creada"); setNombrePlanta(""); setUbicacionPlanta(""); },
    onError: () => toast.error("No se pudo crear la planta"),
  });

  const [nombreMaterial, setNombreMaterial] = useState("");
  const [tipoMaterial, setTipoMaterial] = useState<MaterialTipo>("agregado");
  const [unidadMaterial, setUnidadMaterial] = useState("m3");
  const crearMaterialMut = useMutation({
    mutationFn: () => createMaterial({ nombre: nombreMaterial, tipo: tipoMaterial, unidad_medida: unidadMaterial }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["materiales"] }); toast.success("Material creado"); setNombreMaterial(""); },
    onError: () => toast.error("No se pudo crear el material"),
  });

  const precioMut = useMutation({
    mutationFn: ({ materialId, plantaId, campo, valor }: {
      materialId: number; plantaId: number;
      campo: "precio_especial" | "precio_detal"; valor: number | null;
    }) => setPrecioMaterial(materialId, plantaId, { [campo]: valor }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["materiales"] }); toast.success("Precio actualizado"); },
    onError: () => toast.error("No se pudo actualizar el precio"),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Administración</h1>

      <MiFirma compacto />
      <UsuariosAdmin />

      <section className="card" style={{ padding: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 12px" }}>Plantas</h2>
        <form
          style={{ display: "flex", gap: 8, marginBottom: 14 }}
          onSubmit={(e) => { e.preventDefault(); crearPlantaMut.mutate(); }}
        >
          <input className="input-base" style={{ flex: 1 }} placeholder="Nombre de la planta" value={nombrePlanta} onChange={e => setNombrePlanta(e.target.value)} required />
          <input className="input-base" style={{ flex: 1 }} placeholder="Ubicación" value={ubicacionPlanta} onChange={e => setUbicacionPlanta(e.target.value)} />
          <button type="submit" className="btn-primary"><Icon name="add" size={16} />Agregar</button>
        </form>
        <table className="table-sharp">
          <thead><tr><th>Nombre</th><th>Ubicación</th><th>Estado</th><th></th></tr></thead>
          <tbody>
            {plantas?.map(p => (
              <tr key={p.id} style={p.activa ? undefined : { opacity: 0.55 }}>
                <td>{p.nombre}</td>
                <td>{p.ubicacion || "-"}</td>
                <td>
                  {p.activa
                    ? <span className="badge" style={{ background: "var(--accent-light)", color: "var(--accent-text)" }}>Activa</span>
                    : <span className="badge" style={{ background: "#94a3b822", color: "#64748b" }}>Inactiva</span>}
                </td>
                <td style={{ textAlign: "right" }}>
                  <button
                    className="btn-secondary"
                    disabled={activarPlantaMut.isPending}
                    onClick={() => activarPlantaMut.mutate({ id: p.id, activa: !p.activa })}
                  >
                    {p.activa ? "Desactivar" : "Activar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 12px" }}>Materiales</h2>
        <form
          style={{ display: "flex", gap: 8, marginBottom: 14 }}
          onSubmit={(e) => { e.preventDefault(); crearMaterialMut.mutate(); }}
        >
          <input className="input-base" style={{ flex: 2 }} placeholder="Nombre" value={nombreMaterial} onChange={e => setNombreMaterial(e.target.value)} required />
          <select className="input-base" style={{ flex: 1 }} value={tipoMaterial} onChange={e => setTipoMaterial(e.target.value as MaterialTipo)}>
            <option value="triturado">Triturado</option>
            <option value="agregado">Agregado</option>
            <option value="otro">Otro</option>
          </select>
          <input className="input-base" style={{ flex: 1 }} placeholder="Unidad (m3, ton...)" value={unidadMaterial} onChange={e => setUnidadMaterial(e.target.value)} />
          <button type="submit" className="btn-primary"><Icon name="add" size={16} />Agregar</button>
        </form>

        <table className="table-sharp">
          <thead>
            <tr>
              <th>Material</th>
              <th>Tipo</th>
              <th>Unidad</th>
              {plantas?.map(p => (
                <th key={p.id}>
                  {p.nombre}
                  <span style={{ display: "block", fontWeight: 400, fontSize: 10, opacity: 0.7 }}>
                    especial · detal
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {materiales?.map(m => (
              <tr key={m.id}>
                <td>{m.nombre}</td>
                <td>{m.tipo_display}</td>
                <td>{m.unidad_medida}</td>
                {plantas?.map(p => {
                  const precio = m.precios.find(pr => pr.planta === p.id);
                  // Dos casillas por planta: venta especial y venta detal.
                  const casilla = (
                    campo: "precio_especial" | "precio_detal",
                    actual: string | null | undefined,
                    titulo: string,
                  ) => (
                    <input
                      className="input-base"
                      style={{ width: 84 }}
                      type="number"
                      min="0"
                      step="0.01"
                      title={titulo}
                      defaultValue={actual ?? ""}
                      placeholder="—"
                      onBlur={e => {
                        const txt = e.target.value.trim();
                        const val = txt === "" ? null : Number(txt);
                        if (val !== null && !(val > 0)) return;
                        const previo = actual == null ? null : Number(actual);
                        if (val === previo) return;
                        // El precio especial es obligatorio: no se puede vaciar.
                        if (campo === "precio_especial" && val === null) {
                          e.target.value = actual ?? "";
                          return;
                        }
                        precioMut.mutate({ materialId: m.id, plantaId: p.id, campo, valor: val });
                      }}
                    />
                  );
                  return (
                    <td key={p.id}>
                      <div style={{ display: "flex", gap: 4 }}>
                        {casilla("precio_especial", precio?.precio_especial, "Venta especial (sin IVA)")}
                        {casilla("precio_detal", precio?.precio_detal, "Venta detal (sin IVA) — vacío usa la especial")}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
