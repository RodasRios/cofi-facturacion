import client from "./client";
import type { User } from "../types";

export async function getUsuarios(): Promise<User[]> {
  const res = await client.get("/users/");
  return res.data;
}

export async function actualizarUsuario(
  id: number, data: Partial<Pick<User, "nombre" | "cargo" | "telefono" | "email">>,
): Promise<User> {
  const res = await client.patch(`/users/${id}/`, data);
  return res.data;
}
