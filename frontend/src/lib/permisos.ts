import type { Permiso, RolClave, User } from "../types";

/** Mismo catálogo que api/permissions.py::PERMISOS. */
export const PERMISOS: { clave: Permiso; pestana: string; desc: string }[] = [
  { clave: "tablero", pestana: "Tablero", desc: "Ver el tablero, los indicadores y la cartera por cobrar" },
  { clave: "clientes", pestana: "Clientes", desc: "Crear clientes y sus links de vinculación y pedidos" },
  { clave: "solicitudes", pestana: "Solicitudes", desc: "Registrar solicitudes de cotización" },
  { clave: "cotizaciones", pestana: "Cotizaciones", desc: "Armar cotizaciones" },
  { clave: "aprobar_cotizaciones", pestana: "Cotizaciones", desc: "Aprobar o rechazar cotizaciones" },
  { clave: "pagos", pestana: "Pagos", desc: "Registrar pagos, abonos y órdenes de compra" },
  { clave: "aprobar_pagos", pestana: "Pagos", desc: "Aprobar pagos y confirmar órdenes de compra" },
  { clave: "ordenes", pestana: "Órdenes", desc: "Crear órdenes de suministro y notificar a planta" },
  { clave: "despachos", pestana: "Despachos", desc: "Registrar despachos y subir su soporte" },
  { clave: "disponibilidad", pestana: "Disponibilidad", desc: "Actualizar la disponibilidad de material" },
  { clave: "precios", pestana: "Plantas y precios", desc: "Editar plantas, materiales y precios" },
  { clave: "usuarios", pestana: "Usuarios", desc: "Crear usuarios y asignarles roles y permisos" },
];

/**
 * Ni un administrador los tiene por serlo: hay que darlos a propósito
 * (api/permissions.py::EXCLUSIVOS). Aprobar pagos es de financiera.
 */
export const EXCLUSIVOS: Permiso[] = ["aprobar_pagos"];

const TODOS = PERMISOS.map(p => p.clave);

export interface RolInfo {
  clave: RolClave;
  label: string;
  desc: string;
  color: string;
  grupo: "administracion" | "puesto";
  permisos: Permiso[];
}

/** Mismo catálogo que api/permissions.py::ROLES y PERMISOS_DE_ROL (más el color). */
export const ROLES: RolInfo[] = [
  { clave: "admin", label: "Administrador nivel 1", color: "#059669", grupo: "administracion",
    desc: "Todo: aprobar cotizaciones, precios y usuarios. Aprobar pagos solo si se le da aparte.",
    permisos: TODOS.filter(c => !EXCLUSIVOS.includes(c)) },
  { clave: "coordinador", label: "Administrador nivel 2", color: "#7c3aed", grupo: "administracion",
    desc: "Todo el trabajo diario, precios y usuarios, pero no aprueba cotizaciones ni pagos.",
    permisos: TODOS.filter(c => c !== "aprobar_cotizaciones" && c !== "aprobar_pagos") },
  { clave: "comercial", label: "Comercial", color: "#2563eb", grupo: "puesto",
    desc: "Clientes, solicitudes, cotizaciones, registro de pagos y órdenes de suministro.",
    permisos: ["tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"] },
  { clave: "aprobador", label: "Gerencia (aprobador)", color: "#b45309", grupo: "puesto",
    desc: "Aprueba o rechaza las cotizaciones.",
    permisos: ["tablero", "aprobar_cotizaciones"] },
  { clave: "financiera", label: "Financiera", color: "#be185d", grupo: "puesto",
    desc: "Registra y aprueba pagos, confirma órdenes de compra y lleva la cartera.",
    permisos: ["tablero", "pagos", "aprobar_pagos"] },
  { clave: "logistica", label: "Logística", color: "#0e7490", grupo: "puesto",
    desc: "Emite las órdenes de suministro, avisa a la planta y sigue los despachos.",
    permisos: ["tablero", "ordenes", "despachos"] },
  { clave: "despacho", label: "Despacho (báscula)", color: "#4d7c0f", grupo: "puesto",
    desc: "Registra los despachos y sube la foto o PDF del tiquete.",
    permisos: ["despachos"] },
  { clave: "disponibilidad", label: "Disponibilidad (planta)", color: "#15803d", grupo: "puesto",
    desc: "Actualiza qué material hay en planta.",
    permisos: ["disponibilidad"] },
];
export const ADMINISTRACION = ROLES.filter(r => r.grupo === "administracion");
export const PUESTOS = ROLES.filter(r => r.grupo === "puesto");

export function infoRol(clave: string): RolInfo {
  return ROLES.find(r => r.clave === clave)
    ?? { clave: clave as RolClave, label: clave, desc: "", color: "#6b7280", grupo: "puesto", permisos: [] };
}

export function permisosDeRoles(roles: string[]): Set<Permiso> {
  return new Set(roles.flatMap(r => infoRol(r).permisos));
}

/** Mismo cálculo que api/permissions.py::rango. Solo se gestiona hacia abajo. */
export function rangoDeRoles(roles: string[], superadmin = false): number {
  if (superadmin) return 3;
  if (roles.includes("admin")) return 2;
  if (roles.includes("coordinador")) return 1;
  return 0;
}

/** `user.permisos` ya viene con los efectivos (roles ∪ adicionales). */
export function puede(user: User | null | undefined, ...claves: Permiso[]): boolean {
  if (!user) return false;
  return claves.some(c => user.permisos.includes(c));
}

export const NAV: { path: string; icon: string; label: string; permisos: Permiso[] }[] = [
  { path: "/tablero", icon: "dashboard", label: "Tablero", permisos: ["tablero"] },
  { path: "/clientes", icon: "groups", label: "Clientes", permisos: ["clientes"] },
  { path: "/solicitudes", icon: "request_quote", label: "Solicitudes", permisos: ["solicitudes"] },
  { path: "/cotizaciones", icon: "description", label: "Cotizaciones", permisos: ["cotizaciones", "aprobar_cotizaciones"] },
  { path: "/pagos", icon: "payments", label: "Pagos", permisos: ["pagos", "aprobar_pagos"] },
  { path: "/ordenes-suministro", icon: "local_shipping", label: "Órdenes", permisos: ["ordenes"] },
  { path: "/despachos", icon: "inventory", label: "Despachos", permisos: ["despachos"] },
  { path: "/disponibilidad", icon: "inventory_2", label: "Disponibilidad", permisos: ["disponibilidad"] },
  { path: "/admin", icon: "factory", label: "Precios", permisos: ["precios"] },
  { path: "/usuarios", icon: "admin_panel_settings", label: "Usuarios", permisos: ["usuarios"] },
];

/** A dónde mandar al usuario al entrar: su primera pestaña permitida. */
export function rutaInicial(user: User | null | undefined): string {
  return NAV.find(n => puede(user, ...n.permisos))?.path ?? "/configuracion";
}
