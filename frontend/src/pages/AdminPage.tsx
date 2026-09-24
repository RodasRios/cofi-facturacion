import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getPlantas, createPlanta, setPlantaActiva } from "../api/plantas";
import { getMateriales, createMaterial } from "../api/materiales";
import { Icon } from "../components/ui/Icon";
import { UsuariosAdmin } from "../components/UsuariosAdmin";
import { MiFirma } from "../components/MiFirma";
import { PreciosPorPlanta } from "../components/PreciosPorPlanta";
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

  // Las plantas dadas de baja se esconden: solo sirven para reactivarlas.
  const [verInactivas, setVerInactivas] = useState(false);
  const inactivas = (plantas ?? []).filter(p => !p.activa).length;
  const plantasVisibles = (plantas ?? []).filter(p => verInactivas || p.activa);

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
            {plantasVisibles.map(p => (
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
        {inactivas > 0 && (
          <button className="btn-ghost" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setVerInactivas(v => !v)}>
            <Icon name={verInactivas ? "visibility_off" : "visibility"} size={14} />
            {verInactivas ? "Ocultar plantas inactivas" : `Mostrar plantas inactivas (${inactivas})`}
          </button>
        )}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 4px" }}>Precios por planta</h2>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 12px" }}>
          Al cotizar solo se ofrecen las plantas que tienen precio para cada material.
        </p>
        <PreciosPorPlanta plantas={plantas ?? []} materiales={materiales ?? []} />
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h2 style={{ fontSize: 14, fontWeight: 700, margin: "0 0 4px" }}>Catálogo de materiales</h2>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 12px" }}>
          {materiales?.length ?? 0} materiales. Después de crear uno, asígnale precio en la planta que lo vende.
        </p>
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

      </section>
    </div>
  );
}
