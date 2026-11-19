"""Puts assistant/system-prompt.md into every model spec of librechat.yaml as its promptPrefix.

LibreChat turns a spec's promptPrefix into the instructions of the chat's agent, so every new
chat with a listed model starts from the organisation's system prompt. Supports both a shared
YAML anchor (`promptPrefix: &aihub_prompt |` + `*aihub_prompt` aliases) and per-preset blocks.
Running it again replaces the previous prompt; nothing else in the file changes. A copy of the
file is kept first.

  python3 assistant/apply-system-prompt.py librechat.yaml
"""

import re
import shutil
import sys
import time
from pathlib import Path

PRESET = "      preset:"
KEY = "        promptPrefix: |"
BODY = "          "
ANCHOR_RE = re.compile(r"^(\s*)promptPrefix:\s*(&[A-Za-z0-9_-]+)\s*\|[+-]?\s*$")


def format_block(header: str, body_indent: str, prompt: str) -> list[str]:
    return [header] + [f"{body_indent}{line}" if line.strip() else "" for line in prompt.splitlines()]


def apply_anchored(lines: list[str], prompt: str) -> tuple[list[str], int]:
    out: list[str] = []
    in_specs = False
    skipping = False
    body_indent = ""
    pending_blanks: list[str] = []
    count = 0

    for line in lines:
        if not line.startswith((" ", "#")) and line.strip():
            in_specs = line.startswith("modelSpecs:")

        if skipping:
            if not line.strip():
                pending_blanks.append(line)
                continue
            if line.startswith(body_indent):
                pending_blanks.clear()
                continue
            out.extend(pending_blanks)
            pending_blanks.clear()
            skipping = False

        if in_specs:
            match = ANCHOR_RE.match(line)
            if match:
                key_indent = match.group(1)
                body_indent = key_indent + "  "
                out.extend(format_block(line.rstrip(), body_indent, prompt))
                skipping = True
                count += 1
                continue

        out.append(line)

    if skipping and pending_blanks:
        out.extend(pending_blanks)

    return out, count


def apply_per_preset(lines: list[str], prompt: str) -> tuple[list[str], int]:
    block = format_block(KEY, BODY, prompt)
    out, in_specs, skipping, count = [], False, False, 0
    for line in lines:
        if not line.startswith((" ", "#")) and line.strip():
            in_specs = line.startswith("modelSpecs:")
        if skipping:
            if not line.strip() or line.startswith(BODY):
                continue
            skipping = False
        if in_specs and line.rstrip() == KEY:
            skipping = True
            continue
        out.append(line)
        if in_specs and line.rstrip() == PRESET:
            out.extend(block)
            count += 1
    return out, count


def main(argv: list[str]) -> None:
    no_backup = "--no-backup" in argv
    args = [a for a in argv if a != "--no-backup"]
    target = Path(args[0] if args else "librechat.yaml")
    prompt = (Path(__file__).parent / "system-prompt.md").read_text(encoding="utf-8").strip()
    lines = target.read_text(encoding="utf-8").splitlines()

    out, anchor_count = apply_anchored(lines, prompt)
    if anchor_count:
        alias_count = sum(1 for l in out if re.match(r"^\s*promptPrefix:\s*\*", l))
        summary = f"updated {anchor_count} anchored promptPrefix block(s) (shared by {alias_count} alias spec(s))"
    else:
        out, preset_count = apply_per_preset(lines, prompt)
        if not preset_count:
            sys.exit("no presets found under modelSpecs")
        summary = f"system prompt set on {preset_count} model spec(s)"

    if no_backup:
        target.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"OK: {summary}")
    else:
        backup = target.with_name(f"{target.name}.before-prompt-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copy2(target, backup)
        target.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"OK: {summary}; backup at {backup.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
