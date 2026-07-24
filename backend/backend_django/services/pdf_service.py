from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

EMPRESA_NOMBRE = "TRITURADOS Y CONCRETOS LTDA"

TABLE_HEADER_COLOR = colors.HexColor("#1e3a5f")
TABLE_ROW_ALT = colors.HexColor("#eef2f7")
BRAND_BLUE = colors.HexColor("#1e3a5f")
GRAY_LABEL = colors.HexColor("#64748b")
NEAR_BLACK = colors.HexColor("#1a1a2e")

_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_larga(d: date) -> str:
    return f"{d.day} de {_MESES_ES[d.month - 1]} de {d.year}"


def _base_doc(path: Path, title: str) -> SimpleDocTemplate:
    path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=2.2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        title=title,
    )


def _h1() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        "h1", parent=styles["Title"], fontSize=15, textColor=BRAND_BLUE,
        spaceAfter=2, alignment=TA_LEFT, fontName="Helvetica-Bold",
    )


def _label() -> ParagraphStyle:
    styles = getSampleStyleSheet()
    return ParagraphStyle("label", parent=styles["Normal"], fontSize=10, spaceAfter=3, fontName="Helvetica")


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
        Paragraph("Flujo Comercial / Materiales", ParagraphStyle(
            "sub", parent=styles["Normal"], fontSize=9, textColor=GRAY_LABEL, spaceAfter=10,
        )),
        HRFlowable(width="100%", thickness=1.2, color=BRAND_BLUE, spaceAfter=10),
        Paragraph(titulo, ParagraphStyle(
            "titulo", parent=styles["Normal"], fontSize=13, fontName="Helvetica-Bold",
            textColor=NEAR_BLACK, spaceAfter=4,
        )),
        Paragraph(f"N.° {numero}  ·  {_fecha_larga(fecha)}", _label()),
        Spacer(1, 10),
    ]
    return elements


def _build_datos_generales(pares: list[tuple[str, str]]) -> Table:
    rows = [[Paragraph(f"<b>{k}:</b>", _label()), Paragraph(v or "-", _label())] for k, v in pares]
    t = Table(rows, colWidths=[4 * cm, 13 * cm])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
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
        Spacer(1, 14),
        img,
        HRFlowable(width=4.5 * cm, thickness=0.8, color=colors.HexColor("#888888")),
        Paragraph(label, ParagraphStyle("firma", parent=styles["Normal"], fontSize=8, textColor=GRAY_LABEL)),
    ]


def _build_aclaraciones_section(text: str | None = None) -> list:
    styles = getSampleStyleSheet()
    elements = [Spacer(1, 24), Paragraph("Observaciones:", ParagraphStyle(
        "obs", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold", textColor=GRAY_LABEL, spaceAfter=6,
    ))]
    if text:
        elements.append(Paragraph(text, _label()))
        elements.append(Spacer(1, 6))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    elements.append(Spacer(1, 14))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc")))
    return elements


def _items_table(items: list[dict]) -> Table:
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
    doc.build(elements)


def generate_orden_suministro(
    path: Path, numero: str, fecha: date, cliente_nombre: str, planta_nombre: str,
    items: list[dict], firma_path: str | None = None, notas: str | None = None,
) -> None:
    doc = _base_doc(path, f"Orden de Suministro {numero}")
    elements = _build_header("Formato de Orden de Suministro", numero, fecha)
    elements.append(_build_datos_generales([("Cliente", cliente_nombre), ("Planta despacho", planta_nombre)]))
    elements.append(Spacer(1, 14))
    elements.append(_items_table(items))
    elements += _build_firma_section(firma_path, "Autorizado por")
    elements += _build_aclaraciones_section(notas)
    doc.build(elements)


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
    elements.append(_items_table(items))
    elements.append(Spacer(1, 30))

    firma_cliente = Table([[
        HRFlowable(width=6 * cm, thickness=0.8, color=colors.HexColor("#888888")),
        HRFlowable(width=6 * cm, thickness=0.8, color=colors.HexColor("#888888")),
    ]], colWidths=[8.5 * cm, 8.5 * cm])
    elements.append(firma_cliente)
    styles = getSampleStyleSheet()
    label_row = Table([[
        Paragraph(f"Recibido por: {recibido_por or '_______________________'}", ParagraphStyle("f1", fontSize=8, textColor=GRAY_LABEL)),
        Paragraph("Entregado por (Planta)", ParagraphStyle("f2", fontSize=8, textColor=GRAY_LABEL)),
    ]], colWidths=[8.5 * cm, 8.5 * cm])
    elements.append(label_row)

    elements += _build_aclaraciones_section(notas)
    doc.build(elements)
