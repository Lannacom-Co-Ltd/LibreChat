"""Markdown to an A4 PDF in Sarabun (WeasyPrint), checked before it is saved.

Fixed automatically: a first heading that repeats the title, tables too wide for a portrait
page (switched to landscape), long words and links that would run off the page (wrapped by
CSS). Reported for the model to fix: images that are not files this server created. Returns a
PNG of the first page so the model, and the user in the chat, can see the result.

Markdown is parsed as CommonMark + GFM tables (markdown-it), like the chat itself: models nest
lists with 2 spaces and put tables and lists right under a paragraph, which Python-Markdown
flattens into plain text. Raw HTML in the Markdown is not rendered. PDFium is not thread-safe,
so rendering is serialised.
"""

import io
import re
import threading
from html import escape

import pypdfium2
from markdown_it import MarkdownIt
from weasyprint import HTML, default_url_fetcher

import storage

CSS = """
@page {
  size: A4 %(orientation)s;
  margin: 2.5cm 2cm 2cm 3cm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: "Sarabun", sans-serif; font-size: 9pt; color: #666;
  }
}
body { font-family: "Sarabun", "Noto Sans Thai", sans-serif; font-size: 12pt; line-height: 1.5; color: #1a1a1a; }
h1, h2, h3, h4 { color: #145e6e; line-height: 1.3; margin: 1.2em 0 0.5em; }
h1 { font-size: 16pt; border-bottom: 2px solid #145e6e; padding-bottom: 0.2em; }
h2 { font-size: 14pt; }
h3 { font-size: 13pt; }
p, li, td, th, blockquote { overflow-wrap: anywhere; }
table { border-collapse: collapse; width: 100%%; margin: 0.8em 0; font-size: 10pt; }
th, td { border: 1px solid #b8c4c8; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #e6f0f2; }
tr { page-break-inside: avoid; }
code { font-family: "Noto Sans Mono", monospace; font-size: 9.5pt; background: #f2f2f2; padding: 0 3px; }
pre { background: #f2f2f2; padding: 8px 10px; white-space: pre-wrap; overflow-wrap: anywhere; }
pre code { padding: 0; }
blockquote { border-left: 3px solid #145e6e; margin: 0.8em 0; padding: 0.2em 1em; color: #444; }
hr { border: 0; border-top: 1px solid #ccc; }
img { max-width: 100%%; }
"""

LANDSCAPE_FROM_COLUMNS = 7
PREVIEW_WIDTH = 700
MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
RENDER_LOCK = threading.Lock()


def _plain(text: str) -> str:
    return re.sub(r"[\W_]+", "", text).lower()


def drop_repeated_title(markdown_content: str, title: str | None) -> tuple[str, bool]:
    """Removes a leading # or ## heading that says the same as title."""
    if not title:
        return markdown_content, False
    lines = markdown_content.lstrip("\n").split("\n")
    match = re.match(r"^#{1,2}\s+(.*?)\s*#*\s*$", lines[0]) if lines else None
    if match and _plain(match.group(1)) == _plain(title):
        return "\n".join(lines[1:]).lstrip("\n"), True
    return markdown_content, False


def widest_table(markdown_content: str) -> int:
    widths = [
        line.strip().strip("|").count("|") + 1
        for line in markdown_content.split("\n")
        if line.strip().startswith("|")
    ]
    return max(widths, default=0)


def preview_png(pdf: bytes) -> tuple[bytes, int]:
    doc = pypdfium2.PdfDocument(pdf)
    try:
        page = doc[0]
        scale = PREVIEW_WIDTH / page.get_width()
        image = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        return buf.getvalue(), len(doc)
    finally:
        doc.close()


def render_pdf(markdown_content: str, title: str | None, landscape: bool):
    """Returns (pdf bytes, preview png, page count, notes, problems)."""
    if not markdown_content or len(markdown_content.strip()) < 10:
        raise ValueError("markdown_content is empty; pass the whole document text in markdown_content")
    notes, problems, missing = [], [], []

    markdown_content, dropped = drop_repeated_title(markdown_content, title)
    if dropped:
        notes.append("the first heading repeated the title and was removed (the title is already the top heading)")
    columns = widest_table(markdown_content)
    if columns >= LANDSCAPE_FROM_COLUMNS and not landscape:
        landscape = True
        notes.append(f"a table has {columns} columns, so the pages are landscape")

    def fetcher(url, *args, **kwargs):
        if url.startswith("data:"):
            return default_url_fetcher(url, *args, **kwargs)
        key = storage.own_key(url)
        if key:
            try:
                data, content_type = storage.read(key)
                return {"string": data, "mime_type": content_type}
            except Exception:
                pass
        missing.append(url)
        raise ValueError(f"not loaded: {url}")

    body = MARKDOWN.render(markdown_content)
    heading = f"<h1>{escape(title)}</h1>" if title else ""
    page = (
        f'<html lang="th"><head><meta charset="utf-8"><title>{escape(title or "")}</title>'
        f"<style>{CSS % {'orientation': 'landscape' if landscape else 'portrait'}}</style>"
        f"</head><body>{heading}{body}</body></html>"
    )
    with RENDER_LOCK:
        pdf = HTML(string=page, url_fetcher=fetcher).write_pdf()
        png, pages = preview_png(pdf)
    if missing:
        problems.append(
            "these images were left out because they are not files created by create_chart or "
            f"create_diagram (or have expired): {', '.join(missing[:5])}"
        )
    return pdf, png, pages, notes, problems
