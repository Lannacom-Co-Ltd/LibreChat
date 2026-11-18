"""On/off switches for each kind of file, set in office.env (OFFICE_WORD=off and so on).

Every switch defaults to on, so a deployment without them behaves as before. A file kind that
is off is left out of the tool list LibreChat reads (so the model neither sees nor pays for its
description), out of the instructions, and is refused if called anyway; the model is told not
to make it in another format instead. The text formats (txt, md, csv, json, html) share one
tool and have a switch each. LibreChat reads the tool list once at start-up: recreate its api
container after changing a switch.
"""

import os

OFF = {"off", "false", "0", "no"}


def is_on(switch: str) -> bool:
    return os.environ.get(switch, "on").strip().lower() not in OFF


TEXT_TYPES = [ext for ext in ("txt", "md", "csv", "json", "html") if is_on(f"OFFICE_{ext.upper()}")]

# switch -> (tools, how the instructions name it)
FEATURES = {
    "OFFICE_WORD": ({"create_word_from_markdown"}, "create_word_from_markdown (.docx)"),
    "OFFICE_EXCEL": ({"create_excel_from_markdown"}, "create_excel_from_markdown (.xlsx)"),
    "OFFICE_POWERPOINT": (
        {"create_powerpoint_presentation", "list_presentation_templates"},
        "create_powerpoint_presentation (.pptx)",
    ),
    "OFFICE_PDF": ({"create_pdf_from_markdown"}, "create_pdf_from_markdown (.pdf)"),
    "OFFICE_EMAIL": ({"create_email_draft"}, "create_email_draft (.eml)"),
    "OFFICE_XML": ({"create_xml_file"}, "create_xml_file (.xml)"),
    "OFFICE_MEMO": ({"thai_memo"}, "thai_memo for an official Thai internal memo (บันทึกข้อความ)"),
    "OFFICE_CHART": ({"create_chart"}, "create_chart (a chart image)"),
    "OFFICE_DIAGRAM": ({"create_diagram"}, "create_diagram (a diagram image)"),
}

ENABLED = [switch for switch in FEATURES if is_on(switch)]
DISABLED_TOOLS = {tool for switch, (tools, _) in FEATURES.items() if switch not in ENABLED for tool in tools}
if not TEXT_TYPES:
    DISABLED_TOOLS.add("create_text_file")


def instructions() -> str:
    kinds = [FEATURES[switch][1] for switch in ENABLED]
    if TEXT_TYPES:
        kinds.append(f"create_text_file ({', '.join('.' + ext for ext in TEXT_TYPES)})")
    images = [name for switch, name in (("OFFICE_CHART", "create_chart"), ("OFFICE_DIAGRAM", "create_diagram")) if switch in ENABLED]
    documents = [name for switch, name in (("OFFICE_WORD", "Word"), ("OFFICE_PDF", "PDF"), ("OFFICE_POWERPOINT", "PowerPoint")) if switch in ENABLED]
    embedding = (
        f"For a chart or diagram inside a {', '.join(documents)} document, call {' or '.join(images)} "
        "first and put the returned link in the document's Markdown as ![caption](link). "
        if images and documents
        else ""
    )
    return (
        "Tools for creating files the user can download. They are available in every chat, so only "
        "create a file when the user asks for one (a file, a document, a download or a named "
        "format); otherwise answer in the chat as usual. "
        f"These are the only file types that can be created here: {'; '.join(kinds)}. "
        "Make exactly the file the user asked for, in the format they named, and only one file "
        "unless they ask for more. If they ask for a file type that is not in this list, tell them "
        "briefly that this type cannot be created here and stop: do not create a file in another "
        f"format instead, and do not create one unless they ask for it. {embedding}"
        "Pass file_name in English (letters, digits, hyphens, underscores), even for a Thai "
        "document. Every result ends with the file's link: give it to the user as a Markdown link "
        "copied exactly. If a result lists problems, or a call fails, fix the arguments and call "
        "the tool again in the same turn, before answering the user; do not ask the user to repeat "
        "the request."
    )
