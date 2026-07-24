from pathlib import Path
from datetime import date
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
)
from reportlab.lib.enums import TA_RIGHT

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


def _build_doc(doc: SimpleDocTemplate, elements: list) -> None:
    doc.build(elements, onFirstPage=_on_page, onLaterPages=_on_page)


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


def generate_cotizacion(
    path: Path, numero: str, fecha: date, cliente_nombre: str, planta_nombre: str,
    items: list[dict], total: Decimal, firma_path: str | None = None, notas: str | None = None,
) -> None:
    doc = _base_doc(path, f"Cotización {numero}")
    elements = _build_header("Formato de Cotización", numero, fecha)
    elements.append(_build_datos_generales([("Cliente", cliente_nombre), ("Planta", planta_nombre)]))
    elements.append(Spacer(1, 14))
    elements.append(_items_table(items))
    elements.append(Spacer(1, 10))

    total_table = Table([[
        Paragraph("<b>TOTAL</b>", ParagraphStyle("tot", fontSize=11, fontName="Helvetica-Bold", textColor=BRAND_BLUE)),
        Paragraph(f"<b>$ {Decimal(total):,.2f}</b>", ParagraphStyle("tot2", fontSize=11, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ]], colWidths=[13.5 * cm, 3.5 * cm])
    total_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, BRAND_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(total_table)

    elements += _build_firma_section(firma_path, "Aprobado por")
    elements += _build_aclaraciones_section(notas)
    _build_doc(doc, elements)


def generate_orden_suministro(
    path: Path, numero: str, fecha: date, cliente_nombre: str, planta_nombre: str,
    items: list[dict], firma_path: str | None = None, notas: str | None = None,
) -> None:
    doc = _base_doc(path, f"Orden de Suministro {numero}")
    elements = _build_header("Formato de Orden de Suministro", numero, fecha)
    elements.append(_build_datos_generales([("Cliente", cliente_nombre), ("Planta despacho", planta_nombre)]))
    elements.append(Spacer(1, 14))
    elements.append(_items_table(items, mostrar_precio=False))
    elements += _build_firma_section(firma_path, "Autorizado por")
    elements += _build_aclaraciones_section(notas)
    _build_doc(doc, elements)


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
