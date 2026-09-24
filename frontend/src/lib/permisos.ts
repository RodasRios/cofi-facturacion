import type { Permiso, User } from "../types";

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
];

/** Plantillas para no marcar casilla por casilla al crear un usuario. */
export const PLANTILLAS: { nombre: string; permisos: Permiso[] }[] = [
  { nombre: "Comercial", permisos: ["tablero", "clientes", "solicitudes", "cotizaciones", "pagos", "ordenes"] },
  { nombre: "Aprobador", permisos: ["tablero", "cotizaciones", "aprobar_cotizaciones"] },
  { nombre: "Financiera", permisos: ["tablero", "pagos", "aprobar_pagos"] },
  { nombre: "Órdenes", permisos: ["ordenes"] },
  { nombre: "Despacho", permisos: ["despachos"] },
  { nombre: "Disponibilidad", permisos: ["disponibilidad"] },
  { nombre: "Todo", permisos: PERMISOS.map(p => p.clave).filter(c => c !== "precios") },
];

export function puede(user: User | null | undefined, ...claves: Permiso[]): boolean {
  if (!user) return false;
  if (user.is_admin) return true;
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
];

/** A dónde mandar al usuario al entrar: su primera pestaña permitida. */
export function rutaInicial(user: User | null | undefined): string {
  return NAV.find(n => puede(user, ...n.permisos))?.path ?? "/configuracion";
}
