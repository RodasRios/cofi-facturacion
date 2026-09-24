from pathlib import Path
from datetime import date
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image, PageBreak
)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.utils import ImageReader

EMPRESA_NOMBRE = "TRITURADOS Y CONCRETOS LTDA"
EMPRESA_PIE = "Flujo Comercial / Materiales · Triturados, agregados y concretos"

TABLE_HEADER_COLOR = colors.HexColor("#1e3a5f")
TABLE_ROW_ALT = colors.HexColor("#eef2f7")
BRAND_BLUE = colors.HexColor("#1e3a5f")
BRAND_MID = colors.HexColor("#4a7ab5")
GRAY_LABEL = colors.HexColor("#64748b")
GRAY_LINE = colors.HexColor("#c5d3e8")
NEAR_BLACK = colors.HexColor("#1a1a2e")
LINE_MEDIUM = colors.HexColor("#888888")

PAGE_W, PAGE_H = A4

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {_MESES_ES[d.month - 1]} de {d.year}"


def _on_page(canvas, doc) -> None:
    """Franja superior de marca + pie de página con numeración — se dibuja en cada página."""
    canvas.saveState()

    # Franja de color superior
    canvas.setFillColor(BRAND_BLUE)
    canvas.rect(0, PAGE_H - 0.3 * cm, PAGE_W, 0.3 * cm, fill=1, stroke=0)
    canvas.setFillColor(BRAND_MID)
    canvas.rect(0, PAGE_H - 0.38 * cm, PAGE_W, 0.08 * cm, fill=1, stroke=0)

    # Pie de página
    canvas.setStrokeColor(GRAY_LINE)
    canvas.setLineWidth(0.6)
    canvas.line(2 * cm, 1.5 * cm, PAGE_W - 2 * cm, 1.5 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY_LABEL)
    canvas.drawString(2 * cm, 1.1 * cm, f"{EMPRESA_NOMBRE} · Documento generado automáticamente por el sistema")
    canvas.drawRightString(PAGE_W - 2 * cm, 1.1 * cm, f"Página {doc.page}")

    canvas.restoreState()


def _base_doc(path: Path, title: str) -> SimpleDocTemplate:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=2.4 * cm,
        bottomMargin=2.2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=title,
    )


def _build_doc(doc: SimpleDocTemplate, elements: list, on_page=None) -> None:
    """Único punto que construye un PDF: garantiza la decoración de página.

    Los formatos oficiales de la empresa (cotización, orden, control de
    despachos) pasan su propio ``on_page`` con el encabezado del logo; el resto
    usa la franja de marca genérica.
    """
    dibujar = on_page or _on_page
    doc.build(elements, onFirstPage=dibujar, onLaterPages=dibujar)


def _h1() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "h1", parent=styles["Title"], fontSize=16, textColor=BRAND_BLUE,
        spaceAfter=1, alignment=0, fontName="Helvetica-Bold", leading=18,
    )


def _label() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle("label", parent=styles["Normal"], fontSize=10, spaceAfter=3, fontName="Helvetica", leading=13)


def _table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), TABLE_HEADER_COLOR),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, TABLE_ROW_ALT]),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",         (1, 0), (1, -1), "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("LINEBELOW",     (0, 0), (-1, 0), 1.5, TABLE_HEADER_COLOR),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ])


def _build_header(titulo: str, numero: str, fecha: date) -> list:
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(EMPRESA_NOMBRE, _h1()),
        Paragraph(EMPRESA_PIE, ParagraphStyle(
            "sub", parent=styles["Normal"], fontSize=8.5, textColor=GRAY_LABEL, spaceAfter=10,
        )),
        HRFlowable(width="100%", thickness=1.3, color=BRAND_BLUE, spaceAfter=12),
        Paragraph(titulo.upper(), ParagraphStyle(
            "titulo", parent=styles["Normal"], fontSize=12.5, fontName="Helvetica-Bold",
            textColor=NEAR_BLACK, spaceAfter=3, characterSpacing=0.3,
        )),
        Paragraph(f"N.° <b>{numero}</b>  ·  {_fecha_larga(fecha)}", _label()),
        Spacer(1, 12),
    ]
    return elements


def _build_datos_generales(pares: list[tuple[str, str]]) -> Table:
    rows = [[Paragraph(f"<b>{k}:</b>", _label()), Paragraph(v or "-", _label())] for k, v in pares]
    t = Table(rows, colWidths=[4.2 * cm, 12.8 * cm])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _build_firma_section(firma_path: str | None, label: str) -> list:
    if not firma_path or not Path(firma_path).exists():
        return []
    try:
        img = Image(firma_path, width=3.5 * cm, height=1.8 * cm, kind="proportional")
    except Exception:
        return []
    styles = getSampleStyleSheet()
    return [
        Spacer(1, 16),
        img,
        HRFlowable(width=4.5 * cm, thickness=0.8, color=LINE_MEDIUM),
        Paragraph(label, ParagraphStyle("firma", parent=styles["Normal"], fontSize=8, textColor=GRAY_LABEL)),
    ]


def _build_firmas_en_blanco(izq: str, der: str) -> list:
    """Dos líneas de firma manuscrita lado a lado, para documentos que se firman en físico."""
    lineas = Table([[
        HRFlowable(width=7 * cm, thickness=0.8, color=LINE_MEDIUM),
        HRFlowable(width=7 * cm, thickness=0.8, color=LINE_MEDIUM),
    ]], colWidths=[8.5 * cm, 8.5 * cm])
    etiquetas = Table([[
        Paragraph(izq, ParagraphStyle("f1", fontSize=8, textColor=GRAY_LABEL, leading=11)),
        Paragraph(der, ParagraphStyle("f2", fontSize=8, textColor=GRAY_LABEL, leading=11)),
    ]], colWidths=[8.5 * cm, 8.5 * cm])
    return [Spacer(1, 36), lineas, etiquetas]


def _build_aclaraciones_section(text: str | None = None) -> list:
    styles = getSampleStyleSheet()
    elements = [Spacer(1, 22), Paragraph("Observaciones", ParagraphStyle(
        "obs", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=GRAY_LABEL, spaceAfter=6,
    ))]
    if text:
        elements.append(Paragraph(text, _label()))
        elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    return elements


def _items_table(items: list[dict], mostrar_precio: bool = True) -> Table:
    """Tabla de materiales. mostrar_precio=False para documentos internos de entrega
    (orden de suministro, despacho) donde el precio no aplica — solo cantidades."""
    if mostrar_precio:
        header = ["Material", "Cantidad", "Unidad", "Precio unit.", "Subtotal"]
        rows = [header]
        for it in items:
            cantidad = Decimal(str(it["cantidad"]))
            precio = it.get("precio_unitario")
            if precio is not None:
                precio = Decimal(str(precio))
                subtotal = cantidad * precio
                rows.append([
                    it["material_nombre"], f"{cantidad:g}", it.get("unidad_medida", ""),
                    f"$ {precio:,.2f}", f"$ {subtotal:,.2f}",
                ])
            else:
                rows.append([it["material_nombre"], f"{cantidad:g}", it.get("unidad_medida", ""), "-", "-"])
        t = Table(rows, colWidths=[6.5 * cm, 2.3 * cm, 2 * cm, 3.1 * cm, 3.1 * cm])
    else:
        header = ["Material", "Cantidad", "Unidad"]
        rows = [header]
        for it in items:
            cantidad = Decimal(str(it["cantidad"]))
            rows.append([it["material_nombre"], f"{cantidad:g}", it.get("unidad_medida", "")])
        t = Table(rows, colWidths=[9.5 * cm, 3.5 * cm, 4 * cm])
    t.setStyle(_table_style())
    return t


def generate_despacho(
    path: Path, numero: str, fecha: date, cliente_nombre: str, planta_nombre: str,
    items: list[dict], recibido_por: str | None = None, placa_vehiculo: str | None = None,
    cliente_retira: bool = True, notas: str | None = None,
) -> None:
    doc = _base_doc(path, f"Remisión {numero}")
    elements = _build_header("Control de Despacho y Recibo de Material (Remisión)", numero, fecha)
    elements.append(_build_datos_generales([
        ("Cliente", cliente_nombre),
        ("Planta", planta_nombre),
        ("Retira", "Cliente" if cliente_retira else "Transporte propio"),
        ("Placa vehículo", placa_vehiculo or "-"),
    ]))
    elements.append(Spacer(1, 14))
    elements.append(_items_table(items, mostrar_precio=False))
    elements += _build_firmas_en_blanco(
        f"Recibido por: {recibido_por or '_______________________'}<br/>Firma de recibido",
        "Entregado por (Planta)<br/>Firma autorizada",
    )
    elements += _build_aclaraciones_section(notas)
    _build_doc(doc, elements)


def generate_vinculacion(
    path: Path, numero: str, fecha: date, cliente: dict, notas: str | None = None,
) -> None:
    """Formato de Vinculación de Cliente — cliente: {nombre, nit, telefono, email, direccion}."""
    doc = _base_doc(path, f"Vinculación {numero}")
    elements = _build_header("Formato de Vinculación de Cliente", numero, fecha)
    elements.append(_build_datos_generales([
        ("Nombre / Razón social", cliente.get("nombre")),
        ("NIT / Cédula", cliente.get("nit")),
        ("Teléfono", cliente.get("telefono")),
        ("Correo electrónico", cliente.get("email")),
        ("Dirección", cliente.get("direccion")),
    ]))
    elements.append(Spacer(1, 18))
    elements.append(Paragraph(
        "Mediante la firma del presente documento, el cliente relacionado solicita y autoriza su "
        "vinculación comercial con TRITURADOS Y CONCRETOS LTDA, y declara que la información "
        "suministrada es veraz y verificable. El tratamiento de los datos personales aquí registrados "
        "se realizará exclusivamente para fines comerciales, de facturación y de contacto, conforme a "
        "la política de tratamiento de datos de la empresa.",
        ParagraphStyle("terms", fontSize=9.5, textColor=NEAR_BLACK, leading=14, alignment=0),
    ))
    elements += _build_firmas_en_blanco(
        "Firma del Cliente<br/>C.C. / NIT",
        "Firma Autorizada<br/>Triturados y Concretos Ltda",
    )
    elements += _build_aclaraciones_section(notas)
    _build_doc(doc, elements)


# ═══════════════════════════════════════════════════════════════════════════
# Formatos oficiales de la empresa
#
# Calcados de los formatos que Triturados y Concretos ya usa en papel/Excel:
# FR-GC-08 (cotización), la orden de suministro y el control de despacho de
# materiales. Llevan el cuadro con el logo arriba en cada página y el pie con la
# dirección de la empresa, en tamaño carta como los originales.
# ═══════════════════════════════════════════════════════════════════════════

from services.notas_cotizacion import elegidas  # noqa: E402

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo_tyc.png"


def _escapar(texto: str) -> str:
    """Texto escrito por un usuario: los < y & romperían el marcado de ReportLab."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

EMPRESA_CIUDAD = "Cartago, Valle del Cauca"
EMPRESA_DIRECCION = "Carrera 4 No. 54-75 Cartago – Valle del Cauca"
EMPRESA_CELULAR = "312 834 2898"
EMPRESA_WEB = "https://www.trituradosyconcretos.com/"
EMPRESA_EMAIL = "comercial@trituradosyconcretos.com"

NARANJA = colors.HexColor("#d2601a")
LINK_AZUL = colors.HexColor("#1a0dab")
BORDE = colors.black


def _cop(valor) -> str:
    """Pesos al estilo colombiano: 44.000 (sin decimales, punto de miles)."""
    return f"{int(round(Decimal(str(valor)))):,}".replace(",", ".")


def _cantidad(valor, decimales: int | None = None) -> str:
    """16,04 / 128 — coma decimal. Sin `decimales`, quita los ceros sobrantes."""
    d = Decimal(str(valor))
    d = d.quantize(Decimal(1).scaleb(-decimales)) if decimales is not None else d.normalize()
    txt = f"{d:f}"
    if "." in txt:
        entero, dec = txt.split(".")
        return f"{int(entero):,}".replace(",", ".") + "," + dec
    return f"{int(txt):,}".replace(",", ".")


def _fecha_carta(d: date) -> str:
    """marzo 27 de 2026 — como encabeza la empresa sus cartas."""
    return f"{_MESES_ES[d.month - 1]} {d.day} de {d.year}"


def numero_cotizacion_formal(numero: str) -> str:
    """160-2026 → 160-2.026, como se imprime en el formato FR-GC-08."""
    if "-" in numero:
        consecutivo, anio = numero.rsplit("-", 1)
        if anio.isdigit():
            return f"{consecutivo}-{int(anio):,}".replace(",", ".")
    return numero


def _on_page_formato(titulo: str, lineas_derecha: list[str]):
    """Encabezado en cuadro (logo | título | código) + pie con la dirección."""

    def dibujar(canvas, doc):
        ancho, alto = doc.pagesize
        canvas.saveState()

        # Cuadro superior de tres celdas, como los formatos de la empresa.
        bx, bw, bh = 1.9 * cm, ancho - 3.8 * cm, 1.75 * cm
        by = alto - 1.3 * cm - bh
        c1, c3 = 4.9 * cm, 4.3 * cm
        canvas.setStrokeColor(BORDE)
        canvas.setLineWidth(0.8)
        canvas.rect(bx, by, bw, bh, stroke=1, fill=0)
        canvas.line(bx + c1, by, bx + c1, by + bh)
        canvas.line(bx + bw - c3, by, bx + bw - c3, by + bh)

        if LOGO_PATH.exists():
            canvas.drawImage(
                ImageReader(str(LOGO_PATH)), bx + 0.2 * cm, by + 0.18 * cm,
                width=c1 - 0.4 * cm, height=bh - 0.36 * cm,
                preserveAspectRatio=True, anchor="c", mask="auto",
            )

        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Oblique", 11)
        canvas.drawCentredString(bx + c1 + (bw - c1 - c3) / 2, by + bh / 2 - 3, titulo)

        canvas.setFont("Helvetica", 9.5)
        cx = bx + bw - c3 / 2
        n = len(lineas_derecha)
        for i, linea in enumerate(lineas_derecha):
            canvas.drawCentredString(cx, by + bh / 2 + (n - 1) * 6 - i * 12 - 3, linea)

        # Pie con los datos de contacto, centrado.
        canvas.setFont("Times-BoldItalic", 9)
        base = 1.55 * cm
        canvas.drawCentredString(ancho / 2, base + 30, EMPRESA_DIRECCION)
        canvas.drawCentredString(ancho / 2, base + 20, f"Celular: {EMPRESA_CELULAR}")
        canvas.setFillColor(LINK_AZUL)
        canvas.drawCentredString(ancho / 2, base + 10, EMPRESA_WEB)
        canvas.setFillColor(colors.black)
        canvas.drawCentredString(ancho / 2, base, f"E-mail: {EMPRESA_EMAIL}")

        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY_LABEL)
        canvas.drawRightString(ancho - 1.9 * cm, 0.8 * cm, f"Página {doc.page}")
        canvas.restoreState()

    return dibujar


def _doc_formato(destino, titulo: str, pagesize=LETTER) -> SimpleDocTemplate:
    if isinstance(destino, Path):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino = str(destino)
    return SimpleDocTemplate(
        destino, pagesize=pagesize, title=titulo,
        topMargin=3.6 * cm, bottomMargin=3.4 * cm,
        leftMargin=2.3 * cm, rightMargin=2.3 * cm,
    )


def _p(texto: str, size=11, bold=False, align=TA_JUSTIFY, leading=None, italic=False, color=colors.black):
    fuente = "Helvetica-BoldOblique" if bold and italic else (
        "Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica"))
    return Paragraph(texto, ParagraphStyle(
        "p", fontName=fuente, fontSize=size, leading=leading or size * 1.35,
        alignment=align, textColor=color,
    ))


def _cuadro_control(filas: list[list[str]], anchos: list[float]) -> Table:
    """Cuadro Realizó / Revisó / Aprobó del sistema de gestión documental."""
    datos = [[_p(c, size=8.5, align=TA_LEFT, leading=10.5) for c in fila] for fila in filas]
    t = Table(datos, colWidths=anchos)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _bloque_firma(firmante: dict) -> list:
    """Firma del comercial: imagen guardada (si subió una) + nombre y datos."""
    elementos = []
    firma = firmante.get("firma_path")
    if firma and Path(firma).exists():
        try:
            elementos.append(Image(firma, width=4 * cm, height=1.9 * cm, kind="proportional", hAlign="LEFT"))
        except Exception:
            elementos.append(Spacer(1, 1.6 * cm))
    else:
        elementos.append(Spacer(1, 1.6 * cm))
    elementos.append(_p(f"<b>{_escapar((firmante.get('nombre') or '').upper())}</b>", size=11, align=TA_LEFT))
    if firmante.get("cargo"):
        elementos.append(_p(_escapar(firmante["cargo"]), size=11, align=TA_LEFT))
    if firmante.get("telefono"):
        elementos.append(_p(f"Cel.: {_escapar(firmante['telefono'])}", size=11, align=TA_LEFT))
    correo = firmante.get("email") or EMPRESA_EMAIL
    elementos.append(_p(
        f'Correo: <font color="#1a0dab"><u>{_escapar(correo)}</u></font>', size=11, align=TA_LEFT))
    return elementos


# ─── Cotización FR-GC-08 ───────────────────────────────────────────────────

_COT_INTRO = (
    "Reciba un cordial saludo en nombre de Triturados y Concretos Ltda., una empresa con "
    "más de veinte (20) años de experiencia en la producción y suministro de agregados "
    "pétreos, mezclas asfálticas, concreto hidráulico y construcción de obras de ingeniería "
    "civil, ahora con el ánimo de expandir nuestros servicios, ofrecemos nuestras nuevas "
    "líneas de negocio, por una parte “Soluciones de Ingeniería Metalmecánica - SIM”, un "
    "área dedicada al mantenimiento y montaje de equipos industriales y estructuras "
    "metálicas y, por otra parte, “Prefabricados” para el mercado de la construcción y la industria."
)



_COT_OBSERVACIONES = [
    "La presente cotización es de carácter informativo y no constituye una obligación ni promesa de "
    "suministro por parte de Triturados y Concretos Ltda. El suministro se entenderá formalizado "
    "únicamente una vez el cliente notifique mediante la emisión de una Orden de Compra, junto con su "
    "respectivo anexo de condiciones en caso de ser necesario, la cual formaliza el acuerdo de "
    "voluntades. Dicha Orden de Compra no podrá ser cedida total ni parcialmente sin el consentimiento "
    "previo y expreso de Triturados y Concretos Ltda.",
    "Posterior a esto, el cliente puede realizar el pago y enviar el comprobante de consignación al "
    f"correo electrónico {EMPRESA_EMAIL} o al WhatsApp 3128342898.",
    "Una vez confirmado el ingreso del pago por parte de la entidad bancaria, se procederá a autorizar "
    "el despacho del material, para lo cual el cliente deberá suministrar previamente las placas de los "
    "vehículos autorizados para el ingreso a planta.",
    "Los certificados de retención en la fuente deberán ser expedidos y entregados inmediatamente una "
    "vez se realicen los pagos de las facturas correspondientes.",
]

_COT_TRANSPORTE = [
    "Presentar Cédula de ciudadanía, Licencia de conducción y Planilla de seguridad social vigente del "
    "conductor que vaya a ingresar a las instalaciones de forma temporal o permanente según "
    "normatividad al respecto.",
    "Tarjeta de propiedad, soat y revisión técnico-mecánica.",
    "La afiliación a ARL de los transportadores debe ser por mínimo riesgo 5.",
    "No se ingresará bajo efectos de alcohol o sustancias psicoactivas.",
    "Acatará todas las recomendaciones de seguridad durante su actividad en las instalaciones de "
    "Triturados y Concretos Ltda., así mismo respetará al interior de las plantas, los límites de "
    "acceso restringido para personal externo.",
    "No está autorizado el ingreso de menores de edad a las plantas de Triturados y Concretos Ltda.",
    "No está permitido realizar labores de mantenimiento a vehículos en el interior de las instalaciones",
    "Si se presenta un derrame de líquidos que provengan de los vehículos, el responsable de la "
    "limpieza y recolección es el conductor.",
    "EPP - Usar todos los Elementos de Protección Personal requeridos (botas con puntera, casco, "
    "guantes, chaleco reflectivo etc.), no es permitido utilizar anillos, relojes o joyas.",
]


def _viñeta(texto: str, marca: str = "•") -> Paragraph:
    return Paragraph(texto, ParagraphStyle(
        "vin", fontName="Helvetica", fontSize=11, leading=15, alignment=TA_JUSTIFY,
        leftIndent=0.9 * cm, bulletIndent=0.25 * cm, spaceAfter=2,
    ), bulletText=marca)


def _tabla_cotizacion(grupos: list[dict], subtotal, iva, iva_pct, total, anio: int,
                      subtotal_materiales=None, ajustes=None) -> Table:
    """Una sección por planta (SUMINISTRO DE PLANTA X 2026) y totales al final."""
    anchos = [1.1 * cm, 7.0 * cm, 1.7 * cm, 1.8 * cm, 3.0 * cm, 2.6 * cm]
    fila_style = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=9.5)
    datos, estilo, item = [], [], 1

    for g in grupos:
        r = len(datos)
        datos.append([f"SUMINISTRO DE {g['planta'].upper()} {anio}", "", "", "", "", ""])
        estilo += [("SPAN", (0, r), (-1, r)), ("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"),
                   ("ALIGN", (0, r), (-1, r), "CENTER")]
        datos.append(["ITEM", "DESCRIPCION", "UNIDAD", "CANTIDAD", "VR. UNIT. SIN IVA", "SUB TOTAL"])
        estilo += [("FONTNAME", (0, r + 1), (-1, r + 1), "Helvetica-Bold"),
                   ("ALIGN", (0, r + 1), (-1, r + 1), "CENTER"),
                   ("LINEABOVE", (0, r + 1), (-1, r + 1), 1.2, BORDE)]
        for it in g["items"]:
            datos.append([
                str(item), Paragraph(_escapar(it["descripcion"].upper()), fila_style),
                (it["unidad"] or "").upper(), _cantidad(it["cantidad"]),
                f"$ {_cop(it['precio'])}",
                f"$ {_cop(it['subtotal'])}",
            ])
            fila = len(datos) - 1
            estilo += [("ALIGN", (0, fila), (0, fila), "CENTER"),
                       ("ALIGN", (2, fila), (3, fila), "CENTER"),
                       ("ALIGN", (4, fila), (5, fila), "RIGHT")]
            item += 1

    # Pie de totales. Con cargos o descuentos, se muestra primero lo de
    # materiales y cada ajuste antes del subtotal, para que cuadre a la vista.
    pie = []
    if ajustes:
        pie.append(("SUBTOTAL MATERIALES", subtotal_materiales))
        for aj in ajustes:
            pie.append((aj["descripcion"].upper(), aj["valor"]))
    pie += [("SUBTOTAL", subtotal), ("IVA", iva), ("TOTAL", total)]

    r = len(datos)
    for etiqueta, valor in pie:
        signo = "-" if Decimal(str(valor)) < 0 else ""
        datos.append(["", "", etiqueta, "", "", f"{signo}$ {_cop(abs(Decimal(str(valor))))}"])
    fin = len(datos) - 1
    estilo += [
        ("SPAN", (0, r), (1, fin)),
        ("FONTNAME", (2, r), (4, fin), "Helvetica-Bold"),
        ("FONTNAME", (5, fin), (5, fin), "Helvetica-Bold"),
        ("ALIGN", (5, r), (5, fin), "RIGHT"),
    ]
    for fila in range(r, fin + 1):
        estilo.append(("SPAN", (2, fila), (4, fila)))

    t = Table(datos, colWidths=anchos, repeatRows=0)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
        ("BOX", (0, 0), (-1, -1), 1, BORDE),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ] + estilo))
    return t


def generate_cotizacion(path: Path, datos: dict) -> None:
    """Formato FR-GC-08.

    datos: numero, fecha, cliente {nombre, nit, telefono, email}, grupos
    [{planta, items [{descripcion, unidad, cantidad, precio, subtotal}]}],
    subtotal, iva, iva_porcentaje, total, plantas [(nombre, ubicacion)],
    firmante {nombre, cargo, telefono, email, firma_path}, notas.
    """
    fecha: date = datos["fecha"]
    doc = _doc_formato(path, f"Cotización {datos['numero']}")
    cli = datos["cliente"]
    e = [
        Spacer(1, 4),
        _p(f"<b>{EMPRESA_CIUDAD}, {_fecha_carta(fecha)}.</b>", size=12, align=TA_LEFT),
        Spacer(1, 16),
        _p(f"<b>COT: {numero_cotizacion_formal(datos['numero'])}</b>", size=12, align=TA_RIGHT),
        Spacer(1, 18),
        _p("“Recuerda que la calidad de los materiales de construcción es uno de los factores que, "
           "con un adecuado diseño e instalación, garantizan el éxito y durabilidad de las obras”.",
           size=8.5, align=TA_CENTER),
        Spacer(1, 14),
        _p("<b>Señores:</b>", size=12, align=TA_LEFT),
        _p(f"<b>{_escapar((cli.get('nombre') or '').upper())}</b>", size=12, align=TA_LEFT, leading=17),
    ]
    if cli.get("nit"):
        e.append(_p(f"<b>NIT:</b> {_escapar(cli['nit'])}", size=12, align=TA_LEFT, leading=17))
    if cli.get("telefono"):
        e.append(_p(f"<b>Teléfono:</b> {_escapar(cli['telefono'])}", size=12, align=TA_LEFT, leading=17))
    if cli.get("email"):
        e.append(_p(f'<b>Correo electrónico:</b> <font color="#1a0dab"><u>{_escapar(cli["email"])}</u></font>',
                    size=12, align=TA_LEFT, leading=17))
    e += [
        Spacer(1, 14),
        _p("REF: <b>SUMINISTRO DE GRANULARES PLANTA TRITURADOS Y CONCRETOS LTDA.</b>", size=11, align=TA_LEFT),
        Spacer(1, 12),
        _p(_COT_INTRO, size=11.5, leading=16),
        Spacer(1, 12),
        _p("Agradezco de ante mano su confianza en nuestra empresa y en respuesta a su solicitud me "
           "permito presentar la propuesta económica de los materiales requeridos:", size=11.5, leading=16),
        Spacer(1, 16),
        _tabla_cotizacion(datos["grupos"], datos["subtotal"], datos["iva"],
                          datos["iva_porcentaje"], datos["total"], fecha.year,
                          subtotal_materiales=datos.get("subtotal_materiales"),
                          ajustes=datos.get("ajustes")),
        Spacer(1, 16),
        _p("<b>Validez de la oferta:</b> 15 días.", align=TA_LEFT),
        _p("<b>Forma de pago:</b> Anticipado.", align=TA_LEFT),
        Spacer(1, 10),
        _p("<b>NOTAS ACLARATORIAS:</b>", align=TA_LEFT),
        Spacer(1, 4),
    ]
    notas = elegidas(datos.get("notas_aclaratorias"))
    e += [_viñeta(n["texto"]) for n in notas if n["posicion"] == "antes"]

    for nombre, ubicacion in datos.get("plantas", []):
        texto = f"<b>UBICACIÓN DE LA PLANTA:</b> El suministro se contempla en la {nombre}"
        texto += f", ubicada en {ubicacion}." if ubicacion else "."
        e.append(_viñeta(texto))

    e += [_viñeta(n["texto"]) for n in notas if n["posicion"] == "despues"]
    # Notas extra del comercial: una viñeta por línea escrita.
    for linea in (datos.get("notas") or "").splitlines():
        if linea.strip():
            e.append(_viñeta(_escapar(linea.strip())))

    e += [Spacer(1, 12), _p("<b>Observaciones.</b>", align=TA_LEFT), Spacer(1, 4)]
    for texto in _COT_OBSERVACIONES:
        e += [_p(texto, leading=15), Spacer(1, 8)]

    e += [Spacer(1, 10), _p("Atentamente,", align=TA_LEFT)]
    e += _bloque_firma(datos["firmante"])

    e += [
        PageBreak(),
        _p("<b>NOTAS IMPORTANTE-TRANSPORTE DE MATERIALES.</b>", align=TA_LEFT),
        Spacer(1, 8),
        _p("Estimado cliente nuestra seguridad y la suya es muy importante para nosotros por favor "
           "tener en cuenta las siguientes obligaciones para el ingreso de los vehículos de carga a "
           "nuestras instalaciones:", leading=15),
        Spacer(1, 6),
    ]
    e += [_viñeta(t, marca="✓") for t in _COT_TRANSPORTE]
    e += [
        Spacer(1, 24),
        _cuadro_control(
            [["Realizó: Líder Gestión Comercial", "Revisó: Gerencia Asesor externo", "Aprobó: Gerencia"],
             ["Fecha de creación: 16-06-2022", "Fecha de revisión: 18-08-2022",
              "Fecha de aprobación: 18-08-2022"]],
            [5.8 * cm, 5.8 * cm, 5.4 * cm],
        ),
    ]
    _build_doc(doc, e, on_page=_on_page_formato("COTIZACIÓN", ["FR-GC-08", "Versión:01"]))


# ─── Orden de suministro ───────────────────────────────────────────────────

def generate_orden_suministro(path: Path, datos: dict) -> None:
    """Formato de orden de suministro.

    datos: numero, fecha, cliente, obra, planta, items [{material, cantidad,
    unidad}], fecha_suministro, placas_empresa [..], placas_cliente [..],
    observacion, autoriza {nombre, area}.
    """
    doc = _doc_formato(path, f"Orden de suministro {datos['numero']}")
    lbl = ParagraphStyle("l", fontName="Helvetica-Bold", fontSize=11, leading=13)
    val = ParagraphStyle("v", fontName="Helvetica-Bold", fontSize=11, leading=13, alignment=TA_CENTER)

    def fila(etiqueta, valor):
        return [Paragraph(etiqueta, lbl), "", Paragraph(valor or "", val), ""]

    items = datos["items"]
    unidad = (items[0]["unidad"] if items else "m3").upper()
    mismas_unidades = len({(i["unidad"] or "").lower() for i in items}) <= 1

    filas = [
        fila("FECHA", datos["fecha"].strftime("%d/%m/%Y")),
        fila("NOMBRE DEL CLIENTE O RAZON SOCIAL", (datos["cliente"] or "").upper()),
        fila("OBRA", (datos.get("obra") or "").upper()),
        fila("CODIGO", "SUMINISTRO"),
    ]
    for it in items:
        u = (it["unidad"] or "").upper()
        filas.append(fila("MATERIAL", it["material"].upper()))
        filas.append(fila(f"CANTIDAD ({u})", f"{_cantidad(it['cantidad'])} {u}"))
    filas += [
        fila("PLANTA", datos["planta"].upper().replace("PLANTA ", "")),
        fila("FECHA SUMINISTRO",
             datos["fecha_suministro"].strftime("%d/%m/%Y") if datos.get("fecha_suministro") else ""),
    ]
    if mismas_unidades and items:
        total = sum(Decimal(str(i["cantidad"])) for i in items)
        filas.append(fila(f"CANTIDAD TOTAL PEDIDO ({unidad})", f"{_cantidad(total)} {unidad}"))

    n_datos = len(filas)
    filas.append([Paragraph("TRANSPORTE", val), "", "", ""])
    filas.append([Paragraph("TRITURADOS Y CONCRETOS", val), "", Paragraph("CLIENTE", val), ""])

    empresa = datos.get("placas_empresa") or []
    cliente = datos.get("placas_cliente") or []
    n_placas = max(3, len(empresa), len(cliente))
    ini_placas = len(filas)
    for i in range(n_placas):
        filas.append([
            Paragraph("PLACAS VEHICULOS", val) if i == 0 else "",
            Paragraph(empresa[i], val) if i < len(empresa) else "",
            Paragraph(cliente[i], val) if i < len(cliente) else "",
            "",
        ])
    obs = len(filas)
    filas.append([Paragraph("<i>OBSERVACION</i>", val), Paragraph(datos.get("observacion") or "",
                  ParagraphStyle("o", fontName="Helvetica", fontSize=10, leading=12)), "", ""])
    aut = len(filas)
    autoriza = datos.get("autoriza") or {}
    filas.append([Paragraph("AUTORIZO", val), Paragraph((autoriza.get("nombre") or "").upper(), val), "", ""])
    filas.append(["", Paragraph(autoriza.get("area") or "ÁREA COMERCIAL",
                                ParagraphStyle("a", fontName="Helvetica", fontSize=10, alignment=TA_CENTER)), "", ""])

    anchos = [5.4 * cm, 3.6 * cm, 3.6 * cm, 4.4 * cm]
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.6, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("SPAN", (0, n_datos), (-1, n_datos)),
        ("SPAN", (0, n_datos + 1), (1, n_datos + 1)),
        ("SPAN", (2, n_datos + 1), (3, n_datos + 1)),
        ("SPAN", (0, ini_placas), (0, ini_placas + n_placas - 1)),
        ("SPAN", (2, ini_placas), (3, ini_placas)),
        ("SPAN", (1, obs), (-1, obs)),
        ("SPAN", (1, aut), (-1, aut)),
        ("SPAN", (1, aut + 1), (-1, aut + 1)),
        ("SPAN", (0, aut), (0, aut + 1)),
    ]
    for r in range(n_datos):
        estilo += [("SPAN", (0, r), (1, r)), ("SPAN", (2, r), (3, r))]
    # Filas alternas en gris claro, como el formato en Excel.
    for r in range(0, n_datos, 2):
        estilo.append(("BACKGROUND", (0, r), (-1, r), colors.HexColor("#efefef")))
    for r in range(ini_placas + 1, ini_placas + n_placas):
        estilo.append(("SPAN", (2, r), (3, r)))

    t = Table(filas, colWidths=anchos)
    t.setStyle(TableStyle(estilo))

    e = [
        Spacer(1, 10),
        t,
        Spacer(1, 22),
        _cuadro_control(
            [["Realizó:", "Revisó:", "Aprobó:"],
             ["Líder Gestión comercial", "Gerencia, Asesor externo", "Gerencia"],
             ["Fecha creación: 16-06-2022", "Fecha de revisión:", "Fecha de aprobación:"]],
            [8.0 * cm, 4.8 * cm, 4.2 * cm],
        ),
    ]
    _build_doc(doc, e, on_page=_on_page_formato("ORDEN DE SUMINISTRO", [datos["numero"]]))


# ─── Control de despacho de materiales ─────────────────────────────────────

def generate_control_despachos(datos: dict) -> bytes:
    """Consolidado por cliente de lo despachado, con valores. Devuelve el PDF.

    No se guarda en disco: es un reporte que se arma al vuelo con el rango
    pedido, no un formato emitido una sola vez.

    datos: cliente {nombre, nit, direccion, telefono}, filas [{planta, fecha,
    consecutivo, empresa, obra, placa, material, cantidad, valor_unitario,
    valor_total}], total_cantidad, subtotal, iva_porcentaje, iva, total,
    elaboro {nombre, cargo}, reviso {nombre, cargo}.
    """
    buf = BytesIO()
    pagina = landscape(LETTER)
    doc = SimpleDocTemplate(
        buf, pagesize=pagina, title="Control de despacho de materiales",
        topMargin=1.2 * cm, bottomMargin=1.4 * cm, leftMargin=1.2 * cm, rightMargin=1.2 * cm,
    )
    ancho_util = pagina[0] - 2.4 * cm

    logo = (Image(str(LOGO_PATH), width=5.6 * cm, height=1.7 * cm, kind="proportional")
            if LOGO_PATH.exists() else "")
    titulo = Table([["CONTROL DE DESPACHO DE MATERIALES"]], colWidths=[ancho_util - 7 * cm])
    titulo.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, BORDE),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    cabecera = Table([[logo, titulo]], colWidths=[7 * cm, ancho_util - 7 * cm])
    cabecera.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    cli = datos["cliente"]
    et = ParagraphStyle("et", fontName="Helvetica-Bold", fontSize=9.5, alignment=TA_RIGHT, leading=12)
    vl = ParagraphStyle("vl", fontName="Helvetica-Bold", fontSize=9.5, leading=12)
    contratante = Table([
        [Paragraph("CONTRATANTE:", et), Paragraph((cli.get("nombre") or "").upper(), vl)],
        [Paragraph("NIT:", et), Paragraph(cli.get("nit") or "-", vl)],
        [Paragraph("Dirección:", et), Paragraph(cli.get("direccion") or "-", vl)],
        [Paragraph("Teléfono", et), Paragraph(cli.get("telefono") or "-", vl)],
    ], colWidths=[3.4 * cm, 14 * cm], hAlign="LEFT")
    contratante.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))

    celda = ParagraphStyle("cd", fontName="Helvetica", fontSize=7.5, leading=9)
    enc = ["PLANTA", "FECHA", "CODIGO", "CONSECUTIVO", "EMPRESA", "OBRA", "PLACA",
           "MATERIAL", "CANTIDAD", "VALOR M3", "VALOR TOTAL"]
    anchos = [2.0, 1.8, 2.0, 2.1, 4.6, 3.3, 1.7, 3.4, 1.7, 1.9, 2.3]
    escala = ancho_util / (sum(anchos) * cm)
    anchos = [a * cm * escala for a in anchos]

    filas = [enc]
    for f in datos["filas"]:
        filas.append([
            Paragraph(f["planta"], celda), f["fecha"].strftime("%d/%m/%Y"), "SUMINISTRO",
            f.get("consecutivo") or "-", Paragraph((f["empresa"] or "").upper(), celda),
            Paragraph((f.get("obra") or "-").upper(), celda), (f.get("placa") or "-").upper(),
            Paragraph(f["material"].upper(), celda), _cantidad(f["cantidad"], 2),
            f"$ {_cop(f['valor_unitario'])}", f"$ {_cop(f['valor_total'])}",
        ])
    if len(filas) == 1:
        filas.append(["Sin despachos en el período seleccionado", "", "", "", "", "", "", "", "", "", ""])

    t = Table(filas, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), NARANJA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (8, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (1, 1), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#d9d9d9")),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if not datos["filas"]:
        estilo.append(("SPAN", (0, 1), (-1, 1)))
    t.setStyle(TableStyle(estilo))

    ult = anchos[-3:]
    total_m3 = Table([["TOTAL m3", _cantidad(datos["total_cantidad"], 2)]],
                     colWidths=[sum(anchos[7:8]), anchos[8]], hAlign="RIGHT")
    total_m3.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, BORDE), ("INNERGRID", (0, 0), (-1, -1), 0.8, BORDE),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
    ]))
    pct = f"{Decimal(str(datos['iva_porcentaje'])):g}"
    totales = Table([
        ["SUBTOTAL", "$", _cop(datos["subtotal"])],
        [f"IVA {pct}%", "$", _cop(datos["iva"])],
        ["TOTAL", "$", _cop(datos["total"])],
    ], colWidths=[ult[0], 0.5 * cm, ult[2] + ult[1] - 0.5 * cm], hAlign="RIGHT")
    totales.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"), ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))

    def bloque(titulo_bloque, persona):
        persona = persona or {}
        return [
            [Paragraph(f"<b>{titulo_bloque}</b>", vl), ""],
            [Paragraph("<b>Nombre:</b>", vl), Paragraph((persona.get("nombre") or "").upper(), vl)],
            [Paragraph("<b>Cargo:</b>", vl), Paragraph((persona.get("cargo") or "").upper(), vl)],
        ]

    izq = Table(bloque("Elaboró:", datos.get("elaboro")), colWidths=[2.2 * cm, 8 * cm])
    der = Table(bloque("Revisó:", datos.get("reviso")), colWidths=[2.2 * cm, 8 * cm])
    firmas = Table([[izq, der]], colWidths=[ancho_util / 2, ancho_util / 2])

    e = [cabecera, Spacer(1, 10), contratante, Spacer(1, 10), t, Spacer(1, 8), total_m3,
         Spacer(1, 8), totales, Spacer(1, 22), firmas]

    def pie(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRAY_LABEL)
        canvas.drawString(1.2 * cm, 0.7 * cm, f"{EMPRESA_NOMBRE} · {EMPRESA_DIRECCION} · {EMPRESA_EMAIL}")
        canvas.drawRightString(pagina[0] - 1.2 * cm, 0.7 * cm, f"Página {d.page}")
        canvas.restoreState()

    _build_doc(doc, e, on_page=pie)
    return buf.getvalue()
