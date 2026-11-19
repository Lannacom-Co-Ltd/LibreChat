"""The single file-creation MCP server LibreChat talks to in AI Hub (office-files).

Own tools: create_pdf_from_markdown (pdf.py), create_text_file, create_chart (charts.py),
create_diagram (diagrams.py), create_image (images.py), and for administrators usage_report and
manage_credits (admin.py). The office-docs server's Word, Excel, PowerPoint, email and memo
tools are mounted through a proxy (OFFICE_DOCS_URL), so the chat menu has one entry. Each kind
of file can be switched off in office.env (features.py).

Every file passes a quality gate before its link reaches the model:
- files are checked and repaired where possible (checks.py, and inside each tool);
- what cannot be repaired comes back as problems, with an instruction to fix and call again
  in the same turn instead of asking the user;
- every link is a short public link (storage.py), including office-docs files, which are moved
  out of their long presigned links;
- with PREVIEW_IMAGES=true, charts, diagrams and the first page of a PDF also come back as an
  image for the model to review. Off by default: LibreChat passes tool images to every model,
  and a text-only model (DeepSeek, for one) makes the provider reject the whole request.
"""

import asyncio
import base64
import csv
import hmac
import io
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Literal

import httpx
import uvicorn
from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from fastmcp.server import create_proxy
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware as ToolMiddleware
from fastmcp.tools.tool import ToolResult
from mcp.types import ImageContent, TextContent
from PIL import Image
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

import admin
import features
import images
import logs
import names
import schemas
import storage
import usage
from checks import CHECKS
from charts import Series, draw_chart
from diagrams import DiagramEdge, DiagramNode, TimelineEvent, draw_diagram
from pdf import render_pdf

API_KEY = os.environ.get("API_KEY", "")
PORT = int(os.environ.get("PORT", "8959"))
OFFICE_DOCS_URL = os.environ.get("OFFICE_DOCS_URL", "")
PREVIEW_MAX = 800
PREVIEW_IMAGES = os.environ.get("PREVIEW_IMAGES", "false").lower() == "true"

mcp = FastMCP("office-files", instructions=features.instructions())

if OFFICE_DOCS_URL:
    mcp.mount(
        create_proxy(
            StreamableHttpTransport(OFFICE_DOCS_URL, headers={"Authorization": f"Bearer {API_KEY}"})
        )
    )


def preview(png: bytes) -> ImageContent:
    image = Image.open(io.BytesIO(png))
    image.thumbnail((PREVIEW_MAX, PREVIEW_MAX))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG", optimize=True)
    return ImageContent(type="image", data=base64.b64encode(buf.getvalue()).decode(), mimeType="image/png")


def report(link: str, notes=(), problems=(), image: bytes | None = None, embeddable=False, extra="") -> ToolResult:
    """The message the model gets for every created file."""
    lines = []
    if problems:
        lines.append(
            "PROBLEMS — fix these and call the tool again now, then share only the new link: "
            + "; ".join(problems)
        )
    if notes:
        lines.append("Checked and adjusted automatically: " + "; ".join(notes) + ".")
    if extra:
        lines.append(extra)
    if embeddable:
        lines.append("To put this image in a Word, PDF or PowerPoint document, use ![caption](link).")
    lines.append(f"File link (give it to the user as a Markdown link, copied exactly): {link}")
    content = [TextContent(type="text", text="\n".join(lines))]
    if image and PREVIEW_IMAGES:
        content.append(preview(image))
    return ToolResult(content=content)


def store_image(png: bytes, file_name: str, image_format: str) -> str:
    if image_format == "jpg":
        out = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("RGB").save(out, "JPEG", quality=92)
        return storage.store(out.getvalue(), file_name, "jpg", "image/jpeg", inline=True)
    return storage.store(png, file_name, "png", "image/png", inline=True)


@mcp.tool
def create_pdf_from_markdown(
    markdown_content: str,
    file_name: str = "document",
    title: str | None = None,
    landscape: bool = False,
) -> ToolResult:
    """Create a PDF file from Markdown and return a download link.

    Supports headings, paragraphs, bold/italic, bullet and numbered lists, tables, block quotes,
    code blocks and horizontal rules, in Thai and English. Images are included from links
    returned by create_chart / create_diagram. Do not repeat the title as the first heading.

    :param markdown_content: The full document in Markdown.
    :param file_name: File name without extension, in English.
    :param title: Optional title shown as the top heading and stored in the PDF metadata.
    :param landscape: True for landscape pages (wide tables). Tables with 7+ columns switch
        to landscape automatically.
    """
    pdf, png, pages, notes, problems = render_pdf(markdown_content, title, landscape)
    link = storage.store(pdf, file_name, "pdf", "application/pdf")
    return report(link, notes, problems, image=png, extra=f"{pages} page(s).")


TEXT_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "html": "text/html; charset=utf-8",
}
TEXT_HELP = {
    "txt": "txt (plain text)",
    "md": "md (Markdown)",
    "csv": "csv (comma-separated table; opens in Excel with Thai intact)",
    "json": "json (must be valid JSON; it is pretty-printed)",
    "html": "html (a complete web page)",
}
MAX_TEXT_BYTES = 5 * 1024 * 1024
# Only the formats switched on in office.env are offered (features.py).
TextType = Literal[tuple(features.TEXT_TYPES or TEXT_HELP)]


def create_text_file(
    content: str,
    file_type: TextType,
    file_name: str = "document",
) -> ToolResult:
    if not content.strip():
        raise ValueError("content is empty; pass the whole file text in content")
    notes = []
    if file_type == "json":
        try:
            content = json.dumps(json.loads(content), ensure_ascii=False, indent=2) + "\n"
        except json.JSONDecodeError as err:
            raise ValueError(f"content is not valid JSON ({err}); fix it and call again") from err
    if file_type == "csv":
        widths = {len(row) for row in csv.reader(io.StringIO(content.strip())) if row}
        if len(widths) > 1:
            notes.append(
                f"rows have different numbers of columns ({sorted(widths)}); quote values that "
                "contain commas if that was not intended"
            )
    # Excel reads a CSV without a byte-order mark as the local code page, garbling Thai.
    data = content.encode("utf-8-sig" if file_type == "csv" else "utf-8")
    if len(data) > MAX_TEXT_BYTES:
        raise ValueError("content is larger than 5 MB")
    return report(storage.store(data, file_name, file_type, TEXT_TYPES[file_type]), notes)


create_text_file.__doc__ = f"""Create a plain-text file and return a download link.

    {", ".join(TEXT_HELP[ext] for ext in features.TEXT_TYPES)}.

    :param content: The full file content.
    :param file_type: {", ".join(features.TEXT_TYPES)}.
    :param file_name: File name without extension, in English.
    """
mcp.tool(create_text_file)


@mcp.tool
def create_chart(
    chart_type: Literal["bar", "horizontal_bar", "line", "pie"],
    labels: list[str],
    series: list[Series],
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    image_format: Literal["png", "jpg"] = "png",
    file_name: str = "chart",
) -> ToolResult:
    """Draw a chart in the AI Hub colours and return its link.

    Long category labels are fine: the chart is checked after drawing and switched to
    horizontal bars, tilted labels or a legend if labels would overlap. A pie uses only the
    first series. Use the link as ![caption](link) in Word, PDF or PowerPoint Markdown.

    :param chart_type: bar, horizontal_bar, line or pie.
    :param labels: Category labels (or pie slices).
    :param series: One or more data series, each with one value per label.
    :param title: Chart title.
    :param x_label: Axis title for the categories.
    :param y_label: Axis title for the values.
    :param image_format: png (default) or jpg.
    :param file_name: File name without extension, in English.
    """
    png, notes = draw_chart(chart_type, labels, series, title, x_label, y_label)
    return report(store_image(png, file_name, image_format), notes, image=png, embeddable=True)


@mcp.tool
def create_diagram(
    diagram_type: Literal["flowchart", "org_chart", "timeline", "mind_map"],
    nodes: list[DiagramNode] | None = None,
    edges: list[DiagramEdge] | None = None,
    events: list[TimelineEvent] | None = None,
    title: str = "",
    direction: Literal["auto", "top_down", "left_right"] = "auto",
    image_format: Literal["png", "jpg"] = "png",
    file_name: str = "diagram",
) -> ToolResult:
    """Draw a diagram in the AI Hub colours and return its link.

    flowchart: nodes (kind sets the shape) joined by edges (arrows, optional labels).
    org_chart: nodes for people or units, edges from each superior to each subordinate.
    mind_map: the first node is the centre, edges link it to topics and sub-topics.
    timeline: events in order (nodes and edges are not used).
    Use the link as ![caption](link) in Word, PDF or PowerPoint Markdown.

    :param diagram_type: flowchart, org_chart, timeline or mind_map.
    :param nodes: Boxes for flowchart, org_chart and mind_map.
    :param edges: Connections between node ids.
    :param events: Timeline events in order.
    :param title: Title shown above the diagram.
    :param direction: auto, top_down or left_right (flowchart, org_chart, timeline).
    :param image_format: png (default) or jpg.
    :param file_name: File name without extension, in English.
    """
    png, problems = draw_diagram(diagram_type, nodes, edges, events, title, direction)
    return report(store_image(png, file_name, image_format), problems=problems, image=png, embeddable=True)


AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"]
ImageModel = Literal[tuple(images.MODELS)]


def create_image(
    prompt: str,
    model: ImageModel = images.MODELS[0],
    aspect_ratio: AspectRatio = "1:1",
    edit_image_link: str | None = None,
    file_name: str = "image",
) -> ToolResult:
    if not prompt.strip():
        raise ValueError("prompt is empty; describe the picture")
    png, cost = images.generate(model, prompt.strip(), aspect_ratio, edit_image_link)
    link = store_image(png, file_name, "png")
    print(f"create_image {model} {aspect_ratio} cost={cost}", flush=True)
    extra = (
        f"Made with {model}. Show the picture in your reply as ![short description](link) on its "
        "own line, then the link to download it."
    )
    return report(link, image=png, embeddable=True, extra=extra)


create_image.__doc__ = f"""Create a picture with an AI image model (illustration, photo-style image, poster,
    banner, icon, cover) or edit a picture this tool made earlier, and return its link.

    Only when the user asks for a picture. Write the prompt in English, describing the subject,
    style, colours and layout; put any words that must appear in the picture in quotes. To edit,
    pass the earlier link in edit_image_link and describe only the change. Each call costs money:
    make one picture per request unless the user asks for options.

    :param prompt: What to draw, or for an edit, what to change.
    :param model: {", ".join(images.MODELS)}. Default {images.MODELS[0]}.
    :param aspect_ratio: 1:1 (default), 16:9 (slide, banner), 9:16 (story, poster), 4:3, 3:4, 3:2, 2:3.
    :param edit_image_link: Link of a picture made by create_image to edit; leave empty for a new picture.
    :param file_name: File name without extension, in English.
    """
mcp.tool(create_image)


def admin_headers() -> dict[str, str]:
    headers = get_http_headers(include_all=True)
    admin.require_admin(headers)
    return headers


@mcp.tool
def usage_report(days: int = 30) -> ToolResult:
    """Administrators only: usage report as an Excel file (per user, per model, per day: messages,
    chats, prompt and completion tokens, cost in USD).

    :param days: How many days back to include (1-366). Default 30.
    """
    headers = admin_headers()
    if not 1 <= days <= 366:
        raise ValueError("days must be between 1 and 366")
    data, summary = admin.usage_workbook(days)
    print(f"usage report ({days} days) for admin {headers.get('x-user-id')}", flush=True)
    link = storage.store(data, f"usage-report-{days}d", "xlsx", XLSX)
    return report(link, extra=summary)


@mcp.tool
def manage_credits(
    action: Literal["list", "add", "set"],
    email: str | None = None,
    credits: int | None = None,
) -> ToolResult:
    """Administrators only: see or change users' token credits (1,000,000 credits = 1 USD).

    list: every user's balance (lowest first), with an Excel file.
    add: top up one user by credits. set: set one user's balance to exactly credits.
    Confirm the user's email and the amount with the administrator before add or set.

    :param action: list, add or set.
    :param email: The user's email (for add and set).
    :param credits: Number of credits (for add and set).
    """
    headers = admin_headers()
    if action == "list":
        data, text = admin.balances()
        return report(storage.store(data, "credits", "xlsx", XLSX), extra=text)
    if not email or credits is None:
        raise ValueError("add and set need email and credits")
    text = admin.change_credits(action, email, credits, headers.get("x-user-id") or "unknown")
    return ToolResult(content=[TextContent(type="text", text=text)])


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OWN_TOOLS = {
    "create_pdf_from_markdown", "create_text_file", "create_chart", "create_diagram",
    "create_image", "usage_report", "manage_credits",
}
EXPIRY_TEXT = re.compile(r"\s*\.?\s*Link is valid for \d+ seconds\.?", re.IGNORECASE)
OLD_PREFIX = re.compile(r"^[0-9a-f]{8}_")


async def expected_arguments(name: str) -> str:
    try:
        tool = await mcp.get_tool(name)
        props = tool.parameters.get("properties", {})
        required = set(tool.parameters.get("required", []))
        return ", ".join(f"{p}{' (required)' if p in required else ''}" for p in props)
    except Exception:
        return ""


def office_docs_warnings(text: str) -> list[str]:
    """office-docs reports what did not fit (e.g. a memo drop-down without the given item) as
    JSON {"file": ..., "warnings": [...]} instead of the plain link message."""
    try:
        payload = json.loads(text)
    except ValueError:
        return []
    warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
    return [w.get("message", str(w)) if isinstance(w, dict) else str(w) for w in warnings]


def adopt(url: str, arguments: dict) -> tuple[str, list, list]:
    """Moves an office-docs file to a short link, after checking and repairing it."""
    key = storage.own_key(url)
    data, content_type = storage.read(key)
    base = key.rsplit("/", 1)[-1]
    stem, _, extension = OLD_PREFIX.sub("", base).rpartition(".")
    if not stem or names.is_random(stem):
        stem = names.from_arguments(arguments, extension)
    notes, problems = [], []
    check = CHECKS.get(extension.lower())
    if check:
        try:
            data, notes, problems = (
                check(data, arguments.get("markdown_content", "")) if extension == "docx" else check(data)
            )
        except Exception as err:  # a checker fault must never cost the user the file
            print(f"check of {base} failed: {err}", flush=True)
    link = storage.store(data, stem, extension, content_type)
    storage.remove(key)
    return link, notes, problems


def drop_nulls(value):
    """Some models (GPT-5.6) send every optional field as null. office-docs rejects a field that
    does not belong to a slide type even when it is null, so unset fields are left out."""
    if isinstance(value, dict):
        return {key: drop_nulls(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [drop_nulls(item) for item in value]
    return value


SLIDE_TOOL = "create_powerpoint_presentation"
SLIDE_TYPES = re.compile(r"\[([a-z_, ]+)\]")
_slide_fields: dict[str, set[str]] = {}


async def slide_fields() -> dict[str, set[str]]:
    """Field -> slide types that take it, read from the "[content] ..." tags the PowerPoint
    tool puts at the start of each field description."""
    if not _slide_fields:
        tool = await mcp.get_tool(SLIDE_TOOL)
        props = tool.parameters.get("properties", {}).get("slides", {}).get("items", {}).get("properties", {})
        for field, spec in props.items():
            types = {t.strip() for group in SLIDE_TYPES.findall(spec.get("description", "")) for t in group.split(",")}
            if types:
                _slide_fields[field] = types
    return _slide_fields


async def fit_slides(arguments: dict) -> dict:
    """The same models also fill fields of other slide types (categories, chart_type ... on a
    title slide), which office-docs rejects; each slide keeps only the fields its type takes."""
    slides = arguments.get("slides")
    if not isinstance(slides, list):
        return arguments
    fields = await slide_fields()
    fitted = [
        {
            key: item
            for key, item in slide.items()
            if key not in fields or "all types" in fields[key] or slide.get("type") in fields[key]
        }
        if isinstance(slide, dict)
        else slide
        for slide in slides
    ]
    return {**arguments, "slides": fitted}


class QualityGate(ToolMiddleware):
    async def on_call_tool(self, context, call_next):
        name = context.message.name
        if name not in OWN_TOOLS and context.message.arguments:
            context.message.arguments = drop_nulls(context.message.arguments)
            if name == SLIDE_TOOL:
                context.message.arguments = await fit_slides(context.message.arguments)
        arguments = context.message.arguments or {}
        try:
            result = await call_next(context)
        except Exception as err:
            expected = await expected_arguments(name)
            raise ToolError(
                f"{err}\n\nNothing was created. Fix the arguments and call {name} again now, in "
                "this same turn, without asking the user."
                + (f" Arguments: {expected}." if expected else "")
            ) from err
        if name in OWN_TOOLS or result.content is None:
            return result

        content = []
        for block in result.content:
            if not isinstance(block, TextContent):
                content.append(block)
                continue
            text = EXPIRY_TEXT.sub("", block.text)
            notes, problems, links = [], [], []
            # Only the signed links are files office-docs made; other links into the bucket
            # (an image a warning names) are left as they are.
            for url in dict.fromkeys(u for u in storage.OWN_LINK.findall(text) if "X-Amz-Signature" in u):
                try:
                    link, n, p = adopt(url, arguments)
                except Exception as err:
                    print(f"could not move {url[:120]}: {err}", flush=True)
                    continue
                text = text.replace(url, link)
                links.append(link)
                notes += n
                problems += p
            if links:
                problems += office_docs_warnings(text)
                others = f"Other files from this call: {', '.join(links[:-1])}" if len(links) > 1 else ""
                content += report(links[-1], notes, problems, extra=others).content
            else:
                content.append(TextContent(type="text", text=text))
        return ToolResult(content=content, structured_content=result.structured_content)


class Switches(ToolMiddleware):
    """Hides and refuses the tools of file kinds switched off in office.env (features.py)."""

    async def on_list_tools(self, context, call_next):
        # LibreChat reaches this server through two entries in librechat.yaml: office-files
        # (file tools, shared by every chat) and office-admin (X-AIHub-Scope: admin, with the
        # user's id and role), so each entry lists only its own tools. Calls still check the role.
        tools = await call_next(context)
        admin_scope = get_http_headers(include_all=True).get("x-aihub-scope") == "admin"
        return [
            tool.model_copy(update={"parameters": schemas.slim(tool.name, tool.parameters)})
            for tool in tools
            if tool.name not in features.DISABLED_TOOLS and (tool.name in features.ADMIN_TOOLS) == admin_scope
        ]

    async def on_call_tool(self, context, call_next):
        name = context.message.name
        if name in features.ADMIN_TOOLS and not admin.is_admin(get_http_headers(include_all=True)):
            raise ToolError(f"{name} is for administrators only. Tell the user they need an administrator.")
        file_type = (context.message.arguments or {}).get("file_type")
        if name == "create_text_file" and file_type not in features.TEXT_TYPES:
            name = f".{file_type}"
        if name in features.DISABLED_TOOLS or name.startswith("."):
            raise ToolError(
                f"{name} is switched off on this server. Tell the user this file type cannot be "
                "created here, and do not create the file in another format."
            )
        return await call_next(context)


mcp.add_middleware(Switches())
mcp.add_middleware(QualityGate())


class BearerAuth(BaseHTTPMiddleware):
    """Requires the API key on MCP calls. HEAD and well-known probes pass through to their
    normal 405/404, because LibreChat reads a 401 on its unauthenticated probe as OAuth."""

    async def dispatch(self, request, call_next):
        if not API_KEY or request.method == "HEAD" or not request.url.path.startswith("/mcp"):
            return await call_next(request)
        header = request.headers.get("authorization", "")
        token = header[7:] if header.lower().startswith("bearer ") else header
        if not hmac.compare_digest(token, API_KEY):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


LOGS_DIR = os.environ.get("LOGS_DIR", "/librechat-logs")
LIBRECHAT_API_URL = os.environ.get("LIBRECHAT_API_URL", "http://api:3080")
LOGS_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.html")
LOG_LEVELS = set(logs.LEVELS) | {"login"}


async def librechat_user(url: str, token: str) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {}


def log_error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": code}, status_code=status, headers={"Cache-Control": "no-store"})


async def logs_admin(request) -> tuple[dict | None, JSONResponse | None]:
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    try:
        return await logs.admin_user(token, librechat_user, LIBRECHAT_API_URL), None
    except logs.Unauthorized:
        return None, log_error(401, "signin")
    except logs.Forbidden:
        return None, log_error(403, "admin")
    except logs.Unavailable as err:
        print(f"log page: cannot ask LibreChat who is signed in: {err}", flush=True)
        return None, log_error(503, "unavailable")


USAGE_PAGE_SIZE = 50


def emails_of(db, ids) -> dict:
    ids = [i for i in ids if i]
    return {str(u["_id"]): u.get("email", "") for u in db.users.find({"_id": {"$in": ids}}, {"email": 1})} if ids else {}


def usage_page(range_name: str, text: str, page: int, group: str | None) -> dict:
    """One page of the AI usage log (usage.py) from LibreChat's database: calls, or their sums
    per user or per model."""
    since = usage.window(range_name)
    db = admin.db()
    user_ids = []
    if text:
        found = db.users.find({"email": {"$regex": re.escape(text), "$options": "i"}}, {"_id": 1}).limit(500)
        user_ids = [u["_id"] for u in found]
    stages = usage.pipeline(since, datetime.now(timezone.utc), user_ids, text, page, USAGE_PAGE_SIZE, group)
    result = next(iter(db.transactions.aggregate(stages, allowDiskUse=True)), {"rows": [], "totals": [], "count": []})
    totals = usage.summary(result["totals"])
    count = (result.get("count") or [{}])[0].get("n", 0)
    if group:
        emails = emails_of(db, [doc["_id"] for doc in result["rows"]]) if group == "user" else {}
        rows = [usage.group_row(doc, group, emails) for doc in result["rows"]]
    else:
        emails = emails_of(db, {doc["_id"].get("user") for doc in result["rows"]})
        rows = [usage.row(doc, emails) for doc in result["rows"]]
    return {
        "rows": rows,
        "summary": totals,
        "total": count,
        "page": max(1, page),
        "pages": max(1, -(-count // USAGE_PAGE_SIZE)),
    }


def credits_page(text: str, page: int) -> dict:
    """Every user's credit balance (usage.py), lowest first."""
    result = next(iter(admin.db().balances.aggregate(usage.credits_pipeline(text, page, USAGE_PAGE_SIZE))),
                  {"rows": [], "totals": []})
    totals = usage.credit_summary(result["totals"])
    return {
        "rows": [usage.credit_row(doc) for doc in result["rows"]],
        "summary": totals,
        "total": totals["users"],
        "page": max(1, page),
        "pages": max(1, -(-totals["users"] // USAGE_PAGE_SIZE)),
    }


def logs_routes() -> None:
    """The administrators' log page, only when OFFICE_LOGS=on (features.py)."""

    @mcp.custom_route("/aihub-logs/", methods=["GET"])
    async def logs_page(request):
        # Shown inside the chat page (branding/admin.js) on the same site only.
        return FileResponse(
            LOGS_PAGE,
            headers={
                "Cache-Control": "no-store",
                "X-Frame-Options": "SAMEORIGIN",
                "Content-Security-Policy": "frame-ancestors 'self'",
            },
        )

    @mcp.custom_route("/aihub-logs/api/files", methods=["GET"])
    async def logs_files(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        return JSONResponse(
            {"files": logs.list_files(LOGS_DIR), "user": user.get("email") or user.get("username", "")},
            headers={"Cache-Control": "no-store"},
        )

    @mcp.custom_route("/aihub-logs/api/days", methods=["GET"])
    async def logs_days(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        return JSONResponse(
            {"days": logs.days(LOGS_DIR), "user": user.get("email") or user.get("username", "")},
            headers={"Cache-Control": "no-store"},
        )

    @mcp.custom_route("/aihub-logs/api/usage", methods=["GET"])
    async def logs_usage(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        if not admin.MONGO_URI:
            return log_error(503, "nodb")
        query = request.query_params
        group = query.get("group") or None
        try:
            data = await asyncio.to_thread(
                usage_page, query.get("range", "24h"), query.get("q", "").strip()[:100], int(query.get("page", 1)), group
            )
        except ValueError:
            return log_error(400, "range")
        print(f"log page: {user.get('email', user.get('_id'))} viewed AI usage ({query.get('range', '24h')})", flush=True)
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/aihub-logs/api/credits", methods=["GET"])
    async def logs_credits(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        if not admin.MONGO_URI:
            return log_error(503, "nodb")
        query = request.query_params
        try:
            data = await asyncio.to_thread(credits_page, query.get("q", "").strip()[:100], int(query.get("page", 1)))
        except ValueError:
            return log_error(400, "paging")
        print(f"log page: {user.get('email', user.get('_id'))} viewed user credits", flush=True)
        return JSONResponse(data, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/aihub-logs/api/credits", methods=["POST"])
    async def logs_credits_change(request):
        """Top up (add) or set one user's credits; the same change manage_credits makes."""
        user, refused = await logs_admin(request)
        if refused:
            return refused
        if not admin.MONGO_URI:
            return log_error(503, "nodb")
        try:
            body = await request.json()
            action = body.get("action")
            email = str(body.get("email", "")).strip()
            credits = body.get("credits")
            if action not in ("add", "set") or not email or not isinstance(credits, int) or isinstance(credits, bool):
                raise ValueError("action (add or set), email and a whole number of credits are needed")
            admin_id = str(user.get("id") or user.get("_id") or user.get("email") or "unknown")
            text = await asyncio.to_thread(admin.change_credits, action, email, credits, admin_id)
        except ValueError as err:
            return JSONResponse({"error": "invalid", "message": str(err)}, status_code=400, headers={"Cache-Control": "no-store"})
        print(f"log page: {user.get('email', admin_id)} {action} credits for {email}", flush=True)
        return JSONResponse({"message": text}, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/aihub-logs/api/entries", methods=["GET"])
    async def logs_entries(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        query = request.query_params
        name = query.get("file", "")
        levels = {level for level in query.get("levels", "").split(",") if level in LOG_LEVELS} or None
        try:
            entries = logs.read_entries(LOGS_DIR, name)
            page = logs.select(entries, levels, query.get("q", "")[:200], int(query.get("page", 1)), int(query.get("size", 100)))
        except logs.NotAllowed:
            return log_error(400, "name")
        except FileNotFoundError:
            return log_error(404, "missing")
        except ValueError:
            return log_error(400, "paging")
        print(f"log page: {user.get('email', user.get('_id'))} viewed {name}", flush=True)
        return JSONResponse(page, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/aihub-logs/api/download", methods=["GET"])
    async def logs_download(request):
        user, refused = await logs_admin(request)
        if refused:
            return refused
        name = request.query_params.get("file", "")
        try:
            text = logs.redacted_file(LOGS_DIR, name)
        except logs.NotAllowed:
            return log_error(400, "name")
        except FileNotFoundError:
            return log_error(404, "missing")
        print(f"log page: {user.get('email', user.get('_id'))} downloaded {name}", flush=True)
        download = re.sub(r"\.gz$", "", name)
        return PlainTextResponse(
            text,
            headers={"Content-Disposition": f'attachment; filename="{download}"', "Cache-Control": "no-store"},
        )


if features.LOGS_PAGE:
    logs_routes()

app = mcp.http_app(path="/mcp", middleware=[Middleware(BearerAuth)])

if __name__ == "__main__":
    storage.ensure_bucket()
    threading.Thread(target=storage.sweep_forever, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
