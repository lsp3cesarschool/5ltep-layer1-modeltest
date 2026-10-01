"""Synthetic PDF dictionaries: one known field list, three layouts harder than a plain table.

  prose            one paragraph per field ("O campo X armazena ... Seu tipo é Y, com tamanho Z.")
  list             one bullet per field ("• X — tipo Y; tamanho Z. Descrição...")
  table-reordered  a table whose columns are in another order (description first, name third),
                   with long cells and a header repeated on every page

Every PDF starts with a page of metadata in prose, as real dictionaries do. The output is
byte-for-byte reproducible (reportlab invariant mode), so the gold set's hash only changes when
its content does.
"""

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle

LAYOUTS = ("prose", "list", "table-reordered")
STYLES = getSampleStyleSheet()


def _esc(text) -> str:
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _intro(title: str, source: str) -> list:
    return [
        Paragraph("Dicionário de Dados", STYLES["Title"]),
        Paragraph(_esc(title), STYLES["Heading2"]),
        Paragraph("Este documento descreve os campos do conjunto de dados publicado no portal de dados abertos. "
                  "A frequência de atualização, a cobertura temporal e o responsável pela publicação constam da "
                  "página do conjunto. Os campos estão listados na ordem em que aparecem no arquivo.", STYLES["BodyText"]),
        Paragraph(f"Fonte do esquema: {_esc(source)}.", STYLES["BodyText"]),
        Spacer(1, 0.5 * cm),
    ]


def _size(f: dict) -> str:
    return str(f.get("declaredSize") or "")


def render(fields: list[dict], layout: str, title: str, source: str) -> bytes:
    """fields: [{"name", "declaredType", "declaredSize", "description"}]"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Dicionário de Dados", author="5ltep-layer1-modeltest",
                            invariant=1, leftMargin=2 * cm, rightMargin=2 * cm)
    story = _intro(title, source)
    body = STYLES["BodyText"]
    if layout == "prose":
        for f in fields:
            desc = _esc(f.get("description") or "Sem descrição.").rstrip(".")
            typ = _esc(f.get("declaredType") or "não informado")
            size = f", com tamanho {_size(f)}" if _size(f) else ""
            story.append(Paragraph(f"O campo <b>{_esc(f['name'])}</b> armazena: {desc}. Seu tipo é {typ}{size}.", body))
            story.append(Spacer(1, 0.2 * cm))
    elif layout == "list":
        for f in fields:
            typ = _esc(f.get("declaredType") or "não informado")
            size = f"; tamanho {_size(f)}" if _size(f) else ""
            story.append(Paragraph(f"• {_esc(f['name'])} — tipo {typ}{size}. {_esc(f.get('description'))}", body))
    elif layout == "table-reordered":
        story.append(PageBreak())
        small = STYLES["BodyText"].clone("small", fontSize=8, leading=10)
        rows = [[Paragraph(h, small) for h in ("Descrição", "Tipo", "Campo", "Tamanho")]]
        for f in fields:
            rows.append([Paragraph(_esc(f.get("description")), small), Paragraph(_esc(f.get("declaredType")), small),
                         Paragraph(_esc(f["name"]), small), Paragraph(_size(f), small)])
        table = LongTable(rows, colWidths=[8.5 * cm, 3 * cm, 4 * cm, 1.5 * cm], repeatRows=1)
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, "#888888"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(table)
    else:
        raise ValueError(f"unknown layout {layout!r}")
    doc.build(story)
    return buf.getvalue()
