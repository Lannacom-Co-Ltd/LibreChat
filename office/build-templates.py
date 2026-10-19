"""Builds the CMUBS Word and PowerPoint templates for the office-docs MCP server.

Starts from the server's own default templates (so every style and layout it relies on is
present) and changes only the look: Sarabun for Thai and Latin text, th-TH proofing, A4 with
Thai official-letter margins, the CMUBS deep teal, the logo on every slide, and Sarabun
embedded in the Word files so they look the same on machines without the font.

Run from the repository root (needs Docker; the image already has python-docx/python-pptx):

  docker run --rm -v "$PWD/office:/work" -v "$PWD/branding/icons:/icons:ro" \
    --entrypoint python georgx22/mcp-office-docs@sha256:9c26e1944104ed01d870abae94665e4e5398ee74d50d33c33ba4622db534b38a \
    /work/build-templates.py

Writes office/templates/*.docx|pptx (custom_email_template.html there is hand-written).
Edit this script, not the generated files.
"""

import copy
import io
import re
import uuid
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from pptx import Presentation
from pptx.dml.color import RGBColor as SlideColor
from pptx.oxml.ns import qn as pqn
from pptx.oxml.xmlchemy import OxmlElement as SlideElement
from pptx.shapes.shapetree import SlideShapes
from pptx.util import Emu, Inches

DEFAULTS = Path("/app/default_templates")
WORK = Path("/work")
OUT = WORK / "templates"
FONTS = WORK / "fonts"
LOGO = Path("/icons/logo-light.png")

FONT = "Sarabun"
TEAL = "145E6E"
LANG = "th-TH"

BODY_PT = 12
HEADING_PT = {1: 16, 2: 14, 3: 13, 4: 12, 5: 12, 6: 12}
TITLE_PT = 20

# Office theme: accents follow the CMUBS logo (teal and purple) around the deep teal.
THEME_COLORS = {
    "dk2": "0B3540",
    "lt2": "EEF3F4",
    "accent1": TEAL,
    "accent2": "8A4FA3",
    "accent3": "1E9BB0",
    "accent4": "5C3B8C",
    "accent5": "6BB7C4",
    "accent6": "B58BC9",
    "hlink": TEAL,
    "folHlink": "5C3B8C",
}


# --------------------------------------------------------------------------- shared XML


def retheme(xml: str) -> str:
    """Theme fonts to Sarabun (Latin and complex script) and the CMUBS colour scheme."""
    xml = re.sub(r'<a:latin typeface="[^"]*"', f'<a:latin typeface="{FONT}"', xml)
    xml = re.sub(r'<a:cs typeface="[^"]*"', f'<a:cs typeface="{FONT}"', xml)
    for name, hex_ in THEME_COLORS.items():
        xml = re.sub(
            rf"<a:{name}>.*?</a:{name}>",
            f'<a:{name}><a:srgbClr val="{hex_}"/></a:{name}>',
            xml,
            flags=re.S,
        )
    return xml


def rewrite_zip(data: bytes, edits: dict, extra: dict | None = None) -> bytes:
    """Copies a zip, passing named members through edit functions and adding extra members."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            body = src.read(item.filename)
            if item.filename in edits:
                body = edits[item.filename](body.decode("utf-8")).encode("utf-8")
            dst.writestr(item, body)
        for name, body in (extra or {}).items():
            dst.writestr(name, body)
    return out.getvalue()


# --------------------------------------------------------------------------- Word

# Child order of w:rPr in the WordprocessingML schema; Word refuses files that break it.
RPR_ORDER = (
    "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint "
    "noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u "
    "effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath"
).split()


def set_run_props(rpr, size_pt=None, bold=None, color=None):
    """Sets size/bold on both the Latin and complex-script properties: Word draws Thai with
    the *Cs variants (szCs, bCs), so a style that only sets sz/b leaves Thai unchanged."""
    def put(tag, **attrs):
        for old in rpr.findall(qn(tag)):
            rpr.remove(old)
        el = OxmlElement(tag)
        for k, v in attrs.items():
            el.set(qn(k), v)
        rank = RPR_ORDER.index(tag[2:])
        later = [c for c in rpr if c.tag.split("}")[1] in RPR_ORDER and RPR_ORDER.index(c.tag.split("}")[1]) > rank]
        if later:
            later[0].addprevious(el)
        else:
            rpr.append(el)

    put("w:rFonts", **{"w:ascii": FONT, "w:hAnsi": FONT, "w:eastAsia": FONT, "w:cs": FONT})
    if bold is not None:
        put("w:b", **({} if bold else {"w:val": "0"}))
        put("w:bCs", **({} if bold else {"w:val": "0"}))
    if color:
        put("w:color", **{"w:val": color})
    if size_pt:
        put("w:sz", **{"w:val": str(size_pt * 2)})
        put("w:szCs", **{"w:val": str(size_pt * 2)})


def style_docx(doc):
    """A4, official-letter margins, Sarabun everywhere, teal headings, th-TH proofing."""
    for section in doc.sections:
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin, section.bottom_margin = Cm(2.5), Cm(2)
        section.left_margin, section.right_margin = Cm(3), Cm(2)

    styles = doc.styles.element
    rpr_default = styles.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
    set_run_props(rpr_default, size_pt=BODY_PT)
    for old in rpr_default.findall(qn("w:lang")):
        rpr_default.remove(old)
    lang = OxmlElement("w:lang")
    for attr in ("w:val", "w:eastAsia", "w:bidi"):
        lang.set(qn(attr), LANG)
    rpr_default.append(lang)

    for style in doc.styles:
        if style.type != 1:
            continue
        rpr = style.element.get_or_add_rPr()
        match = re.fullmatch(r"Heading (\d)", style.name)
        if match:
            level = int(match.group(1))
            set_run_props(rpr, size_pt=HEADING_PT.get(level, BODY_PT), bold=True, color=TEAL)
        elif style.name == "Title":
            set_run_props(rpr, size_pt=TITLE_PT, bold=True, color=TEAL)
        elif style.name == "Subtitle":
            set_run_props(rpr, size_pt=14, color="555555")
        else:
            fonts = rpr.find(qn("w:rFonts"))
            if fonts is not None:
                rpr.remove(fonts)
                set_run_props(rpr)


def add_page_number_footer(doc):
    footer = doc.sections[0].footer
    para = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)
    run.font.size = Pt(10)


def embed_fonts(docx: bytes) -> bytes:
    """Embeds Sarabun (regular, bold, italic, bold italic) as obfuscated fonts (ECMA-376
    17.8.1), so Word and LibreOffice show it on machines that do not have it installed."""
    faces = {
        "embedRegular": "Sarabun-Regular.ttf",
        "embedBold": "Sarabun-Bold.ttf",
        "embedItalic": "Sarabun-Italic.ttf",
        "embedBoldItalic": "Sarabun-BoldItalic.ttf",
    }
    extra, rels, embeds = {}, [], []
    for n, (tag, file) in enumerate(faces.items(), start=1):
        guid = str(uuid.uuid4()).upper()
        key = bytes.fromhex(guid.replace("-", ""))[::-1]
        data = bytearray((FONTS / file).read_bytes())
        for i in range(32):
            data[i] ^= key[i % 16]
        extra[f"word/fonts/sarabun{n}.odttf"] = bytes(data)
        rels.append(
            f'<Relationship Id="rIdSarabun{n}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" '
            f'Target="fonts/sarabun{n}.odttf"/>'
        )
        embeds.append(f'<w:{tag} r:id="rIdSarabun{n}" w:fontKey="{{{guid}}}"/>')

    font_entry = (
        f'<w:font w:name="{FONT}"><w:charset w:val="00"/><w:family w:val="auto"/>'
        f'<w:pitch w:val="variable"/>{"".join(embeds)}</w:font>'
    )

    def font_table(xml):
        xml = re.sub(rf'<w:font w:name="{FONT}">.*?</w:font>', "", xml, flags=re.S)
        if "xmlns:r=" not in xml.split(">", 2)[1]:
            xml = xml.replace(
                "<w:fonts ",
                '<w:fonts xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ',
                1,
            )
        return xml.replace("</w:fonts>", font_entry + "</w:fonts>")

    def settings(xml):
        if "<w:embedTrueTypeFonts" in xml:
            return xml
        return re.sub(r"(<w:settings[^>]*>(?:\s*<w:(?:writeProtection|view|zoom|removePersonalInformation|removeDateAndTime)[^>]*?/>)*)",
                      r"\1<w:embedTrueTypeFonts/>", xml, count=1)

    def content_types(xml):
        if 'Extension="odttf"' in xml:
            return xml
        return xml.replace(
            "<Types ",
            "<Types ",
            1,
        ).replace(
            "<Default ",
            '<Default Extension="odttf" '
            'ContentType="application/vnd.openxmlformats-officedocument.obfuscatedFont"/><Default ',
            1,
        )

    names = zipfile.ZipFile(io.BytesIO(docx)).namelist()
    rels_name = "word/_rels/fontTable.xml.rels"
    edits = {
        "word/fontTable.xml": font_table,
        "word/settings.xml": settings,
        "[Content_Types].xml": content_types,
    }
    if rels_name in names:
        edits[rels_name] = lambda xml: xml.replace("</Relationships>", "".join(rels) + "</Relationships>")
    else:
        extra[rels_name] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels)
            + "</Relationships>"
        )
    return rewrite_zip(docx, edits, extra)


def save_docx(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return rewrite_zip(buf.getvalue(), {"word/theme/theme1.xml": retheme})


def no_borders(table):
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tbl_pr = table._tbl.tblPr
    later = [tbl_pr.find(qn(t)) for t in ("w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook")]
    later = [el for el in later if el is not None]
    if later:
        later[0].addprevious(borders)
    else:
        tbl_pr.append(borders)


def labelled(doc, parts, tab_cm=None, space_after=4):
    """One memo line of bold labels and {{placeholders}}, e.g. [("ที่", True), ("{{doc_number}}", False)]."""
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(space_after)
    if tab_cm:
        para.paragraph_format.tab_stops.add_tab_stop(Cm(tab_cm), WD_TAB_ALIGNMENT.LEFT)
    for text, bold in parts:
        run = para.add_run(text)
        rpr = run._r.get_or_add_rPr()
        set_run_props(rpr, size_pt=14 if bold else BODY_PT, bold=bold)
    return para


def build_memo(base: bytes) -> bytes:
    """บันทึกข้อความ in the layout of the Thai official internal memo, CMUBS logo in place
    of the Garuda."""
    doc = Document(io.BytesIO(base))
    body = doc.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)

    head = doc.add_table(rows=1, cols=3)
    head.alignment = WD_TABLE_ALIGNMENT.CENTER
    no_borders(head)
    widths = (Cm(3.5), Cm(9), Cm(3.5))
    for cell, width in zip(head.rows[0].cells, widths):
        cell.width = width
    head.cell(0, 0).paragraphs[0].add_run().add_picture(str(LOGO), height=Cm(1.6))
    title = head.cell(0, 1).paragraphs[0]
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_props(title.add_run("บันทึกข้อความ")._r.get_or_add_rPr(), size_pt=22, bold=True)

    labelled(doc, [("ส่วนงาน  ", True), ("{{department}}", False)])
    labelled(doc, [("ที่  ", True), ("{{doc_number}}", False), ("\t", False), ("วันที่  ", True), ("{{date}}", False)], tab_cm=8)
    rule = labelled(doc, [("เรื่อง  ", True), ("{{subject}}", False)], space_after=10)
    border = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "6"), ("w:color", TEAL)):
        bottom.set(qn(k), v)
    border.append(bottom)
    p_pr = rule._p.get_or_add_pPr()
    later = [p_pr.find(qn(t)) for t in ("w:shd", "w:tabs", "w:spacing", "w:ind", "w:jc", "w:rPr")]
    later = [el for el in later if el is not None]
    if later:
        later[0].addprevious(border)
    else:
        p_pr.append(border)
    labelled(doc, [("เรียน  ", False), ("{{to}}", False)], space_after=8)

    body_para = doc.add_paragraph("{{body}}")
    body_para.paragraph_format.first_line_indent = Cm(2.5)
    body_para.alignment = WD_ALIGN_PARAGRAPH.THAI_JUSTIFY

    doc.add_paragraph()
    for text in ("({{signer_name}})", "{{signer_position}}"):
        para = doc.add_paragraph(text)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.left_indent = Cm(7)
        para.paragraph_format.space_after = Pt(0)
    doc.paragraphs[-2].paragraph_format.space_before = Pt(36)

    return save_docx(doc)


# --------------------------------------------------------------------------- PowerPoint


def brand_pptx(path: Path) -> bytes:
    prs = Presentation(str(path))
    master = prs.slide_masters[0]
    width, height = prs.slide_width, prs.slide_height
    margin = Emu(int(width * 0.03))
    logo_h = Emu(int(height * 0.085))

    # MasterShapes has no add_picture/add_shape; the slide shape tree API works on the
    # master's own tree and part.
    shapes = SlideShapes(master.shapes._spTree, master)
    pic = shapes.add_picture(str(LOGO), 0, Emu(int(height * 0.035)), height=logo_h)
    pic.left = width - pic.width - margin
    pic.name = "CMUBS logo"

    for shape in master.placeholders:
        if shape.placeholder_format.type == 1 and shape.left + shape.width > pic.left - margin:
            shape.width = pic.left - margin - shape.left

    bar = shapes.add_shape(1, 0, height - Emu(int(height * 0.012)), width, Emu(int(height * 0.012)))
    bar.fill.solid()
    bar.fill.fore_color.rgb = SlideColor.from_string(TEAL)
    bar.line.fill.background()
    bar.name = "CMUBS bar"

    # python-pptx numbers new master shapes after the layout ids (2147483648 and up), which
    # PowerPoint refuses to open; give them the next ids after the master's own shapes.
    ids = [int(el.get("id")) for el in master.element.iter(pqn("p:cNvPr"))]
    next_id = max(i for i in ids if i < 2**31 - 2) + 1
    for shape in (pic, bar):
        shape._element.find(".//" + pqn("p:cNvPr")).set("id", str(next_id))
        next_id += 1

    title_rpr = master.element.find(".//" + pqn("p:titleStyle")).find(".//" + pqn("a:defRPr"))
    for fill in title_rpr.findall(pqn("a:solidFill")):
        title_rpr.remove(fill)
    fill = SlideElement("a:solidFill")
    clr = SlideElement("a:schemeClr")
    clr.set("val", "accent1")
    fill.append(clr)
    title_rpr.insert(0, fill)
    title_rpr.set("b", "1")

    buf = io.BytesIO()
    prs.save(buf)
    names = zipfile.ZipFile(io.BytesIO(buf.getvalue())).namelist()
    return rewrite_zip(buf.getvalue(), {n: retheme for n in names if re.match(r"ppt/theme/theme\d+\.xml$", n)})


# --------------------------------------------------------------------------- main


def main():
    OUT.mkdir(exist_ok=True)

    doc = Document(str(DEFAULTS / "default_docx_template.docx"))
    style_docx(doc)
    add_page_number_footer(doc)
    base = save_docx(doc)
    (OUT / "custom_docx_template.docx").write_bytes(embed_fonts(base))
    (OUT / "cmubs_memo.docx").write_bytes(embed_fonts(build_memo(base)))

    for aspect in ("16_9", "4_3"):
        (OUT / f"custom_pptx_template_{aspect}.pptx").write_bytes(
            brand_pptx(DEFAULTS / f"default_pptx_template_{aspect}.pptx")
        )

    for f in sorted(OUT.iterdir()):
        print(f"{f.name}: {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
