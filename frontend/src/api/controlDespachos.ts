/** Ruta del PDF de control de despachos, para abrirla en el PdfViewerModal. */
export function urlControlDespachos(filtro: {
  cliente: number; desde?: string; hasta?: string; obra?: string;
}): string {
  const params = new URLSearchParams({ cliente: String(filtro.cliente) });
  if (filtro.desde) params.set("desde", filtro.desde);
  if (filtro.hasta) params.set("hasta", filtro.hasta);
  if (filtro.obra) params.set("obra", filtro.obra);
  return `/control-despachos/pdf/?${params.toString()}`;
}
