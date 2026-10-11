"""Figures of a run (sheet *Charts*) — matplotlib, drawn on axes the caller provides.

Every ``draw_*`` function draws on a given :class:`~matplotlib.axes.Axes`, so the GUI embeds the
same drawings as the exports (ADR-012); ``figure(key, …)`` builds a stand-alone
:class:`~matplotlib.figure.Figure` without pyplot's global state.

Colour follows the class (categorical slots in fixed order, validated for colour-vision
deficiency); the class is also told by the marker shape, and the sample by the fill — filled =
training sample D, hollow = validation sample F — so no meaning rests on colour alone.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import numpy as np
from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from erdr.core.readings import Readings
from erdr.export.text import display
from erdr.notation import class_name
from erdr.services.analysis import ReadingRow, SweepRow
from erdr.services.experiment import ExperimentResult

SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
"""Categorical slots in their fixed order (blue, orange, aqua, yellow, magenta, green, violet,
red); classes and series take them in order, never cycled."""
MARKERS = ("o", "^", "s", "D", "v", "P", "X", "*")
"""Marker shape per class — the second channel of the class identity."""
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
LABEL_LIMIT = 40
"""Objects are labelled on the map and the per-object charts up to this many objects."""


def _style(ax: Axes, title: str, *, grid_axis: Literal["x", "y", ""] = "y") -> None:
    """Recessive chrome: hairline grid, muted ticks, no top/right spines."""
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK_SECONDARY, labelsize=8)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _colour(class_index: int) -> str:
    return SERIES[class_index % len(SERIES)]


def _marker(class_index: int) -> str:
    return MARKERS[class_index % len(MARKERS)]


def classical_mds(matrix: np.ndarray, dimensions: int = 2) -> np.ndarray:
    """Classical multidimensional scaling of a distance matrix (positions are approximate).

    B = −½·J·ρ²·J; the coordinates are the leading eigenvectors scaled by √λ. Signs are fixed so
    that every axis has its largest component positive, which makes the map reproducible.
    """
    m = matrix.shape[0]
    if m < 2:
        return np.zeros((m, dimensions))
    centring = np.eye(m) - np.full((m, m), 1.0 / m)
    gram = -0.5 * centring @ np.square(matrix) @ centring
    values, vectors = np.linalg.eigh(gram)
    order = np.argsort(values)[::-1][:dimensions]
    coords = vectors[:, order] * np.sqrt(np.clip(values[order], 0.0, None))
    for axis in range(coords.shape[1]):
        column = coords[:, axis]
        if column[np.argmax(np.abs(column))] < 0:
            coords[:, axis] = -column
    if coords.shape[1] < dimensions:
        coords = np.hstack([coords, np.zeros((m, dimensions - coords.shape[1]))])
    return coords


def _class_legend(ax: Axes, run: ExperimentResult, *, samples: bool) -> None:
    handles: list[Line2D] = []
    for index, label in enumerate(run.dataset.classes):
        handles.append(
            Line2D(
                [],
                [],
                linestyle="",
                marker=_marker(index),
                markersize=8,
                markerfacecolor=_colour(index),
                markeredgecolor=_colour(index),
                label=f"{class_name(index)} (class {label})",
            )
        )
    if samples:
        handles.append(
            Line2D(
                [],
                [],
                linestyle="",
                marker="o",
                markersize=8,
                markerfacecolor=MUTED,
                markeredgecolor=MUTED,
                label="filled: training D",
            )
        )
        handles.append(
            Line2D(
                [],
                [],
                linestyle="",
                marker="o",
                markersize=8,
                markerfacecolor="white",
                markeredgecolor=MUTED,
                label="hollow: validation F",
            )
        )
    ax.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK_SECONDARY, loc="best")


def draw_map(ax: Axes, run: ExperimentResult) -> None:
    """2-D map of the objects: classical MDS of ρ; colour + shape = class, fill = sample."""
    coords = classical_mds(run.distances.matrix)
    classes = run.result.characteristics.classes
    training = run.result.training_mask
    names = run.object_names
    _style(ax, "Objects on a 2-D map (classical MDS of ρ)", grid_axis="")
    for index in range(len(run.dataset.classes)):
        for in_d in (True, False):
            chosen = (classes == index) & (training == in_d)
            if not chosen.any():
                continue
            ax.scatter(
                coords[chosen, 0],
                coords[chosen, 1],
                s=70,
                marker=_marker(index),
                facecolors=_colour(index) if in_d else "white",
                edgecolors=_colour(index),
                linewidths=1.6,
                zorder=3,
            )
    if len(names) <= LABEL_LIMIT:
        for i, name in enumerate(names):
            ax.annotate(
                name,
                coords[i],
                textcoords="offset points",
                xytext=(6, 5),
                fontsize=8,
                color=INK_SECONDARY,
            )
    ax.set_xticks([])
    ax.set_yticks([])
    _class_legend(ax, run, samples=True)


def draw_radii(ax: Axes, run: ExperimentResult) -> None:
    """r(Sᵢ) (enemy radius) and z(Sᵢ, k) (k-th neighbour) of every object."""
    c = run.result.characteristics
    x = np.arange(c.m)
    _style(ax, f"Enemy radius r and k-th neighbour distance z (k = {c.k})")
    ax.vlines(x, np.minimum(c.r, c.z), np.maximum(c.r, c.z), color=AXIS, linewidth=2, zorder=2)
    ax.scatter(x, c.r, s=64, marker="o", color=SERIES[0], zorder=3, label="r(Sᵢ) — nearest enemy")
    ax.scatter(
        x,
        c.z,
        s=64,
        marker="D",
        facecolors="white",
        edgecolors=SERIES[1],
        linewidths=1.8,
        zorder=3,
        label=f"z(Sᵢ, {c.k}) — k-th neighbour",
    )
    if c.m <= LABEL_LIMIT:
        ax.set_xticks(x, run.object_names)
    ax.set_ylabel("distance ρ")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_SECONDARY)


def draw_priorities(ax: Axes, run: ExperimentResult) -> None:
    """d(Sᵢ) in the Step 2 order (first in the queue at the top), coloured by class."""
    c = run.result.characteristics
    order = c.priority
    y = np.arange(c.m)
    _style(ax, "Step 2 · priority d(Sᵢ) in queue order", grid_axis="x")
    ax.barh(
        y,
        c.d[order],
        height=0.62,
        color=[_colour(int(c.classes[i])) for i in order],
        edgecolor=SURFACE,
        linewidth=2,
    )
    for index in range(len(run.dataset.classes)):  # the class marker also shows a bar of d = 0
        places = np.flatnonzero(c.classes[order] == index)
        ax.scatter(
            c.d[order][places],
            places,
            s=40,
            marker=_marker(index),
            color=_colour(index),
            edgecolors=SURFACE,
            linewidths=1.2,
            zorder=3,
        )
    if c.m <= LABEL_LIMIT:
        ax.set_yticks(y, [run.object_names[i] for i in order])
        for place, i in enumerate(order):
            ax.annotate(
                display(float(c.d[i]), 4),
                (c.d[i], place),
                textcoords="offset points",
                xytext=(4, -3),
                fontsize=7,
                color=INK_SECONDARY,
            )
    ax.invert_yaxis()
    ax.set_xlabel("d = |z − r| / (z + r)")
    _class_legend(ax, run, samples=False)


def draw_sizes(ax: Axes, run: ExperimentResult) -> None:
    """|F|, |D| and the queue length after every iteration (0 = start)."""
    result = run.result
    t = np.arange(len(result.iterations) + 1)
    f_sizes = [result.m] + [it.f_size for it in result.iterations]
    d_sizes = [0] + [it.d_size for it in result.iterations]
    queue = [result.m] + [it.queue_left for it in result.iterations]
    _style(ax, "Sample sizes through the iterations")
    for values, label, colour, marker in (
        (f_sizes, "|F| working set", SERIES[0], "o"),
        (d_sizes, "|D| training sample", SERIES[1], "^"),
        (queue, "objects left in the queue", SERIES[2], "s"),
    ):
        ax.step(t, values, where="post", color=colour, linewidth=2, label=label)
        ax.plot(t, values, linestyle="", marker=marker, color=colour, markersize=6)
    ax.set_xlabel("iteration t")
    ax.set_ylabel("objects")
    ax.margins(y=0.06)  # keeps the markers on 0 visible
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_SECONDARY)


def draw_composition(ax: Axes, run: ExperimentResult) -> None:
    """Objects of every class in D and in F."""
    result = run.result
    classes = len(run.dataset.classes)
    width = 0.8 / classes
    samples = ("D · training", "F · validation")
    _style(ax, "Class composition of D and F")
    for index in range(classes):
        counts = [
            run.class_counts(result.training)[index],
            run.class_counts(result.validation)[index],
        ]
        positions = np.arange(2) + (index - (classes - 1) / 2) * width
        bars = ax.bar(
            positions,
            counts,
            width=width,
            color=_colour(index),
            edgecolor=SURFACE,
            linewidth=2,
            label=f"{class_name(index)} (class {run.dataset.classes[index]})",
        )
        ax.bar_label(bars, fontsize=8, color=INK_SECONDARY, padding=2)
    ax.set_xticks(np.arange(2), samples)
    ax.set_ylabel("objects")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_SECONDARY)


def draw_sweep(ax: Axes, rows: Sequence[SweepRow], m: int) -> None:
    """|D| against k for every reading of a sweep."""
    _style(ax, f"Training-sample size |D| by k (m = {m})")
    readings: list[Readings] = []
    for row in rows:
        if row.readings not in readings:
            readings.append(row.readings)
    for index, reading in enumerate(readings):
        chosen = [row for row in rows if row.readings == reading]
        ks = [row.k for row in chosen]
        sizes = [row.training_size for row in chosen]
        ax.plot(
            ks,
            sizes,
            color=_colour(index),
            linewidth=2,
            marker=_marker(index),
            markersize=6,
            label=reading.label,
        )
        if ks:
            ax.annotate(
                str(sizes[-1]),
                (ks[-1], sizes[-1]),
                textcoords="offset points",
                xytext=(5, 0),
                fontsize=8,
                color=INK_SECONDARY,
            )
    ax.set_xlabel("k")
    ax.set_ylabel("|D|")
    ax.set_ylim(0, m)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_SECONDARY)


def draw_readings(ax: Axes, rows: Sequence[ReadingRow], m: int) -> None:
    """|D| for every reading of a comparison (the literal reading first)."""
    usable = [row for row in rows if row.error is None]
    labels = [row.readings.label for row in usable]
    sizes = [len(row.training) for row in usable]
    y = np.arange(len(usable))
    _style(ax, f"Training-sample size |D| per reading (m = {m})", grid_axis="x")
    colours = [SERIES[0] if row.readings.is_literal else MUTED for row in usable]
    bars = ax.barh(y, sizes, height=0.62, color=colours, edgecolor=SURFACE, linewidth=2)
    ax.bar_label(bars, fontsize=8, color=INK_SECONDARY, padding=3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, m)
    ax.set_xlabel("|D|  (blue: the literal article reading)")


RUN_FIGURES: dict[str, tuple[str, Callable[[Axes, ExperimentResult], None]]] = {
    "map": ("2-D map", draw_map),
    "radii": ("r and z per object", draw_radii),
    "priorities": ("Step 2 priorities", draw_priorities),
    "sizes": ("Sample sizes", draw_sizes),
    "composition": ("Class composition", draw_composition),
}
"""The figures of one run: key → (name, draw function)."""


def new_figure(width: float = 7.0, height: float = 4.2) -> Figure:
    """An empty figure on the chart surface (no pyplot global state)."""
    return Figure(figsize=(width, height), facecolor=SURFACE, layout="constrained")


def run_figure(key: str, run: ExperimentResult) -> Figure:
    """One figure of a run (see :data:`RUN_FIGURES`).

    Raises:
        KeyError: Unknown figure key.
    """
    _, draw = RUN_FIGURES[key]
    m = run.result.m
    height = max(4.2, min(0.28 * m + 1.5, 12.0)) if key == "priorities" else 4.6
    figure = new_figure(7.0 if key != "map" else 6.4, height)
    draw(figure.add_subplot(), run)
    return figure


def sweep_figure(rows: Sequence[SweepRow], m: int) -> Figure:
    """The figure of a k sweep."""
    figure = new_figure()
    draw_sweep(figure.add_subplot(), rows, m)
    return figure


def readings_figure(rows: Sequence[ReadingRow], m: int) -> Figure:
    """The figure of a readings comparison."""
    figure = new_figure(7.0, 0.42 * len(rows) + 1.6)
    draw_readings(figure.add_subplot(), rows, m)
    return figure


def save_figure(figure: Figure, path: Path, *, dpi: int = 150) -> Path:
    """Save as PNG or SVG (by the file extension); SVG keeps text as text and no timestamp."""
    path.parent.mkdir(parents=True, exist_ok=True)
    svg = path.suffix.lower() == ".svg"
    with rc_context({"svg.fonttype": "none", "svg.hashsalt": "erdr"}):
        figure.savefig(path, dpi=dpi, facecolor=SURFACE, metadata={"Date": None} if svg else None)
    return path


def svg_text(figure: Figure) -> str:
    """The figure as inline SVG markup (for the HTML report)."""
    buffer = io.StringIO()
    with rc_context({"svg.fonttype": "none", "svg.hashsalt": "erdr"}):
        figure.savefig(buffer, format="svg", facecolor=SURFACE, metadata={"Date": None})
    text = buffer.getvalue()
    return text[text.find("<svg") :]
