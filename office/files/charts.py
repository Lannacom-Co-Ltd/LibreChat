"""Charts in the AI Hub colours (orange, green, ink), checked for unreadable labels before they are saved.

After drawing, the label boxes are measured. Overlapping category labels are wrapped at spaces,
then tilted, and a bar chart still crowded becomes a horizontal bar chart, where labels have
the full left margin. A pie with many or long labels moves them into a legend. Every change is
reported, so the model knows what the user will see.

Figures are built without pyplot: tools run in a thread pool, and pyplot keeps one global
current figure that concurrent calls would draw over each other.
"""

import io
import textwrap
from typing import Literal

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from pydantic import BaseModel, Field

INK = "#1f1e1d"
COLORS = ["#f05023", "#1ab06c", "#3b6fd9", "#f2a33a", "#7a5cfa", "#6b6a65", "#c23a2b", "#0f8a72"]
matplotlib.rcParams.update(
    {
        "font.family": "Sarabun",
        "axes.prop_cycle": matplotlib.cycler(color=COLORS),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "axes.titlesize": 14,
        "axes.titlecolor": INK,
    }
)

ChartType = Literal["bar", "horizontal_bar", "line", "pie"]
WRAP_AT = 16
WRAP_AT_SIDE = 28
PIE_LEGEND_LABEL = 14
PIE_LEGEND_SLICES = 6


class Series(BaseModel):
    name: str = Field(description="Series name shown in the legend")
    values: list[float] = Field(description="One value per label")


def _wrap(label: str, width: int = WRAP_AT) -> str:
    """Wraps at spaces only; Thai words have no spaces between them and must not be cut."""
    return "\n".join(textwrap.wrap(label, width, break_long_words=False)) or label


def _overlaps(fig, labels) -> bool:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    boxes = [t.get_window_extent(renderer) for t in labels if t.get_text()]
    return any(a.overlaps(b) for a, b in zip(boxes, boxes[1:]))


def _draw(chart_type: ChartType, labels, series, title, x_label, y_label, tilt=0, legend_pie=False):
    fig = Figure(figsize=(8, 4.5), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    if chart_type == "pie":
        values = series[0].values
        total = sum(values) or 1
        colors = (COLORS * (len(labels) // len(COLORS) + 1))[: len(labels)]
        wedges, texts, percents = ax.pie(
            values,
            labels=None if legend_pie else labels,
            autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
            startangle=90,
            colors=colors,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        for text in percents:
            text.set(color="white", fontweight="bold")
        if legend_pie:
            ax.legend(
                wedges,
                [f"{lab} ({v / total:.0%})" for lab, v in zip(labels, values)],
                loc="center left",
                bbox_to_anchor=(1, 0.5),
                frameon=False,
            )
        ax.axis("equal")
    elif chart_type == "line":
        for item in series:
            ax.plot(labels, item.values, marker="o", linewidth=2.2, label=item.name)
    else:
        width = 0.8 / len(series)
        positions = list(range(len(labels)))
        draw = ax.barh if chart_type == "horizontal_bar" else ax.bar
        for i, item in enumerate(series):
            draw([p - 0.4 + width * (i + 0.5) for p in positions], item.values, width, label=item.name)
        if chart_type == "horizontal_bar":
            ax.set_yticks(positions, labels)
            ax.invert_yaxis()
        else:
            ax.set_xticks(positions, labels)
    if chart_type != "pie":
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(axis="x" if chart_type == "horizontal_bar" else "y", alpha=0.3)
        if len(series) > 1:
            ax.legend(frameon=False)
        if tilt:
            for tick in ax.get_xticklabels():
                tick.set(rotation=tilt, ha="right", rotation_mode="anchor")
    if title:
        ax.set_title(_wrap(title, 60), pad=12)
    return fig, ax


def draw_chart(chart_type: ChartType, labels, series, title="", x_label="", y_label=""):
    """Returns (png bytes, notes on what was changed to keep it readable)."""
    if not labels or not series:
        raise ValueError("labels and series must not be empty")
    for item in series:
        if len(item.values) != len(labels):
            raise ValueError(
                f"series '{item.name}' has {len(item.values)} values for {len(labels)} labels"
            )
    if chart_type == "pie" and any(v < 0 for v in series[0].values):
        raise ValueError("a pie chart cannot show negative values; use a bar chart")

    notes = []
    wrapped = [_wrap(label) for label in labels]
    side = [_wrap(label, WRAP_AT_SIDE) for label in labels]
    if chart_type == "pie":
        legend = len(labels) > PIE_LEGEND_SLICES or max(len(s) for s in labels) > PIE_LEGEND_LABEL
        fig, _ = _draw(chart_type, labels, series, title, x_label, y_label, legend_pie=legend)
        if legend:
            notes.append("pie labels were long or many, so they are shown in a legend")
    else:
        # x_label names the categories, which a horizontal chart puts on the y axis.
        axes = (y_label, x_label) if chart_type == "horizontal_bar" else (x_label, y_label)
        fig, ax = _draw(chart_type, side if chart_type == "horizontal_bar" else wrapped, series, title, *axes)
        if chart_type == "bar" and _overlaps(fig, ax.get_xticklabels()):
            fig, ax = _draw("horizontal_bar", side, series, title, y_label, x_label)
            notes.append(
                "category labels were too long for vertical bars, so the chart is drawn as horizontal bars"
            )
        elif chart_type == "line" and _overlaps(fig, ax.get_xticklabels()):
            fig, ax = _draw(chart_type, wrapped, series, title, x_label, y_label, tilt=30)
            if _overlaps(fig, ax.get_xticklabels()):
                notes.append("x labels still crowd each other even tilted; shorten them or use fewer points")
            else:
                notes.append("x labels were tilted so they do not overlap")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    return buf.getvalue(), notes
