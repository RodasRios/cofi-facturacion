import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getPlantas, createPlanta } from "../api/plantas";
import { getMateriales, createMaterial, setPrecioMaterial } from "../api/materiales";
import { Icon } from "../components/ui/Icon";
import type { MaterialTipo } from "../types";

export function AdminPage() {
  const qc = useQueryClient();
  const { data: plantas } = useQuery({ queryKey: ["plantas"], queryFn: getPlantas });
  const { data: materiales } = useQuery({ queryKey: ["materiales"], queryFn: getMateriales });

  const [nombrePlanta, setNombrePlanta] = useState("");
  const [ubicacionPlanta, setUbicacionPlanta] = useState("");
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
    mutationFn: ({ materialId, plantaId, precio }: { materialId: number; plantaId: number; precio: number }) =>
      setPrecioMaterial(materialId, plantaId, precio),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["materiales"] }); toast.success("Precio actualizado"); },
    onError: () => toast.error("No se pudo actualizar el precio"),
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Administración</h1>

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
          <thead><tr><th>Nombre</th><th>Ubicación</th></tr></thead>
          <tbody>
            {plantas?.map(p => <tr key={p.id}><td>{p.nombre}</td><td>{p.ubicacion || "-"}</td></tr>)}
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
              {plantas?.map(p => <th key={p.id}>{p.nombre}</th>)}
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
                  return (
                    <td key={p.id}>
                      <input
                        className="input-base"
                        style={{ width: 90 }}
                        type="number"
                        min="0"
                        step="0.01"
                        defaultValue={precio?.precio_unitario ?? ""}
                        placeholder="—"
                        onBlur={e => {
                          const val = Number(e.target.value);
                          if (val > 0 && val !== Number(precio?.precio_unitario ?? -1)) {
                            precioMut.mutate({ materialId: m.id, plantaId: p.id, precio: val });
                          }
                        }}
                      />
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
