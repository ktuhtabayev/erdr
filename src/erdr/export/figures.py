"""Figures of a run (sheets *Charts* and *Hyperspheres*) — matplotlib, drawn on given axes.

Every ``draw_*`` function draws on a given :class:`~matplotlib.axes.Axes`, so the GUI embeds the
same drawings as the exports (ADR-012); ``figure(key, …)`` builds a stand-alone
:class:`~matplotlib.figure.Figure` without pyplot's global state.

The hypersphere figures show Steps 1–5 geometrically (ADR-020): the enemy sphere (solid) and the
k-sphere (dashed) of an object, every object's neighbours on a strip, the radius plane (r, z) on
which d is constant along lines through the origin, and in every iteration the enemy spheres of
the own-class objects around the selected Sᵢ — the spheres that contain Sᵢ give L. A sphere's
line is in its owner's class colour; its state is told by the line and the fill: a sphere in L
is solid with the yellow of L, one in F but not in L dashed, one of an object already in D dotted.

The colours are :mod:`erdr.export.theme`'s, so a figure and a table say the same: in every figure
of a run the colour is the class (K1 blue, K2 orange, … — categorical slots in fixed order,
validated for colour-vision deficiency, never cycled); the class is also told by the marker
shape, and the sample by the fill — filled = training sample D, hollow = validation sample F — so
no meaning rests on colour alone. The sample sizes are drawn in the colours of D (aqua) and F
(violet); the readings keep one colour each (the literal reading green, the closest blue).
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

import numpy as np
from matplotlib import rc_context
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch

from erdr.core.hyperspheres import (
    RATIO_LINES,
    coinciding_points,
    object_title,
    radial_layout,
    ratio_line,
    ray_length,
    strip_levels,
)
from erdr.core.readings import CLOSEST, LITERAL, Readings
from erdr.export.tables import HYPERSPHERES_ITERATIONS, HYPERSPHERES_STEP1, iteration_view
from erdr.export.text import display
from erdr.export.theme import (
    AXIS,
    D_ACCENT,
    F_ACCENT,
    GRID,
    INK,
    INK_SECONDARY,
    MUTED,
    READING_COLOURS,
    STATES,
    SURFACE,
    class_colour,
    class_mark,
    swatch,
)
from erdr.notation import class_name, object_set
from erdr.services.analysis import ReadingRow, SweepRow
from erdr.services.experiment import ExperimentResult

_HIGHLIGHT_KEYS = (("green", "literal article", LITERAL), ("blue", "closest", CLOSEST))
"""How the readings figure names its two highlighted readings."""
MARKERS = ("o", "^", "s", "D", "v", "P", "X", "*")
"""Marker shape per class — the second channel of the class identity."""
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
    return class_colour(class_index)


def reading_colour(readings: Readings, others: Sequence[Readings] = ()) -> str:
    """The colour of a reading in every figure: literal green, closest blue, then ``others``.

    ``others`` lists the further readings of the figure in their order; a reading keeps its
    colour whichever readings are shown with it, and readings past the palette are grey.
    """
    if readings == LITERAL:
        return READING_COLOURS[0]
    if readings == CLOSEST:
        return READING_COLOURS[1]
    rest = [r for r in others if r not in (LITERAL, CLOSEST)]
    place = rest.index(readings) + 2 if readings in rest else len(READING_COLOURS)
    return READING_COLOURS[place] if place < len(READING_COLOURS) else MUTED


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
    """r(Sᵢ) (enemy radius, filled ●) and z(Sᵢ, k) (k-th neighbour, hollow ◇), by class colour."""
    c = run.result.characteristics
    x = np.arange(c.m)
    colours = [_colour(int(i)) for i in c.classes]
    _style(ax, f"Enemy radius r and k-th neighbour distance z (k = {c.k})")
    ax.vlines(x, np.minimum(c.r, c.z), np.maximum(c.r, c.z), color=AXIS, linewidth=2, zorder=2)
    ax.scatter(x, c.r, s=64, marker="o", color=colours, edgecolors=SURFACE, zorder=3)
    ax.scatter(
        x, c.z, s=64, marker="D", facecolors="white", edgecolors=colours, linewidths=1.8, zorder=3
    )
    if c.m <= LABEL_LIMIT:
        ax.set_xticks(x, run.object_names)
    ax.set_ylabel("distance ρ")
    ax.set_ylim(bottom=0)
    handles = [
        Line2D([], [], linestyle="", marker="o", markersize=8, color=MUTED, label="r(Sᵢ) — enemy"),
        Line2D(
            [],
            [],
            linestyle="",
            marker="D",
            markersize=7,
            markerfacecolor="white",
            markeredgecolor=MUTED,
            label=f"z(Sᵢ, {c.k}) — k-th neighbour",
        ),
        *(
            Line2D(
                [],
                [],
                linestyle="",
                marker="s",
                markersize=8,
                color=_colour(index),
                label=f"{class_name(index)} (class {label})",
            )
            for index, label in enumerate(run.dataset.classes)
        ),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK_SECONDARY)


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
    for values, label, short, colour, marker, style in (
        (f_sizes, "|F| validation sample (working set)", "F", F_ACCENT, "o", "-"),
        (d_sizes, "|D| training sample", "D", D_ACCENT, "^", "-"),
        (queue, "objects left in the queue", "queue", MUTED, "s", "--"),
    ):
        ax.step(t, values, where="post", color=colour, linewidth=2, linestyle=style, label=label)
        ax.plot(t, values, linestyle="", marker=marker, color=colour, markersize=6)
        ax.annotate(  # the direct label: which line, and where it ends
            f"{short} {values[-1]}",
            (t[-1], values[-1]),
            textcoords="offset points",
            xytext=(6, 0),
            va="center",
            fontsize=8,
            color=INK_SECONDARY,
        )
    ax.set_xlabel("iteration t")
    ax.set_ylabel("objects")
    ax.margins(x=0.1, y=0.06)  # keeps the markers on 0 and the end labels visible
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
            color=reading_colour(reading, readings),
            linewidth=2,
            marker=_marker(index),
            markersize=6,
            label=reading.label + ("  (literal)" if reading.is_literal else ""),
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
    highlighted = (LITERAL, CLOSEST)
    colours = [
        reading_colour(row.readings) if row.readings in highlighted else MUTED for row in usable
    ]
    bars = ax.barh(y, sizes, height=0.62, color=colours, edgecolor=SURFACE, linewidth=2)
    ax.bar_label(bars, fontsize=8, color=INK_SECONDARY, padding=3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, m)
    shown = {row.readings for row in usable}
    keys = [f"{hue}: the {name} reading" for hue, name, r in _HIGHLIGHT_KEYS if r in shown]
    ax.set_xlabel("|D|" + (f"  ({' · '.join(keys)})" if keys else ""))


# ---------------------------------------------------------------- hyperspheres (ADR-020)

PANEL_LIMIT = 12
"""The multi-panel sphere figures show at most this many objects or iterations."""
PANEL_LABELS = 12
"""Objects are labelled in a panel up to this many objects."""
CROWDED = 36
"""Above this many objects the diagrams leave out their spokes, use small markers, and an
iteration diagram draws only the spheres that contain Sᵢ."""
_K_SPHERE = (0, (4, 3))
"""Dash pattern of the k-sphere, and of a sphere in F that is not in L."""
_IN_D = (0, (1, 2))
"""Dot pattern of the sphere of an object already in D."""


def _tint(class_index: int) -> str:
    """The light tint of a class (its table cells' fill)."""
    found = swatch(class_mark(class_index))
    return found.fill if found is not None else GRID


def _points(
    ax: Axes,
    x: np.ndarray,
    y: np.ndarray,
    classes: np.ndarray,
    filled: np.ndarray,
    *,
    size: float = 64.0,
    zorder: int = 4,
    rasterized: bool = False,
) -> None:
    """Objects in their class colour and shape; filled where ``filled``, hollow elsewhere.

    ``rasterized`` keeps the SVG of a large sample small: the markers become one image.
    """
    for index in np.unique(classes).tolist():
        for full in (True, False):
            chosen = (classes == index) & (filled == full)
            if not chosen.any():
                continue
            ax.scatter(
                x[chosen],
                y[chosen],
                s=size,
                marker=_marker(int(index)),
                facecolors=_colour(int(index)) if full else "white",
                edgecolors=_colour(int(index)),
                linewidths=1.6 if size >= 30 else 0.8,
                zorder=zorder,
                rasterized=rasterized,
            )


def _centre(ax: Axes, x: float, y: float, class_index: int, *, size: float = 150.0) -> None:
    """The centre of a diagram: a large filled marker with a dark ring."""
    ax.scatter(
        [x],
        [y],
        s=size,
        marker=_marker(class_index),
        facecolors=_colour(class_index),
        edgecolors=INK,
        linewidths=1.8,
        zorder=6,
    )


def _square(ax: Axes, half: float, *, x0: float = 0.0, y0: float = 0.0) -> None:
    """Equal scales on both axes, a square window of half side ``half``, no ticks."""
    ax.set_xlim(x0 - half, x0 + half)
    ax.set_ylim(y0 - half, y0 + half)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def _class_handles(run: ExperimentResult) -> list[Line2D]:
    return [
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
        for index, label in enumerate(run.dataset.classes)
    ]


def _hollow(label: str, marker: str = "o") -> Line2D:
    return Line2D(
        [],
        [],
        linestyle="",
        marker=marker,
        markersize=8,
        markerfacecolor="white",
        markeredgecolor=MUTED,
        label=label,
    )


def _filled(label: str, marker: str = "o") -> Line2D:
    return Line2D([], [], linestyle="", marker=marker, markersize=8, color=MUTED, label=label)


def _object_sphere_handles(run: ExperimentResult) -> list[Line2D | Patch]:
    k = run.result.characteristics.k
    return [
        Line2D([], [], color=MUTED, linewidth=2.0, label="enemy sphere r(Sᵢ) — open"),
        Line2D(
            [], [], color=MUTED, linewidth=1.6, linestyle=_K_SPHERE, label=f"k-sphere z(Sᵢ, {k})"
        ),
        _filled("own class inside — counted in g"),
        _hollow("not counted in g"),
        *_class_handles(run),
    ]


def _scale(run: ExperimentResult) -> float:
    """ρ_max: one scale for the diagrams of every object (radius 1 = the largest distance)."""
    largest = float(run.distances.matrix.max()) if run.result.m else 1.0
    return largest if largest > 0.0 else 1.0


def draw_object_spheres(
    ax: Axes, run: ExperimentResult, i: int, *, compact: bool = False, legend: bool = True
) -> None:
    """The two spheres of Sᵢ with every other object at its true distance (Step 1).

    The centre is Sᵢ; the others stand in its neighbour order clockwise from the top. The enemy
    sphere (solid, shaded) passes through the nearest enemy, the k-sphere (dashed) through the
    k-th neighbour; filled markers are the own-class objects inside — g(Sᵢ) counts them and Sᵢ.
    Every object's diagram has the same scale, so diagrams can be compared.
    """
    c = run.result.characteristics
    names = run.object_names
    m = c.m
    layout = radial_layout(run.distances.matrix, c, i)
    x, y = layout.xy()
    own = int(c.classes[i])
    colour = _colour(own)
    label = str(run.dataset.y[i].item())
    title = object_title(names[i], label, int(c.g[i]), float(c.d[i]), int(c.position[i]))
    if compact:  # two short lines: the panel is narrow
        title = (
            f"{names[i]} (class {label})  ·  queue {int(c.position[i])}\n"
            f"g = {int(c.g[i])}  ·  d = {float(c.d[i]):.3f}"
        )
    _style(ax, title, grid_axis="")
    if compact:
        ax.title.set_fontsize(9)
    others = np.arange(m) != i
    if m <= CROWDED:
        for j in np.flatnonzero(others).tolist():
            ax.plot([0.0, x[j]], [0.0, y[j]], color=GRID, linewidth=0.8, zorder=1)
    r, z = float(c.r[i]), float(c.z[i])
    ax.add_patch(Circle((0.0, 0.0), r, facecolor=_tint(own), edgecolor="none", zorder=0))
    ax.add_patch(Circle((0.0, 0.0), r, fill=False, edgecolor=colour, linewidth=2.0, zorder=2))
    ax.add_patch(
        Circle(
            (0.0, 0.0),
            z,
            fill=False,
            edgecolor=colour,
            linewidth=1.6,
            linestyle=_K_SPHERE,
            zorder=3,
        )
    )
    counted = c.spheres[i] & others
    small = m > CROWDED
    _points(
        ax,
        x[others],
        y[others],
        c.classes[others],
        counted[others],
        size=18 if small else 64,
        rasterized=small,
    )
    _centre(ax, 0.0, 0.0, own, size=60 if small else 150)
    limit = PANEL_LABELS if compact else LABEL_LIMIT
    if m <= limit:
        for j in np.flatnonzero(others).tolist():
            tags = [
                tag
                for tag, hit in (("r", j == c.nearest_enemy[i]), ("z", j == c.kth_neighbour[i]))
                if hit
            ]
            text = f"{names[j]}  {layout.distance[j]:.2f}" + (
                f" ({', '.join(tags)})" if tags else ""
            )
            angle = float(layout.angle[j])
            ax.annotate(
                text,
                (x[j], y[j]),
                textcoords="offset points",
                xytext=(7 * math.cos(angle), 7 * math.sin(angle)),
                ha="left"
                if math.cos(angle) > 0.2
                else ("right" if math.cos(angle) < -0.2 else "center"),
                va="bottom"
                if math.sin(angle) > 0.2
                else ("top" if math.sin(angle) < -0.2 else "center"),
                fontsize=7 if compact else 8,
                color=INK_SECONDARY,
                zorder=7,
            )
    ax.text(
        0.01,
        0.01,
        f"r = {r:.3f}  ·  z = {z:.3f}"
        + ("" if compact else f"  ·  d = |z − r| / (z + r) = {float(c.d[i]):.3f}"),
        transform=ax.transAxes,
        fontsize=7 if compact else 8,
        color=INK_SECONDARY,
    )
    _square(ax, _scale(run) * 1.15)
    if legend and not compact:
        ax.legend(
            handles=_object_sphere_handles(run),
            frameon=False,
            fontsize=8,
            labelcolor=INK_SECONDARY,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
        )


def _panel_grid(figure: Figure, count: int) -> tuple[list[Axes], Axes | None]:
    """``count`` panels in rows of four; a spare slot (if any) for the legend."""
    columns = min(4, max(count, 1))
    rows = math.ceil(max(count, 1) / columns)
    axes = figure.subplots(rows, columns, squeeze=False).ravel().tolist()
    spare = axes[count] if count < len(axes) else None
    for extra in axes[count:]:
        extra.set_axis_off()
    return axes[:count], spare


def _panel_legend(figure: Figure, spare: Axes | None, handles: Sequence[Line2D | Patch]) -> None:
    if spare is not None:
        spare.legend(
            handles=handles, frameon=False, fontsize=8, labelcolor=INK_SECONDARY, loc="center"
        )
    else:
        figure.legend(
            handles=handles,
            frameon=False,
            fontsize=8,
            labelcolor=INK_SECONDARY,
            loc="outside lower center",
            ncols=min(len(handles), 4),
        )


def sphere_objects(run: ExperimentResult) -> list[int]:
    """The objects of the multi-panel figure: all (≤ 12), else the first 12 of the queue."""
    c = run.result.characteristics
    if c.m <= PANEL_LIMIT:
        return list(range(c.m))
    return [int(i) for i in c.priority[:PANEL_LIMIT]]


def draw_object_panels(figure: Figure, run: ExperimentResult) -> None:
    """The spheres of every object, one panel each, on one scale (sheet *Hyperspheres (Step 1)*)."""
    chosen = sphere_objects(run)
    panels, spare = _panel_grid(figure, len(chosen))
    for ax, i in zip(panels, chosen, strict=True):
        draw_object_spheres(ax, run, i, compact=True, legend=False)
    m = run.result.m
    which = "" if m <= PANEL_LIMIT else f" — the first {PANEL_LIMIT} of {m} in the Step 2 queue"
    figure.suptitle(
        f"Hyperspheres of every object{which} · one scale: ρ_max = {_scale(run):.2f}",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    _panel_legend(figure, spare, _object_sphere_handles(run))


def draw_strips(ax: Axes, run: ExperimentResult) -> None:
    """Every object's neighbours on one strip, in Step 2 queue order (first at the top).

    x is the distance from the strip owner Sᵢ; the solid tick above the strip is r(Sᵢ), the
    dashed tick below z(Sᵢ, k) — the closer the two ticks, the smaller d and the earlier Sᵢ.
    """
    c = run.result.characteristics
    matrix = run.distances.matrix
    names = run.object_names
    m = c.m
    levels = strip_levels(c)
    reach = float(matrix.max()) if m else 1.0
    small = m > LABEL_LIMIT
    _style(
        ax,
        "Neighbourhood strips in Step 2 queue order — r above, z below every strip",
        grid_axis="",
    )
    ax.hlines(levels, 0.0, reach, color=GRID, linewidth=0.8, zorder=1, rasterized=small)
    colours = [_colour(int(k)) for k in c.classes]
    ax.vlines(c.r, levels, levels + 0.32, colors=colours, linewidth=2.0, zorder=3)
    ax.vlines(
        c.z,
        levels - 0.32,
        levels,
        colors=colours,
        linewidth=1.6,
        linestyle=_K_SPHERE,
        zorder=3,
    )
    pairs = ~np.eye(m, dtype=bool)  # every strip at once: owner i (rows), neighbour j (columns)
    owners, neighbours = np.nonzero(pairs)
    _points(
        ax,
        matrix[owners, neighbours],
        levels[owners].astype(np.float64),
        c.classes[neighbours],
        c.spheres[owners, neighbours],
        size=12 if small else 48,
        rasterized=small,
    )
    for index in np.unique(c.classes).tolist():  # the strip owners at x = 0
        chosen = c.classes == index
        ax.scatter(
            np.zeros(int(chosen.sum())),
            levels[chosen],
            s=24 if small else 90,
            marker=_marker(int(index)),
            facecolors=_colour(int(index)),
            edgecolors=INK,
            linewidths=1.8 if not small else 0.8,
            zorder=6,
            rasterized=small,
        )
    if not small:
        ax.set_yticks(levels, [f"{names[i]}  ·  d {float(c.d[i]):.3f}" for i in range(m)])
    else:
        ax.set_yticks([])
    ax.set_ylim(0.4, m + 0.6)
    ax.set_xlim(-0.03 * reach, reach * 1.03)
    ax.set_xlabel("distance ρ(Sᵢ, Sⱼ) from the strip owner Sᵢ")
    handles: list[Line2D | Patch] = [
        Line2D([], [], color=MUTED, linewidth=2.0, label="r(Sᵢ) — enemy sphere"),
        Line2D(
            [],
            [],
            color=MUTED,
            linewidth=1.6,
            linestyle=_K_SPHERE,
            label=f"z(Sᵢ, {c.k}) — k-sphere",
        ),
        _filled("own class inside — counted in g"),
        _hollow("not counted"),
        *_class_handles(run),
    ]
    ax.legend(
        handles=handles,
        frameon=False,
        fontsize=8,
        labelcolor=INK_SECONDARY,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
    )


def _place_labels(
    ax: Axes,
    items: Sequence[tuple[float, float, str]],
    points: Sequence[tuple[float, float]],
    *,
    fontsize: float = 8.0,
) -> None:
    """Label points; each label takes the first of four places that covers no point or label.

    The axes' limits must be set: the places are judged in display units at the current size.
    """
    box = ax.get_window_extent()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    scale = min(box.width / (x1 - x0), box.height / (y1 - y0))  # equal aspect: one scale
    unit = ax.figure.dpi / 72.0
    marks = [(x * scale, y * scale) for x, y in points]
    taken: list[tuple[float, float, float, float]] = []
    places = ((6.0, -11.0), (6.0, 5.0), (-6.0, 5.0), (-6.0, -11.0))

    def free(rect: tuple[float, float, float, float]) -> bool:
        left, bottom, right, top = rect
        pad = 5.0 * unit
        if any(left - pad < px < right + pad and bottom - pad < py < top + pad for px, py in marks):
            return False
        return not any(left < r and right > lt and bottom < t and top > b for lt, b, r, t in taken)

    for x, y, text in items:
        width = len(text) * fontsize * 0.55 * unit
        height = fontsize * 1.2 * unit
        px, py = x * scale, y * scale
        chosen = places[0]
        rect = (0.0, 0.0, 0.0, 0.0)
        for dx, dy in places:
            left = px + dx * unit if dx > 0 else px + dx * unit - width
            candidate = (left, py + dy * unit, left + width, py + dy * unit + height)
            if free(candidate):
                chosen, rect = (dx, dy), candidate
                break
        else:
            dx, dy = chosen
            left = px + dx * unit
            rect = (left, py + dy * unit, left + width, py + dy * unit + height)
        taken.append(rect)
        ax.annotate(
            text,
            (x, y),
            textcoords="offset points",
            xytext=chosen,
            ha="left" if chosen[0] > 0 else "right",
            fontsize=fontsize,
            color=INK_SECONDARY,
            zorder=5,
        )


def _ratio_lines(run: ExperimentResult) -> list[float]:
    """The priorities drawn on the radius plane: 0, 0.1, 0.2, 0.3 — more if d is larger."""
    largest = float(run.result.characteristics.d.max()) if run.result.m else 0.0
    steps = list(RATIO_LINES)
    while steps[-1] < min(largest, 0.9) - 1e-12:
        steps.append(round(steps[-1] + 0.1, 1))
    return steps


def draw_radius_plane(ax: Axes, run: ExperimentResult) -> None:
    """The point (r, z) of every object; d is constant on every line through the origin.

    Below the diagonal z < r (the k-sphere lies inside the enemy sphere), above it z > r (the
    nearest enemy lies inside the k-sphere); on it d = 0. Objects on one point tie in d and r.
    """
    c = run.result.characteristics
    names = run.object_names
    length = ray_length(c) or 1.0
    _style(ax, "Radius plane — d(Sᵢ) is constant on every line through the origin", grid_axis="")
    for d in _ratio_lines(run):
        below, above = ratio_line(d, length)
        if d == 0.0:
            ax.plot([0.0, length], [0.0, length], color=AXIS, linewidth=1.4, zorder=1)
            ax.annotate(
                "d = 0",
                (length, length),
                textcoords="offset points",
                xytext=(3, 3),
                fontsize=7,
                color=MUTED,
            )
            continue
        for end in (below, above):
            ax.plot([0.0, end[0]], [0.0, end[1]], color=GRID, linewidth=1.0, zorder=1)
            ax.annotate(
                f"d = {d:g}",
                end,
                textcoords="offset points",
                xytext=(3, 3),
                fontsize=7,
                color=MUTED,
            )
    ax.text(
        0.97,
        0.04,
        "z < r · k-sphere inside the enemy sphere",
        transform=ax.transAxes,
        ha="right",
        fontsize=8,
        color=MUTED,
    )
    ax.text(
        0.03,
        0.96,
        "z > r · nearest enemy inside the k-sphere",
        transform=ax.transAxes,
        va="top",
        fontsize=8,
        color=MUTED,
    )
    for index in np.unique(c.classes).tolist():
        chosen = c.classes == index
        ax.scatter(
            c.r[chosen],
            c.z[chosen],
            s=64,
            marker=_marker(int(index)),
            color=_colour(int(index)),
            edgecolors=SURFACE,
            linewidths=1.2,
            zorder=4,
        )
    ax.set_xlim(0.0, length * 1.04)
    ax.set_ylim(0.0, length * 1.04)
    ax.set_aspect("equal")
    if c.m <= LABEL_LIMIT:
        items = []
        for group in coinciding_points(c):
            first = group[0]
            text = ", ".join(f"{names[j]} ({int(c.position[j])})" for j in group)
            items.append((float(c.r[first]), float(c.z[first]), text))
        _place_labels(ax, items, [(float(r), float(z)) for r, z in zip(c.r, c.z, strict=True)])
    ax.set_xlabel("r(Sᵢ) · enemy-sphere radius")
    ax.set_ylabel(f"z(Sᵢ, {c.k}) · k-sphere radius")
    handles: list[Line2D | Patch] = [*_class_handles(run)]
    handles.append(Line2D([], [], color=GRID, linewidth=1.0, label="a line of equal d(Sᵢ)"))
    handles.append(Line2D([], [], linestyle="", label="S₁ (1): object (Step 2 position)"))
    ax.legend(
        handles=handles,
        frameon=False,
        fontsize=8,
        labelcolor=INK_SECONDARY,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
    )


def _iteration_handles(run: ExperimentResult) -> list[Line2D | Patch]:
    return [
        Patch(
            facecolor=STATES["L"].fill,
            edgecolor=MUTED,
            linewidth=2.0,
            label="Sⱼ ∈ L — its sphere contains Sᵢ",
        ),
        Line2D(
            [],
            [],
            color=MUTED,
            linewidth=1.2,
            linestyle=_K_SPHERE,
            label="own class in F, not in L",
        ),
        Line2D(
            [],
            [],
            color=MUTED,
            linewidth=1.2,
            linestyle=_IN_D,
            label="own class in D — no longer counts",
        ),
        Line2D(
            [],
            [],
            linestyle="",
            marker="o",
            markersize=10,
            color=MUTED,
            markeredgecolor=INK,
            markeredgewidth=1.8,
            label="Sᵢ — the selected object (centre)",
        ),
        _filled("filled: in D"),
        _hollow("hollow: in F"),
        *_class_handles(run),
    ]


def draw_iteration_spheres(
    ax: Axes, run: ExperimentResult, t: int, *, compact: bool = False, legend: bool = True
) -> None:
    """Iteration t: the enemy spheres of the own-class objects around the selected Sᵢ.

    Every object stands at its true distance ρ(Sⱼ, Sᵢ) from Sᵢ (in Sᵢ's neighbour order), so a
    sphere of radius r(Sⱼ) around Sⱼ contains the centre exactly when ρ(Sⱼ, Sᵢ) < r(Sⱼ) — the
    condition of Step 4. Labels show the counters g before → after and the moves to D.
    """
    result = run.result
    c = result.characteristics
    names = run.object_names
    view = iteration_view(run, t)
    if view.selected is None:
        _style(ax, f"Iteration {t}  ·  queue empty → Step 6 (stop)", grid_axis="")
        ax.text(
            0.5,
            0.5,
            f"D = {_short_set(result.training.tolist(), names, 48)}\n"
            f"F = {_short_set(result.validation.tolist(), names, 48)}",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=9 if compact else 11,
            color=INK_SECONDARY,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return
    i = view.selected
    it = result.iterations[t - 1]
    decision = it.decision.value
    members = _short_set(it.L, names, 60)
    if compact:
        full = object_set(it.L, names)
        shown = f"L = {full}" if len(full) <= 20 else f"|L| = {len(it.L)}"
        title = f"t = {t}  ·  Sᵢ = {names[i]}  ·  {shown}\n{decision}"
    else:
        title = f"Iteration {t}  ·  Sᵢ = {names[i]}  ·  L = {members}  ·  {decision}"
        if len(title) > 72:  # the decision on a line of its own
            title = f"Iteration {t}  ·  Sᵢ = {names[i]}  ·  L = {members}\n{decision}"
    _style(ax, title, grid_axis="")
    if compact:
        ax.title.set_fontsize(8.5)
    layout = radial_layout(run.distances.matrix, c, i)
    x, y = layout.xy()
    m = c.m
    crowded = m > CROWDED
    if not crowded:
        for j in np.flatnonzero(np.arange(m) != i).tolist():
            ax.plot([0.0, x[j]], [0.0, y[j]], color=GRID, linewidth=0.7, zorder=1)
    extent = float(np.max(np.hypot(x, y))) if m else 1.0
    drawn = view.own_class & (view.contains | (not crowded))
    for j in np.flatnonzero(drawn).tolist():
        colour = _colour(int(c.classes[j]))
        radius = float(view.radius[j])
        extent = max(extent, float(math.hypot(x[j], y[j])) + radius)
        if view.in_l[j]:
            ax.add_patch(
                Circle(
                    (x[j], y[j]),
                    radius,
                    facecolor=STATES["L"].fill,
                    alpha=0.45,
                    edgecolor="none",
                    zorder=0,
                )
            )
            ax.add_patch(
                Circle((x[j], y[j]), radius, fill=False, edgecolor=colour, linewidth=2.0, zorder=2)
            )
        elif view.in_f[j]:
            ax.add_patch(
                Circle(
                    (x[j], y[j]),
                    radius,
                    fill=False,
                    edgecolor=colour,
                    linewidth=1.2,
                    linestyle=_K_SPHERE,
                    zorder=2,
                )
            )
        else:
            ax.add_patch(
                Circle(
                    (x[j], y[j]),
                    radius,
                    fill=False,
                    edgecolor=colour,
                    linewidth=1.2,
                    linestyle=_IN_D,
                    alpha=0.7,
                    zorder=2,
                )
            )
    others = np.arange(m) != i
    _points(
        ax,
        x[others],
        y[others],
        c.classes[others],
        (~view.in_f)[others],
        size=18 if crowded else 64,
        rasterized=crowded,
    )
    _centre(ax, 0.0, 0.0, int(c.classes[i]), size=60 if crowded else 150)
    if crowded:
        ax.text(
            0.01,
            0.01,
            f"m = {m}: only the spheres that contain Sᵢ are drawn",
            transform=ax.transAxes,
            fontsize=7,
            color=INK_SECONDARY,
        )
    limit = PANEL_LABELS if compact else LABEL_LIMIT
    if m <= limit:
        for j in range(m):
            parts = [f"{names[j]} = Sᵢ" if j == i else names[j]]
            if view.g_after[j] != view.g_before[j]:
                parts.append(f"g {int(view.g_before[j])}→{int(view.g_after[j])}")
            if view.moved_by[j]:
                parts.append("→ D" if compact else f"→ D (Step {int(view.moved_by[j])})")
            angle = float(layout.angle[j]) if j != i else -math.pi / 2
            ax.annotate(
                (" " if compact else "  ·  ").join(parts),
                (x[j], y[j]),
                textcoords="offset points",
                xytext=(8 * math.cos(angle), 8 * math.sin(angle)),
                ha="left"
                if math.cos(angle) > 0.2
                else ("right" if math.cos(angle) < -0.2 else "center"),
                va="bottom"
                if math.sin(angle) > 0.2
                else ("top" if math.sin(angle) < -0.2 else "center"),
                fontsize=7 if compact else 8,
                color=INK if j == i else INK_SECONDARY,
                zorder=7,
            )
    _square(ax, extent * 1.08)
    if legend and not compact:
        ax.legend(
            handles=_iteration_handles(run),
            frameon=False,
            fontsize=8,
            labelcolor=INK_SECONDARY,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
        )


def _short_set(indices: Sequence[int], names: Sequence[str], limit: int) -> str:
    """``{S₁, S₂, S₅}`` — or ``{S₁, S₂, S₅, …} (12)`` when the full set is longer than ``limit``."""
    full = object_set(indices, names)
    if len(full) <= limit:
        return full
    return object_set(indices[:3], names)[:-1] + f", …}} ({len(indices)})"


def sphere_iterations(run: ExperimentResult) -> list[int]:
    """The iterations of the multi-panel figure: the first 12."""
    return list(range(1, min(len(run.result.iterations), PANEL_LIMIT) + 1))


def draw_iteration_panels(figure: Figure, run: ExperimentResult) -> None:
    """The spheres around Sᵢ in every iteration, one panel each (*Hyperspheres (Iterations)*)."""
    chosen = sphere_iterations(run)
    if not chosen:  # no iteration (an empty queue from the start cannot happen with m ≥ 1)
        chosen = [1]
    panels, spare = _panel_grid(figure, len(chosen))
    for ax, t in zip(panels, chosen, strict=True):
        draw_iteration_spheres(ax, run, t, compact=True, legend=False)
    total = len(run.result.iterations)
    which = "" if total <= PANEL_LIMIT else f" — the first {PANEL_LIMIT} of {total}"
    figure.suptitle(
        f"Hyperspheres in every iteration{which} — the spheres in F that contain Sᵢ give L",
        x=0.01,
        ha="left",
        fontsize=11,
        color=INK,
    )
    _panel_legend(figure, spare, _iteration_handles(run))


RUN_FIGURES: dict[str, tuple[str, Callable[[Axes, ExperimentResult], None]]] = {
    "map": ("2-D map", draw_map),
    "radii": ("r and z per object", draw_radii),
    "priorities": ("Step 2 priorities", draw_priorities),
    "sizes": ("Sample sizes", draw_sizes),
    "composition": ("Class composition", draw_composition),
    "strips": ("Neighbourhood strips", draw_strips),
    "radius-plane": ("Radius plane (r, z)", draw_radius_plane),
}
"""The figures of one run on one axes: key → (name, draw function)."""

PANEL_FIGURES: dict[str, tuple[str, Callable[[Figure, ExperimentResult], None]]] = {
    "hyperspheres": ("Hyperspheres of every object", draw_object_panels),
    "iteration-spheres": ("Hyperspheres in every iteration", draw_iteration_panels),
}
"""The multi-panel figures of one run: key → (name, draw function on a figure)."""

FIGURE_SHEETS: dict[str, str] = {
    "hyperspheres": HYPERSPHERES_STEP1,
    "strips": HYPERSPHERES_STEP1,
    "radius-plane": HYPERSPHERES_STEP1,
    "iteration-spheres": HYPERSPHERES_ITERATIONS,
}
"""The workbook sheet a figure belongs to (every other figure: *Charts*)."""
CHARTS = "Charts"


def figure_names() -> list[tuple[str, str]]:
    """(key, name) of every figure of a run, in the order the exports and the GUI show them."""
    keys = ["map", "radii", "priorities", "sizes", "composition"]
    keys += ["hyperspheres", "strips", "radius-plane", "iteration-spheres"]
    names = {key: name for key, (name, _) in RUN_FIGURES.items()}
    names |= {key: name for key, (name, _) in PANEL_FIGURES.items()}
    return [(key, names[key]) for key in keys]


def figure_sheet(key: str) -> str:
    """The workbook sheet of figure ``key``: a *Hyperspheres* sheet or *Charts*."""
    return FIGURE_SHEETS.get(key, CHARTS)


def new_figure(width: float = 7.0, height: float = 4.2) -> Figure:
    """An empty figure on the chart surface (no pyplot global state)."""
    return Figure(figsize=(width, height), facecolor=SURFACE, layout="constrained")


def run_figure(key: str, run: ExperimentResult) -> Figure:
    """One figure of a run (see :data:`RUN_FIGURES`, :data:`PANEL_FIGURES`).

    Raises:
        KeyError: Unknown figure key.
    """
    m = run.result.m
    if key in PANEL_FIGURES:
        _, draw_panels = PANEL_FIGURES[key]
        count = len(sphere_objects(run) if key == "hyperspheres" else sphere_iterations(run))
        columns = min(4, max(count, 1))
        rows = math.ceil(max(count, 1) / columns)
        figure = new_figure(3.1 * columns + 0.4, 3.2 * rows + (0.9 if count % 4 == 0 else 0.5))
        draw_panels(figure, run)
        return figure
    if key not in RUN_FIGURES:
        raise KeyError(key)
    _, draw = RUN_FIGURES[key]
    if key in ("priorities", "strips"):
        height = max(4.2, min((0.28 if key == "priorities" else 0.42) * m + 1.5, 12.0))
    else:
        height = 4.6
    width = {"map": 6.4, "strips": 9.6, "radius-plane": 9.4}.get(key, 7.0)
    figure = new_figure(width, 6.4 if key == "radius-plane" else height)
    draw(figure.add_subplot(), run)
    return figure


def object_spheres_figure(run: ExperimentResult, i: int) -> Figure:
    """The two spheres of object ``i`` (0-based) with every other object around it."""
    figure = new_figure(9.6, 6.2)
    draw_object_spheres(figure.add_subplot(), run, i)
    return figure


def iteration_spheres_figure(run: ExperimentResult, t: int) -> Figure:
    """Iteration ``t`` (1-based): the own-class spheres around the selected Sᵢ."""
    figure = new_figure(9.6, 6.2)
    draw_iteration_spheres(figure.add_subplot(), run, t)
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


ANIMATION_SECONDS = 1.8
"""How long the animation shows every iteration."""


def iteration_animation(run: ExperimentResult, path: Path, *, dpi: int = 100) -> Path:
    """An animated GIF of the iteration diagrams: iterations 1 … 12, then Step 6.

    Every frame is :func:`iteration_spheres_figure`; the last one (the result) stays twice as
    long. Raises nothing for a run without iterations: it shows Step 6 alone.
    """
    from PIL import Image as PillowImage  # matplotlib's own dependency

    steps = [*sphere_iterations(run), len(run.result.iterations) + 1]
    frames = []
    for t in steps:
        buffer = io.BytesIO()
        figure = iteration_spheres_figure(run, t)
        figure.savefig(buffer, format="png", dpi=dpi, facecolor=SURFACE)
        buffer.seek(0)
        frames.append(PillowImage.open(buffer).convert("RGB"))
    durations = [int(ANIMATION_SECONDS * 1000)] * (len(frames) - 1) + [
        int(ANIMATION_SECONDS * 2000)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True
    )
    return path


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
