import client from "./client";
import type { User } from "../types";

export interface LoginResult {
  access_token: string;
  token_type: string;
}

export async function login(username: string, password: string): Promise<LoginResult> {
  const res = await client.post("/auth/login", { username, password });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await client.get("/auth/me");
  return res.data;
}

export async function uploadFirma(file: File): Promise<{ firma_path: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.post("/auth/firma", form);
  return res.data;
}

export async function borrarFirma(): Promise<void> {
  await client.delete("/auth/firma");
}

/** La firma propia como blob (la ruta pide el token, un <img src> no lo manda). */
export async function getFirmaBlob(): Promise<Blob> {
  const res = await client.get("/auth/firma", { responseType: "blob" });
  return res.data;
}

export async function actualizarPerfil(
  data: Partial<Pick<User, "nombre" | "email" | "cedula" | "cargo" | "telefono">>,
): Promise<User> {
  const res = await client.patch("/auth/perfil", data);
  return res.data;
}

export async function cambiarPassword(nueva: string, actual?: string): Promise<User> {
  const res = await client.post("/auth/cambiar-password", { nueva, actual });
  return res.data;
}
