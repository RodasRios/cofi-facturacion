import client from "./client";
import type { User } from "../types";

export type UsuarioDatos = Partial<Pick<User,
  "username" | "email" | "nombre" | "cedula" | "rol" | "cargo" | "telefono" |
  "is_admin" | "is_superadmin" | "is_active">> & { password?: string };

export async function getUsuarios(): Promise<User[]> {
  const res = await client.get("/users/");
  return res.data;
}

export async function crearUsuario(data: UsuarioDatos): Promise<User> {
  const res = await client.post("/users/", data);
  return res.data;
}

export async function actualizarUsuario(id: number, data: UsuarioDatos): Promise<User> {
  const res = await client.patch(`/users/${id}/`, data);
  return res.data;
}

export async function eliminarUsuario(id: number): Promise<void> {
  await client.delete(`/users/${id}/`);
}
