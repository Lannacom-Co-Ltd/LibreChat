"""Puts assistant/system-prompt.md into every model spec of librechat.yaml as its promptPrefix.

LibreChat turns a spec's promptPrefix into the instructions of the chat's agent, so every new
chat with a listed model starts from the CMUBS system prompt. Running it again replaces the
previous prompt; nothing else in the file changes. A copy of the file is kept first.

  python3 assistant/apply-system-prompt.py librechat.yaml
"""

import shutil
import sys
import time
from pathlib import Path

PRESET = "      preset:"
KEY = "        promptPrefix: |"
BODY = "          "


def main(path: str) -> None:
    target = Path(path)
    prompt = (Path(__file__).parent / "system-prompt.md").read_text(encoding="utf-8").strip()
    block = [KEY] + [f"{BODY}{line}" if line.strip() else "" for line in prompt.splitlines()]

    out, in_specs, skipping, count = [], False, False, 0
    for line in target.read_text(encoding="utf-8").splitlines():
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
    if not count:
        sys.exit("no presets found under modelSpecs")

    backup = target.with_name(f"{target.name}.before-prompt-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(target, backup)
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"OK: system prompt set on {count} model spec(s); backup at {backup.name}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "librechat.yaml")
