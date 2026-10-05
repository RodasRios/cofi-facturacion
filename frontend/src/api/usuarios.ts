import client from "./client";
import type { Permiso, RolClave, User } from "../types";

export type UsuarioDatos = Partial<Pick<User,
  "username" | "email" | "nombre" | "cedula" | "cargo" | "telefono" |
  "is_superadmin" | "is_active" | "roles" | "permisos_extra" | "plantas">> & { password?: string };

export interface PanelUsuarios {
  activos: number;
  inactivos: number;
  administradores: number;
  clave_temporal: number;
  por_rol: Record<RolClave, number>;
  esperando_aprobacion: { cotizaciones: number; pagos: number };
  alertas: { tipo: string; nivel: "grave" | "aviso" | "info"; texto: string }[];
}

export type { Permiso };

export async function getUsuarios(): Promise<User[]> {
  return (await client.get("/users/")).data;
}

export async function getPanelUsuarios(): Promise<PanelUsuarios> {
  return (await client.get("/users/panel/")).data;
}

export async function crearUsuario(data: UsuarioDatos): Promise<User> {
  return (await client.post("/users/", data)).data;
}

export async function actualizarUsuario(id: number, data: UsuarioDatos): Promise<User> {
  return (await client.patch(`/users/${id}/`, data)).data;
}

export async function eliminarUsuario(id: number): Promise<void> {
  await client.delete(`/users/${id}/`);
}
