"""Shorter tool descriptions for the tool list LibreChat sends with every chat message.

LibreChat puts every tool's JSON schema into each request, so its size is paid on every message
whether or not a file is made. The office-docs schemas are written for any client and carry a
lot that is noise here; this module rewrites only the copy that is listed, never what a call is
checked against:
- an optional "X or null" field becomes plain X (nulls a model still sends are dropped before
  the call, see drop_nulls in server.py);
- add_unique_prefix is left out (the file is moved to a short link either way);
- file_name says what it is for here instead of "a unique identifier will be used";
- PowerPoint: the "blank" slide type (free-positioned elements, about a third of the schema) and
  the per-slide layout override are left out, since the typed slides cover a chat's decks, and
  the long slides description is replaced by the rules the field descriptions do not carry;
- Word: the Markdown guide keeps every rule but drops the worked examples.
"""

import re

DROP_FIELDS = {"add_unique_prefix"}
FILE_NAME_HELP = "File name without extension, in English."

SLIDE_TOOL = "create_powerpoint_presentation"
SLIDE_DROP_TYPES = {"blank"}
SLIDE_DROP_FIELDS = {"elements", "layout"}
SLIDE_TEXT_CUTS = (re.compile(r"blank: elements; "),)
# office-docs' own text runs to ~3,500 characters; the field descriptions already say which slide
# types take each field, so this keeps only the rules they cannot express.
SLIDES_HELP = (
    "Ordered slides. 'type' picks the slide kind and each field's description names the types "
    "that accept it; a field on the wrong type fails the whole call.\n"
    "Structure: start with 'title', then 'agenda' (leave out its items to build it from the "
    "section slides), divide with 'section', end with 'closing'. 'kpi' for 2-4 headline figures, "
    "'timeline' for 3-5 steps, 'chart' for category data (each series' values as long as "
    "categories), 'scatter' for [x, y] points.\n"
    "'body' (content, chart, image) and 'left'/'right' (two_column): a Markdown bullet string, "
    "'- item' per line, indent to nest.\n"
    "Text fields take **bold**, *italic*, __underline__, ~~strike~~, `code` and "
    "[label](https://url) links.\n"
    "Tables: 'rows' with the header row first; 'widths' are relative weights; 'fills' "
    "({row, col, color}) and 'merges' ({row, col, row_span, col_span}) count the header as row 0.\n"
    "Colours: a theme name (accent1..accent6, dark1, dark2, light1, light2) or 6-digit hex.\n"
    "Images: 'source' is an https link.\n"
    "Text that does not fit is shrunk and reported in 'warnings': split long content across slides."
)

WORD_TOOL = "create_word_from_markdown"
# The same rules as office-docs' ~3,900-character text, without its examples for Czech dates,
# formatting combinations and contract layout.
WORD_MARKDOWN_HELP = (
    "The document body in Markdown; separate blocks with blank lines.\n"
    "Blocks: # to ###### headings; - bullets and 1. numbered lists (indent to nest; keep "
    "numbering running 3., 4. across text between items, restart at 1.); tables (header row, "
    "|---| separator with :---: for alignment, <br> for a line break in a cell); "
    "<!-- borderless --> or <!-- widths: 30 70 --> on the line before a table; > quotes; "
    "![alt](url) images; ``` code blocks; --- alone on a line is a PAGE BREAK, *** a horizontal "
    "line; <!-- style: Name --> before a block applies that Word style.\n"
    "Inline: **bold**, *italic*, __underline__ (not bold), ~~strike~~, `code`, x^2^, H~2~O, "
    "==highlight==, [text](https://url). Escape a literal marker or a line-leading number's dot "
    "with a backslash.\n"
    "Alignment: <center>text</center> or <div align=\"right|center|justify\">text</div>.\n"
    "A line break inside a paragraph is <br>; never write a literal backslash-n."
)


def is_null(schema) -> bool:
    return isinstance(schema, dict) and schema.get("type") == "null" and len(schema) == 1


def compact(schema):
    """Copy of a JSON schema without nullable unions and null defaults."""
    if isinstance(schema, list):
        return [compact(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    optional = "default" in schema and schema["default"] is None
    out = {key: compact(value) for key, value in schema.items() if not (key == "default" and optional)}
    options = out.get("anyOf")
    if optional and isinstance(options, list) and any(is_null(o) for o in options):
        rest = [o for o in options if not is_null(o)]
        del out["anyOf"]
        if len(rest) == 1 and isinstance(rest[0], dict):
            out = {**rest[0], **out}
        elif rest:
            out["anyOf"] = rest
    return out


def cut(text: str) -> str:
    for pattern in SLIDE_TEXT_CUTS:
        text = pattern.sub("", text)
    return text


def trim_slides(parameters: dict) -> dict:
    slides = parameters.get("properties", {}).get("slides")
    if not isinstance(slides, dict):
        return parameters
    item = slides.get("items", {})
    props = {k: v for k, v in item.get("properties", {}).items() if k not in SLIDE_DROP_FIELDS}
    kind = props.get("type")
    if isinstance(kind, dict) and isinstance(kind.get("enum"), list):
        props["type"] = {**kind, "enum": [t for t in kind["enum"] if t not in SLIDE_DROP_TYPES]}
    item = {
        **item,
        "properties": props,
        "required": [r for r in item.get("required", []) if r not in SLIDE_DROP_FIELDS],
    }
    if isinstance(item.get("description"), str):
        item["description"] = cut(item["description"])
    slides = {**slides, "items": item, "description": SLIDES_HELP}
    return {**parameters, "properties": {**parameters["properties"], "slides": slides}}


def slim(name: str, parameters: dict) -> dict:
    """The parameters schema as listed to the model."""
    if not isinstance(parameters, dict):
        return parameters
    params = compact(parameters)
    props = params.get("properties")
    if isinstance(props, dict):
        props = {k: v for k, v in props.items() if k not in DROP_FIELDS}
        if isinstance(props.get("file_name"), dict):
            props["file_name"] = {**props["file_name"], "description": FILE_NAME_HELP}
        params = {
            **params,
            "properties": props,
            "required": [r for r in params.get("required", []) if r not in DROP_FIELDS],
        }
        if not params["required"]:
            del params["required"]
        if name == WORD_TOOL and isinstance(props.get("markdown_content"), dict):
            props["markdown_content"] = {**props["markdown_content"], "description": WORD_MARKDOWN_HELP}
    return trim_slides(params) if name == SLIDE_TOOL else params
