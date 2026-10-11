"""Colour semantics — one source for the tables, the figures, Excel, HTML, the GUI and the CLI.

A table cell or column header may carry a *mark* (:mod:`erdr.export.tables`): what it means, not
how it looks. This module gives every mark its colours, so a category looks the same on screen,
in the Excel workbook, in the HTML report, in the figures and in the console (ADR-019). The
colours are the ERDR workbook's own legend (*Overview*, "Colour legend"), which the template
project's workbooks share — with one change: blue and orange stay with the classes K1 and K2, as
in every figure, so the training sample D is aqua and the validation sample F violet.

Categories — what kind of quantity a column holds (column headers)
    ``quantitative`` feature (set I) blue · ``nominal`` feature (set J) yellow · ``class`` label
    red · ``characteristic`` r, g, z light green · ``priority`` d green · ``parameter`` lavender ·
    ``type`` flags · ``statistic`` of the scaling grey
Classes — ``K1``, ``K2``, … (:func:`class_mark`)
    the class of an object, in the figures' categorical colours: K1 blue, K2 orange, K3 aqua, …
Samples — ``D`` training aqua · ``F`` validation violet; ``moved`` to D takes D's colours
States of the algorithm
    ``selected`` · ``own`` · ``literal`` · ``yes`` green — ``L`` · ``decreased`` · ``tie-r``
    yellow — ``tie-index`` aqua (with D, as the workbook groups them) — ``enemy`` · ``no`` red —
    ``warning`` orange (not the literal article reading)

Cells and headers keep these light tints and dark inks in the light and in the dark theme of the
application (ADR-018); the *accent* of a mark is its strong colour, for figures, legend swatches
and the console. The categorical slots are the validated colour-blind-safe palette of the
template's figures, assigned in fixed order and never cycled.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------- figures: chrome and slots

SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948")
"""Categorical slots in their fixed order (blue, orange, aqua, yellow, magenta, green, violet,
red); classes take them in order, never cycled — a ninth class is drawn in :data:`MUTED`."""
SURFACE = "#fcfcfb"
"""Figure and axes background."""
INK = "#0b0b0b"
"""Titles and values in the figures."""
INK_SECONDARY = "#52514e"
"""Axis labels, legends, notes."""
MUTED = "#898781"
"""Tick marks and de-emphasised marks."""
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

TEXT = "#1f2430"
"""Ink on the lightest tints (the application's text colour)."""


# ---------------------------------------------------------------- marks


@dataclass(frozen=True)
class Swatch:
    """The colours of one mark."""

    fill: str
    """Background of a cell or a header (a light tint)."""
    ink: str
    """Text on :attr:`fill`."""
    accent: str
    """The strong colour of the mark: figures, legend swatches, the console."""
    meaning: str
    """What the colour says (tooltips and legends)."""


GOOD = ("#c6efce", "#006100")
"""The workbook's green: d(Sᵢ), selected, own class, correct."""
STEP = ("#ffe699", "#1f3864")
"""The workbook's yellow: member of L, decreased counter, tie decided by r."""
TRAINING = ("#b3e5d9", "#0b4a3c")
"""Aqua: the training sample D (the workbook's blue, which stays with K1)."""
VALIDATION = ("#d6cff7", "#3b2a8c")
"""Violet: the validation sample F."""
ENEMY = ("#fde9e7", "#9c0006")

D_ACCENT = SERIES[2]
"""Aqua — the training sample D in the figures."""
F_ACCENT = SERIES[6]
"""Violet — the validation sample F in the figures."""

CATEGORIES: dict[str, Swatch] = {
    "quantitative": Swatch("#ddebf7", TEXT, "#3987e5", "quantitative feature (set I)"),
    "nominal": Swatch("#fff2cc", TEXT, "#c98500", "nominal feature (set J)"),
    "type": Swatch("#d9e1f2", TEXT, MUTED, "feature types: 1 = quantitative (I), 0 = nominal (J)"),
    "class": Swatch("#f4cccc", "#9c0006", "#e34948", "class label"),
    "characteristic": Swatch("#e2efda", TEXT, "#199e70", "ERDR characteristic r, g, z"),
    "priority": Swatch(*GOOD, "#0ca30c", "priority d(Sᵢ) and the Step 2 order"),
    "parameter": Swatch("#e4dfec", "#3f3151", "#9085e9", "parameter / setting"),
    "statistic": Swatch("#f2f2f2", "#595959", MUTED, "scaling statistic"),
}
"""What kind of quantity a column holds — the workbook's legend."""

CLASS_TINTS = (
    ("#d6e6fa", "#123f7a"),
    ("#fbe0d3", "#8a3410"),
    ("#d1f0e4", "#0d5c40"),
    ("#fcecc4", "#6b4800"),
    ("#fadbe7", "#8a2a52"),
    ("#cfe8cf", "#005200"),
    ("#e0dcf7", "#3a2d8a"),
    ("#fbdada", "#8a1f1f"),
)
"""Fill and ink of the classes K1 … K8: tints of :data:`SERIES` (K1, K2 are the template's)."""

CLASSES: dict[str, Swatch] = {
    f"K{i + 1}": Swatch(fill, ink, SERIES[i], f"class K{i + 1}")
    for i, (fill, ink) in enumerate(CLASS_TINTS)
}
"""One mark per class, K1 … K8, in the colours the class has in every figure."""

SAMPLES: dict[str, Swatch] = {
    "D": Swatch(*TRAINING, D_ACCENT, "training sample D"),
    "F": Swatch(*VALIDATION, F_ACCENT, "validation sample F"),
    "moved": Swatch(*TRAINING, D_ACCENT, "moved to D in this iteration"),
}

STATES: dict[str, Swatch] = {
    "selected": Swatch(*GOOD, "#0ca30c", "the selected object Sᵢ (Step 3)"),
    "L": Swatch(*STEP, "#c98500", "member of L"),
    "decreased": Swatch(*STEP, "#c98500", "counter g decreased by Step 5"),
    "own": Swatch(*GOOD, "#0ca30c", "same class / inside the enemy sphere"),
    "enemy": Swatch(*ENEMY, "#d03b3b", "enemy (another class)"),
    "tie-r": Swatch(*STEP, "#c98500", "Step 2 order decided by r (equal d)"),
    "tie-index": Swatch(*TRAINING, D_ACCENT, "Step 2 order decided by the index (equal d, r)"),
}
"""The steps of the algorithm — the workbook's legend."""

CHECKS: dict[str, Swatch] = {
    "literal": Swatch(*GOOD, "#008300", "the literal article reading"),
    "warning": Swatch("#fce4d6", "#833c0b", "#fab219", "not the literal article reading"),
    "yes": Swatch(*GOOD, "#0ca30c", "occurs / permitted"),
    "no": Swatch("#ffc7ce", "#9c0006", "#d03b3b", "does not occur / not permitted"),
}

SWATCHES: dict[str, Swatch] = {**CATEGORIES, **CLASSES, **SAMPLES, **STATES, **CHECKS}
"""Every mark and its colours."""

LEGEND_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Columns", tuple(CATEGORIES)),
    ("Classes", tuple(CLASSES)),
    ("Samples", tuple(SAMPLES)),
    ("Steps of the algorithm", tuple(STATES)),
    ("Readings and checks", tuple(CHECKS)),
)
"""The legend's sections, in order."""


def class_mark(index: int) -> str:
    """The mark of the class with 0-based ``index``: ``K1`` for 0; ``class`` past K8."""
    name = f"K{index + 1}"
    return name if name in CLASSES else "class"


def class_colour(index: int) -> str:
    """The figure colour of the class with 0-based ``index`` (grey past the eighth class)."""
    return SERIES[index] if 0 <= index < len(SERIES) else MUTED


def swatch(mark: str | None) -> Swatch | None:
    """The colours of ``mark``; ``None`` for no mark or an unknown one."""
    return SWATCHES.get(mark) if mark else None


def meaning(mark: str, class_labels: Sequence[object] = ()) -> str:
    """What ``mark`` says; a class mark names its label (``class K1 (label 1)``)."""
    found = SWATCHES[mark]
    index = int(mark[1:]) - 1 if mark in CLASSES else -1
    if 0 <= index < len(class_labels):
        return f"{found.meaning} (label {class_labels[index]})"
    return found.meaning


def legend(marks: Iterable[str | None]) -> list[tuple[str, list[str]]]:
    """The legend sections that ``marks`` need: (section, marks in the theme's order)."""
    present = {mark for mark in marks if mark in SWATCHES}
    sections = []
    for title, members in LEGEND_GROUPS:
        chosen = [mark for mark in members if mark in present]
        if chosen:
            sections.append((title, chosen))
    return sections


# ---------------------------------------------------------------- stages of the experiment


@dataclass(frozen=True)
class Stage:
    """A stage of the experiment: the workbook colours its sheet tabs by stage."""

    name: str
    colour: str


STAGES: dict[str, Stage] = {
    "info": Stage("Overview", "#404040"),
    "data": Stage("The sample E₀", "#2f5597"),
    "step0": Stage("Step 0 · scaling and distances", "#7030a0"),
    "steps": Stage("Steps 1–5 · ERDR", "#c55a11"),
    "result": Stage("Step 6 · D and F, cases, charts", "#548235"),
    "analysis": Stage("Readings and k", "#bf8f00"),
}
"""The stages and their tab colours (the ERDR workbook's)."""

SHEET_STAGES: dict[str, str] = {
    "Overview": "info",
    "Dataset": "data",
    "Normalized Dataset": "step0",
    "Zhuravlev Distances": "step0",
    "Distances": "step0",
    "Sorted Neighbors": "step0",
    "ERDR Characteristics": "steps",
    "Hyperspheres (Step 1)": "steps",
    "Priority Queue": "steps",
    "Hyperspheres (Iterations)": "steps",
    "ERDR Trace": "steps",
    "Training & Validation": "result",
    "Case Checklist": "result",
    "Charts": "result",
    "Readings (Switches)": "analysis",
    "Article Table 1 Check": "analysis",
}
"""Workbook sheet → stage."""


def stage_of(sheet: str) -> Stage | None:
    """The stage of a workbook sheet, if it is one of the workbook's."""
    key = SHEET_STAGES.get(sheet)
    return STAGES[key] if key else None


# ---------------------------------------------------------------- readings in the figures

READING_COLOURS = ("#008300", "#2a78d6", "#eda100", "#e87ba4")
"""The literal reading (green, as in the tables), the closest reading (blue) and two more; every
other reading is drawn in :data:`MUTED`. Validated together for colour-vision deficiency."""


def hex_rgb(colour: str) -> tuple[int, int, int]:
    """``#2a78d6`` → ``(42, 120, 214)``."""
    value = colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
