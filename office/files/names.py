"""A readable name for a file office-docs saved under a random one.

office-docs names a file with a random identifier when the model leaves out file_name (models
do, despite the instructions), and the user then downloads 3f2a9c...docx. The name is taken
instead from what the file is about: its title, its first heading or its first slide's title.
Thai is fine here: the link keeps an ASCII key and the Thai name goes in the download header.
"""

import re

RANDOM = re.compile(r"^(?:[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}|[0-9a-f]{16,})$", re.IGNORECASE)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(?!Sheet:)(.+?)\s*#*\s*$", re.MULTILINE | re.IGNORECASE)
MARKUP = re.compile(r"[*_~`^=\[\]<>]|\(https?://[^)]*\)")
FALLBACK = {"docx": "document", "xlsx": "spreadsheet", "pptx": "presentation", "eml": "email", "xml": "data"}
MAX_LENGTH = 60


def is_random(stem: str) -> bool:
    return bool(RANDOM.match(stem or ""))


def plain(text) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", MARKUP.sub("", text)).strip()[:MAX_LENGTH].strip()


def first_slide_title(slides) -> str:
    if not isinstance(slides, list):
        return ""
    return next((plain(s.get("title")) for s in slides if isinstance(s, dict) and plain(s.get("title"))), "")


def from_arguments(arguments: dict, extension: str) -> str:
    """Best name for the file the call made, from its own arguments."""
    arguments = arguments if isinstance(arguments, dict) else {}
    heading = HEADING.search(arguments.get("markdown_content") or "") if isinstance(arguments.get("markdown_content"), str) else None
    for candidate in (
        arguments.get("file_name"),
        arguments.get("title"),
        arguments.get("subject"),
        heading.group(1) if heading else "",
        first_slide_title(arguments.get("slides")),
    ):
        name = plain(candidate)
        if name:
            return name
    return FALLBACK.get(extension.lower(), "document")
