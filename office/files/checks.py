"""Checks for Word, PowerPoint and Excel files from the office-docs server, run before the link
reaches the model. Anything that can be repaired is repaired in the file; the rest comes back as
problems for the model to fix in the same turn.

Word refuses a file whose run, paragraph or table properties are out of schema order, and
PowerPoint one with a shape id at or above 2^31 (LibreOffice opens both), so those are repaired.
"""

import io
import re
import zipfile
from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

WORD_ORDER = {
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint "
    "noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect "
    "bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath",
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers "
    "pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE "
    "autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents "
    "suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr "
    "sectPr pPrChange",
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc "
    "tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription",
}
WORD_ORDER = {name: {tag: i for i, tag in enumerate(order.split())} for name, order in WORD_ORDER.items()}
MAX_SHAPE_ID = 2**31 - 1
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
CELL_REF = re.compile(r"(?<![A-Za-z!$'\"])\$?([A-Z]{1,3})\$?([0-9]{1,7})(?![0-9(])")
RANGE_REF = re.compile(
    r"(?<![A-Za-z!$'\"])\$?([A-Z]{1,3})\$?([0-9]{1,7}):\$?([A-Z]{1,3})\$?([0-9]{1,7})(?![0-9(])"
)


def _column(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def _letters(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _empty_references(formula: str, filled: set) -> list[str]:
    """Cells a formula reads that hold nothing: single references that are empty, and ranges
    in which every cell is empty (a range may legitimately include some blanks)."""
    empty = []
    for c1, r1, c2, r2 in RANGE_REF.findall(formula):
        cols = range(min(_column(c1), _column(c2)), max(_column(c1), _column(c2)) + 1)
        rows = range(min(int(r1), int(r2)), max(int(r1), int(r2)) + 1)
        if len(cols) * len(rows) <= 100000 and not any(f"{_letters(c)}{r}" in filled for c in cols for r in rows):
            empty.append(f"{c1}{r1}:{c2}{r2}")
    singles = RANGE_REF.sub("", formula)
    empty += [f"{c}{r}" for c, r in CELL_REF.findall(singles) if f"{c}{r}" not in filled]
    return empty


def _rewrite(data: bytes, edits: dict) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            body = src.read(item.filename)
            dst.writestr(item, edits.get(item.filename, body))
    return out.getvalue()


def _sort_children(element, order: dict) -> bool:
    known = [c for c in element if isinstance(c.tag, str) and c.tag.startswith(W) and c.tag[len(W):] in order]
    ranks = [order[c.tag[len(W):]] for c in known]
    if ranks == sorted(ranks):
        return False
    for child in known:
        element.remove(child)
    others = list(element)
    for child in others:
        element.remove(child)
    for child in sorted(known, key=lambda c: order[c.tag[len(W):]]) + others:
        element.append(child)
    return True


def check_docx(data: bytes, markdown_content: str = ""):
    """Returns (data, notes, problems)."""
    notes, problems, edits = [], [], {}
    archive = zipfile.ZipFile(io.BytesIO(data))
    parts = [n for n in archive.namelist() if re.match(r"word/(document|styles|header\d*|footer\d*)\.xml$", n)]
    fixed = 0
    for name in parts:
        # lxml keeps every namespace declaration; Word needs those named in mc:Ignorable.
        root = etree.fromstring(archive.read(name))
        changed = sum(
            _sort_children(el, order)
            for tag, order in WORD_ORDER.items()
            for el in root.iter(W + tag)
        )
        if changed:
            fixed += changed
            edits[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    if fixed:
        notes.append(f"repaired {fixed} formatting blocks Word would have rejected")

    document = archive.read("word/document.xml").decode("utf-8", "replace")
    text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", document)).strip()
    if len(text) < 5:
        problems.append("the document has no text; pass the full content in markdown_content")
    wanted = len(MARKDOWN_IMAGE.findall(markdown_content or ""))
    placed = len([n for n in archive.namelist() if n.startswith("word/media/")])
    if wanted > placed:
        problems.append(
            f"{wanted - placed} of {wanted} images could not be placed; use links returned by "
            "create_chart / create_diagram exactly, or public https image links"
        )
    return (_rewrite(data, edits) if edits else data), notes, problems


def check_pptx(data: bytes):
    notes, problems, edits = [], [], {}
    archive = zipfile.ZipFile(io.BytesIO(data))
    slides = sorted(n for n in archive.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
    for name in [n for n in archive.namelist() if re.match(r"ppt/(slides|slideLayouts|slideMasters)/[^/]+\.xml$", n)]:
        xml = archive.read(name).decode("utf-8")
        ids = [int(i) for i in re.findall(r'<p:cNvPr id="(\d+)"', xml)]
        if any(i > MAX_SHAPE_ID for i in ids):
            next_id = max([i for i in ids if i <= MAX_SHAPE_ID], default=1) + 1

            def renumber(match):
                nonlocal next_id
                if int(match.group(1)) <= MAX_SHAPE_ID:
                    return match.group(0)
                next_id += 1
                return f'<p:cNvPr id="{next_id - 1}"'

            edits[name] = re.sub(r'<p:cNvPr id="(\d+)"', renumber, xml).encode("utf-8")
    if edits:
        notes.append("repaired shape ids PowerPoint would have rejected")
    empty = [
        str(i + 1)
        for i, name in enumerate(slides)
        if not re.search(r"<a:t>[^<]*\S", archive.read(name).decode("utf-8")) and b"<p:pic" not in archive.read(name)
    ]
    if empty:
        problems.append(f"slide {', '.join(empty)} is empty")
    return (_rewrite(data, edits) if edits else data), notes, problems


def check_xlsx(data: bytes):
    """Flags formulas that point at empty cells or broken references (formulas are not
    calculated here, so wrong-row references are the common mistake to catch)."""
    notes, problems = [], []
    archive = zipfile.ZipFile(io.BytesIO(data))
    for name in sorted(n for n in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
        root = etree.fromstring(archive.read(name))
        filled, formulas = set(), []
        for cell in root.iter(S + "c"):
            ref = cell.get("r")
            formula = cell.find(S + "f")
            if formula is not None and formula.text:
                formulas.append((ref, formula.text))
                filled.add(ref)
            elif cell.find(S + "v") is not None or cell.find(S + "is") is not None:
                filled.add(ref)
        sheet = name.rsplit("/", 1)[1].removesuffix(".xml")
        bad = []
        for ref, formula in formulas:
            if "#REF!" in formula:
                bad.append(f"{ref} ={formula} (broken reference)")
                continue
            local = re.sub(r"(?:'[^']+'|[A-Za-z0-9_]+)![$A-Z0-9:]+", "", formula)
            empty = _empty_references(local, filled)
            if empty:
                bad.append(f"{ref} ={formula} (refers to empty {', '.join(empty[:3])})")
        if bad:
            problems.append(
                f"{sheet}: formulas that look wrong: {'; '.join(bad[:5])}. Use the B[0] / T1.B[0] "
                "reference forms from the tool description, not absolute row numbers"
            )
    return data, notes, problems


CHECKS = {"docx": check_docx, "pptx": check_pptx, "xlsx": check_xlsx}
