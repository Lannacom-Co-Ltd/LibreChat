"""Diagrams (flowchart, org chart, timeline, mind map) drawn with Graphviz in the CMUBS look.

Labels are table rows rather than Graphviz line breaks, because Graphviz spaces lines by the
font size alone and Thai upper vowels and tone marks would touch the line above. Long labels
are wrapped at spaces, and nodes that no edge reaches are reported.
"""

import subprocess
import textwrap
from html import escape
from typing import Literal

from pydantic import BaseModel, Field

DiagramType = Literal["flowchart", "org_chart", "timeline", "mind_map"]
LIMIT = 150
WRAP_AT = 22


class DiagramNode(BaseModel):
    id: str = Field(description="Short unique id used by edges")
    label: str = Field(description="Text in the box; keep it short, use \\n for a line break")
    kind: Literal["process", "start", "end", "decision", "data", "note"] = Field(
        default="process",
        description="Flowchart shape: start/end (rounded), process (box), decision (diamond), "
        "data (parallelogram), note. Ignored outside flowcharts.",
    )


class DiagramEdge(BaseModel):
    source: str = Field(description="id of the node the arrow starts from")
    target: str = Field(description="id of the node the arrow points to")
    label: str = Field(default="", description="Optional text on the arrow, e.g. ใช่ / ไม่ใช่")


class TimelineEvent(BaseModel):
    date: str = Field(description="When, e.g. ต.ค. 2569 or Q1")
    label: str = Field(description="What happens; keep it short, use \\n for a line break")


FLOW_SHAPES = {
    "process": 'shape=box, style="rounded,filled", fillcolor="#e6f0f2"',
    "start": 'shape=box, style="rounded,filled", fillcolor="#145e6e", fontcolor="white", penwidth=0',
    "end": 'shape=box, style="rounded,filled", fillcolor="#145e6e", fontcolor="white", penwidth=0',
    "decision": 'shape=diamond, style=filled, fillcolor="#ffffff"',
    "data": 'shape=parallelogram, style=filled, fillcolor="#f3ecf7", color="#8a4fa3"',
    "note": 'shape=note, style=filled, fillcolor="#fff8e1", color="#b58b00"',
}
DARK_BOX = 'shape=box, style="rounded,filled", fillcolor="#145e6e", fontcolor="white", penwidth=0'
LIGHT_BOX = 'shape=box, style="rounded,filled", fillcolor="#e6f0f2"'


def _plain(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _lines(text: str) -> list[str]:
    out = []
    for line in text.replace("\\n", "\n").split("\n"):
        out += textwrap.wrap(line, WRAP_AT, break_long_words=False) or [line]
    return out


def _label(text: str, first_bold: str = "") -> str:
    rows = [f"<B>{escape(first_bold)}</B>"] if first_bold else []
    rows += [escape(line) for line in _lines(text)]
    cells = "".join(f"<TR><TD>{row}</TD></TR>" for row in rows)
    return f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2">{cells}</TABLE>>'


def draw_diagram(diagram_type: DiagramType, nodes, edges, events, title, direction):
    """Returns (png bytes, notes for the model)."""
    nodes, edges, events = nodes or [], edges or [], events or []
    notes = []
    if diagram_type == "timeline":
        if not events:
            raise ValueError("a timeline needs events (date and label for each)")
        if len(events) > LIMIT:
            raise ValueError(f"at most {LIMIT} events")
    else:
        if not nodes:
            raise ValueError(f"a {diagram_type} needs nodes")
        if len(nodes) + len(edges) > LIMIT:
            raise ValueError(f"at most {LIMIT} nodes and edges together")
        seen = set()
        for node in nodes:
            if node.id in seen:
                raise ValueError(f"node id '{node.id}' is used twice; ids must be unique")
            seen.add(node.id)
    ids = {node.id: f"n{i}" for i, node in enumerate(nodes)}
    for edge in edges:
        for end in (edge.source, edge.target):
            if end not in ids:
                raise ValueError(
                    f"edge {edge.source} -> {edge.target} refers to unknown node id '{end}'; "
                    f"known ids: {', '.join(ids)}"
                )
    if diagram_type != "timeline" and len(nodes) > 1:
        linked = {e.source for e in edges} | {e.target for e in edges}
        loose = [n.label for n in nodes if n.id not in linked]
        if loose:
            notes.append(f"not connected to anything: {', '.join(loose)}")

    graph = [
        'fontname="Sarabun"; fontsize=18; fontcolor="#145e6e"; labelloc=t; pad=0.3; dpi=150; bgcolor="white";',
        f'label="{_plain(title)}";' if title else "",
        'node [fontname="Sarabun", fontsize=13, color="#145e6e", penwidth=1.4, margin="0.18,0.08"];',
        'edge [fontname="Sarabun", fontsize=11, color="#5f6b6d", fontcolor="#3c4446", arrowsize=0.8];',
    ]
    engine = "dot"
    if diagram_type == "timeline":
        vertical = direction == "top_down" or (direction == "auto" and len(events) > 6)
        graph.append(f"rankdir={'TB' if vertical else 'LR'}; nodesep=0.35; ranksep=0.45;")
        graph += [f"e{i} [label={_label(e.label, e.date)}, {LIGHT_BOX}];" for i, e in enumerate(events)]
        graph.append(" -> ".join(f"e{i}" for i in range(len(events))) + ' [color="#145e6e", penwidth=2];')
    elif diagram_type == "mind_map":
        engine = "twopi"
        graph.append(f"root={ids[nodes[0].id]}; overlap=false; splines=true; ranksep=1.6;")
        for i, node in enumerate(nodes):
            style = f"{DARK_BOX}, fontsize=16" if i == 0 else LIGHT_BOX
            graph.append(f"{ids[node.id]} [label={_label(node.label)}, {style}];")
        graph += [f"{ids[e.source]} -> {ids[e.target]} [arrowhead=none];" for e in edges]
    else:
        graph.append(f"rankdir={'LR' if direction == 'left_right' else 'TB'}; nodesep=0.4; ranksep=0.5;")
        if diagram_type == "org_chart":
            graph.insert(0, "splines=ortho;")
        targets = {e.target for e in edges}
        for node in nodes:
            if diagram_type == "flowchart":
                shape = FLOW_SHAPES[node.kind]
            else:
                shape = LIGHT_BOX if node.id in targets else DARK_BOX
            graph.append(f"{ids[node.id]} [label={_label(node.label)}, {shape}];")
        for edge in edges:
            attrs = []
            if edge.label:
                attrs.append(f'label=" {_plain(edge.label)} "')
            elif diagram_type == "org_chart":
                attrs.append("arrowhead=none")
            suffix = f" [{', '.join(attrs)}]" if attrs else ""
            graph.append(f"{ids[edge.source]} -> {ids[edge.target]}{suffix};")

    source = "digraph G {\n" + "\n".join(line for line in graph if line) + "\n}\n"
    result = subprocess.run(
        [engine, "-Tpng:cairo"], input=source.encode("utf-8"), capture_output=True, timeout=30
    )
    if result.returncode != 0 or not result.stdout:
        raise ValueError(f"the diagram could not be drawn: {result.stderr.decode(errors='replace')[:300]}")
    return result.stdout, notes
