"""Overlay for the office-docs container, loaded by Python at start-up (mounted as
site-packages/sitecustomize.py; the image itself is unchanged).

1. Thai formatting for python-docx. Word draws Thai with the complex-script run properties:
   bold is w:bCs, italic w:iCs and size w:szCs. python-docx sets only w:b, w:i and w:sz, so
   **bold** and sizes written by the server would not show on Thai text. Each setter here also
   writes its complex-script twin, placed right after it as the schema orders them.

2. Excel in the CMUBS look: Sarabun instead of Calibri, teal instead of the server's blues.

3. Images from this deployment's own bucket (charts from create_chart). Their links are
   public presigned URLs, which the server cannot fetch through Cloudflare and must not fetch
   as private addresses. A link into MINIO_ENDPOINT/MINIO_BUCKET is read from the store on
   the shared network instead (OFFICE_STORE_URL), with the Host its signature was made for.
   Every other image keeps the server's own download and SSRF rules.
"""

import os
import sys
import builtins

try:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.text.font import Font
except ImportError:
    Font = None


def _twin(prop, tag, twin):
    original = getattr(Font, prop)

    def setter(self, value):
        original.fset(self, value)
        rpr = self._element.rPr
        if rpr is None:
            return
        for old in rpr.findall(qn(twin)):
            rpr.remove(old)
        base = rpr.find(qn(tag))
        if base is None:
            return
        el = OxmlElement(twin)
        val = base.get(qn("w:val"))
        if val is not None:
            el.set(qn("w:val"), val)
        base.addnext(el)

    setattr(Font, prop, property(original.fget, setter, original.fdel, original.__doc__))


if Font is not None:
    _twin("bold", "w:b", "w:bCs")
    _twin("italic", "w:i", "w:iCs")
    _twin("size", "w:sz", "w:szCs")


try:
    import openpyxl.workbook.workbook as _xl_workbook
    from openpyxl.styles import fills as _xl_fills
    from openpyxl.styles import fonts as _xl_fonts
    from openpyxl.styles.colors import Color as _XlColor
except ImportError:
    _xl_fonts = None

# Excel: the server hard-codes Calibri and an Office blue for headers. Fonts without a name
# become Sarabun, and its blues become the CMUBS teal family.
_XLSX_COLORS = {"366092": "145E6E", "E7F3FF": "E6F0F2", "2F5597": "145E6E", "4472C4": "1E7C8F"}


def _xl_color(value):
    if isinstance(value, str) and value.upper().lstrip("#")[-6:] in _XLSX_COLORS:
        return _XLSX_COLORS[value.upper().lstrip("#")[-6:]]
    return value


if _xl_fonts is not None:
    _font_init = _xl_fonts.Font.__init__
    _fill_init = _xl_fills.PatternFill.__init__

    def _xl_font_init(self, name=None, *args, **kwargs):
        if "color" in kwargs:
            kwargs["color"] = _xl_color(kwargs["color"])
        _font_init(self, name or "Sarabun", *args, **kwargs)

    def _xl_fill_init(self, *args, **kwargs):
        for key in ("fgColor", "bgColor", "start_color", "end_color"):
            if key in kwargs:
                kwargs[key] = _xl_color(kwargs[key])
        _fill_init(self, *args, **kwargs)

    _xl_fonts.Font.__init__ = _xl_font_init
    _xl_fills.PatternFill.__init__ = _xl_fill_init
    # The workbook's Normal style; a "minor" scheme font would follow the theme's Calibri.
    _default_font = _xl_fonts.Font(name="Sarabun", sz=11, family=2, b=False, i=False, color=_XlColor(theme=1))
    _xl_fonts.DEFAULT_FONT = _default_font
    _xl_workbook.DEFAULT_FONT = _default_font


_PUBLIC = os.environ.get("MINIO_ENDPOINT", "").rstrip("/")
_BUCKET = os.environ.get("MINIO_BUCKET", "")
_STORE = os.environ.get("OFFICE_STORE_URL", "http://localhost:9000").rstrip("/")
_PREFIX = f"{_PUBLIC}/{_BUCKET}/" if _PUBLIC and _BUCKET else None


def _patch_image_utils(module):
    import io
    from urllib.parse import urlsplit

    import requests

    original_download = module.download_image

    def download_image(url):
        if not (_PREFIX and isinstance(url, str) and url.startswith(_PREFIX)):
            return module.load_image(url) if module.is_data_uri(url) else original_download(url)
        parts = urlsplit(url)
        internal = f"{_STORE}{parts.path}" + (f"?{parts.query}" if parts.query else "")
        response = requests.get(internal, headers={"Host": parts.netloc}, timeout=15)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            raise module.ImageValidationError(f"Not an image: {content_type}")
        return io.BytesIO(response.content), module.get_image_extension(content_type, parts.path)

    module.download_image = download_image
    module._cmubs_patched = True


_import = builtins.__import__
# image_utils sits in sys.modules while it is still importing; patch only once it is complete.
_NEEDED = ("download_image", "load_image", "is_data_uri", "get_image_extension", "ImageValidationError")


def _import_hook(name, *args, **kwargs):
    module = _import(name, *args, **kwargs)
    loaded = sys.modules.get("image_utils")
    ready = loaded is not None and all(hasattr(loaded, n) for n in _NEEDED)
    if ready and not getattr(loaded, "_cmubs_patched", False):
        loaded._cmubs_patched = True
        try:
            _patch_image_utils(loaded)
        except Exception as err:  # never break the server over the overlay
            print(f"sitecustomize: image patch skipped: {err}", file=sys.stderr)
    return module


builtins.__import__ = _import_hook
