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
