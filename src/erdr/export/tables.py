"""Plain tables of a run — one model for CSV, JSON, Markdown, LaTeX, Excel, HTML and the GUI.

Every table mirrors a sheet of the ERDR workbook (ADR-012). Cells are plain values (text,
integers, floats, ``None``); :attr:`Table.marks` gives each cell an optional *mark* — what the cell
means, not how it looks — which the GUI, the Excel writer and the HTML report turn into colours:

``D`` / ``F``
    the object ends in the training / validation sample;
``selected``
    the object selected in an iteration (Step 3);
``L``
    a member of L; ``moved`` an object moved to D; ``decreased`` a counter lowered by Step 5;
``own`` / ``enemy``
    an own-class object inside the enemy sphere / an object of the other class;
``tie-r`` / ``tie-index``
    a Step 2 order decided by r / by the index;
``literal``
    the literal article reading (readings tables);
``yes`` / ``no``
    a case that occurs / does not;
``K1``, ``K2``, …
    the class of the object (:func:`~erdr.export.theme.class_mark`);
``literal`` / ``warning``
    a switch value of the literal reading / one that differs from it;
``statistic``, ``type``, ``parameter``
    a scaling statistic, the feature-type row, a setting.

:attr:`Table.header_marks` says what kind of quantity a column holds — a ``quantitative`` or
``nominal`` feature, the ``class``, an ERDR ``characteristic`` (r, g, z), the ``priority`` d, a
``parameter``, a sample ``D`` / ``F``, a class ``K1`` …; :mod:`erdr.export.theme` gives every
mark its colours.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from erdr.core.algorithm import Decision
from erdr.core.readings import Readings, ZScope
from erdr.data.schema import Dataset
from erdr.export.theme import class_mark
from erdr.notation import (
    DASH,
    changes_text,
    class_name,
    moves_text,
    object_order,
    object_set,
)
from erdr.services.analysis import ReadingRow, SweepRow
from erdr.services.experiment import ExperimentResult

Cell = str | int | float | None
"""A table cell."""
MATRIX_LIMIT = 60
"""Matrix tables (m × m) of larger samples are left out of Markdown, LaTeX and HTML (ADR-012)."""


@dataclass(frozen=True)
class Table:
    """A titled table of plain values."""

    key: str
    """Identifier and file stem, e.g. ``characteristics``."""
    title: str
    """Heading, e.g. ``Step 1 · r, g, z, d``."""
    columns: tuple[str, ...]
    """Column headers."""
    rows: tuple[tuple[Cell, ...], ...]
    """The cells, row by row."""
    marks: tuple[tuple[str | None, ...], ...] = ()
    """Per cell, an optional mark (see the module docstring); empty when there are none."""
    note: str = ""
    """One line shown under the table."""
    matrix: bool = False
    """An m × m table (left out of the text reports when m > :data:`MATRIX_LIMIT`)."""
    sheet: str = ""
    """The workbook sheet this table mirrors."""
    extra: dict[str, str] = field(default_factory=dict)
    """Additional text (e.g. the definition of the columns)."""
    header_marks: tuple[str | None, ...] = ()
    """Per column, an optional mark of its header: what kind of quantity the column holds."""

    def mark(self, row: int, column: int) -> str | None:
        """The mark of a cell, or ``None``."""
        if not self.marks:
            return None
        return self.marks[row][column]

    def header_mark(self, column: int) -> str | None:
        """The mark of a column header, or ``None``."""
        if not self.header_marks:
            return None
        return self.header_marks[column]

    def used_marks(self) -> set[str]:
        """Every mark of the table's cells and headers (what its legend has to explain)."""
        found = {mark for row in self.marks for mark in row if mark}
        return found | {mark for mark in self.header_marks if mark}


def _marks(rows: Sequence[Sequence[Cell]]) -> list[list[str | None]]:
    return [[None] * len(row) for row in rows]


def _sample_mark(run: ExperimentResult, j: int) -> str:
    return "D" if run.result.routes[j].in_training else "F"


def _labels(run: ExperimentResult) -> tuple[str, ...]:
    return tuple(str(v.item()) for v in run.dataset.y)


def class_marks(dataset: Dataset) -> tuple[str, ...]:
    """The class mark (``K1`` …) of every object."""
    return tuple(class_mark(int(i)) for i in dataset.class_index)


def _class_marks(run: ExperimentResult) -> tuple[str, ...]:
    return class_marks(run.dataset)


def feature_marks(dataset: Dataset) -> tuple[str, ...]:
    """``quantitative`` or ``nominal`` for every feature, in column order."""
    return tuple("quantitative" if q else "nominal" for q in dataset.quantitative)


def _class_columns(classes: int) -> tuple[str, ...]:
    return tuple(class_mark(i) for i in range(classes))


def _data_marks(
    dataset: Dataset, features: Sequence[str], statistics: int = 0
) -> tuple[tuple[str | None, ...], ...]:
    """Objects (the class cell in its class colour), the type row, the statistic rows."""
    width = len(features) + 2
    rows: list[tuple[str | None, ...]] = [
        (None, *([None] * len(features)), mark) for mark in class_marks(dataset)
    ]
    rows.append(("type", *features, "type"))
    rows += [tuple(["statistic"] * width)] * statistics
    return tuple(rows)


def _switch_marks(readings: Readings) -> tuple[str, str, str, str]:
    """A, B, C and the scope of z: ``literal`` where a switch reads the article literally."""
    a, b, c = tuple(readings.code)
    return (
        "literal" if a == "1" else "warning",
        "literal" if b == "1" else "warning",
        "literal" if c == "1" else "warning",
        "literal" if readings.z_scope is ZScope.ALL else "warning",
    )


# ---------------------------------------------------------------- tables of one run


def summary_table(run: ExperimentResult) -> Table:
    """Key results — the workbook's *Overview*, section *Key results*."""
    result = run.result
    names = run.object_names
    sizes = run.dataset.class_sizes
    d_counts = run.class_counts(result.training)
    f_counts = run.class_counts(result.validation)
    classes = len(run.dataset.classes)
    comp = ", ".join(f"{class_name(i)} {d_counts[i]}" for i in range(classes))
    fcomp = ", ".join(f"{class_name(i)} {f_counts[i]}" for i in range(classes))
    occurring = sum(case.occurs for case in run.cases)
    rows: list[tuple[Cell, ...]] = [
        ("Dataset", f"{run.dataset.name}  ({run.dataset.m}, {run.dataset.n}, {classes})"),
        ("Objects N · class sizes", f"{run.dataset.m} · " + " · ".join(str(s) for s in sizes)),
        ("Normalizer · metric", f"{run.distances.scaling.normalizer} · {run.distances.metric}"),
        ("k for z(Sᵢ, k) · permitted by the k rule", f"{run.k}  (permitted: {run.permitted.text})"),
        ("ε", run.result.epsilon),
        ("Reading", result.readings.label + ("  (literal)" if result.readings.is_literal else "")),
        ("Step 2 queue order", object_order(result.characteristics.priority, names)),
        ("Iterations until the queue is empty", len(result.iterations)),
        (
            "Training sample D",
            f"{object_set(result.training, names)}  ·  {result.training.size}  ({comp})",
        ),
        (
            "Validation sample F",
            f"{object_set(result.validation, names)}  ·  {result.validation.size}  ({fcomp})",
        ),
        ("Share of N in D", result.training.size / result.m),
        ("Cases of the algorithm that occur", f"{occurring} of {len(run.cases)}"),
    ]
    reading = "literal" if result.readings.is_literal else "warning"
    marks: list[tuple[str | None, ...]] = [(None, None)] * len(rows)
    for row in (2, 3, 4):
        marks[row] = ("parameter", None)
    marks[5] = ("parameter", reading)
    marks[8] = (None, "D")
    marks[9] = (None, "F")
    return Table(
        "summary",
        "Key results",
        ("Figure", "Value"),
        tuple(rows),
        tuple(marks),
        note="; ".join(run.notes) if run.notes else "Literal article reading.",
        sheet="Overview",
    )


def sample_table(ds: Dataset, title: str | None = None) -> Table:
    """A sample: objects, features, class and the type row — sheet *Dataset* (no run needed).

    Feature columns are marked ``quantitative`` or ``nominal``, the class cells ``K1``, ``K2`` …
    """
    rows: list[tuple[Cell, ...]] = [
        (ds.object_ids[i], *(float(v) for v in ds.X[i]), str(ds.y[i].item())) for i in range(ds.m)
    ]
    rows.append(("Type", *ds.type_flags, "1 = I"))
    features = feature_marks(ds)
    return Table(
        "dataset",
        f"Dataset · {ds.name}" if title is None else title,
        ("№", *ds.feature_names, "Class"),
        tuple(rows),
        _data_marks(ds, features),
        note="Last row: feature types (1 = quantitative, set I; 0 = nominal, set J).",
        sheet="Dataset",
        header_marks=(None, *features, "class"),
    )


def dataset_table(run: ExperimentResult) -> Table:
    """The sample E₀ — sheet *Dataset*."""
    return sample_table(run.dataset)


def normalized_table(run: ExperimentResult) -> Table:
    """Step 0 · the unified values with the scaling statistics — sheet *Normalized Dataset*."""
    ds = run.dataset
    Z = run.distances.unified
    labels = _labels(run)
    rows: list[tuple[Cell, ...]] = [
        (ds.object_ids[i], *(float(v) for v in Z[i]), labels[i]) for i in range(ds.m)
    ]
    rows.append(("Type", *ds.type_flags, "1 = I"))
    statistics = run.distances.scaling.statistics
    for key, values in statistics.items():
        rows.append((key, *(DASH if np.isnan(v) else float(v) for v in values), ""))
    features = feature_marks(ds)
    return Table(
        "normalized",
        f"Step 0 · Scale unification ({run.distances.scaling.normalizer})",
        ("№", *(f"{name}′" for name in ds.feature_names), "Class"),
        tuple(rows),
        _data_marks(ds, features, len(statistics)),
        note="Quantitative features rescaled over the objects of E₀; nominal codes unchanged.",
        sheet="Normalized Dataset",
        header_marks=(None, *features, "class"),
    )


def _matrix(
    run: ExperimentResult,
    key: str,
    title: str,
    corner: str,
    values: np.ndarray,
    sheet: str,
    note: str,
) -> Table:
    names = run.object_names
    m = len(names)
    rows: list[tuple[Cell, ...]] = [
        (names[i], *(float(values[i, j]) for j in range(m))) for i in range(m)
    ]
    same = run.result.characteristics.classes
    objects = _class_marks(run)
    marks = [
        [objects[i], *("own" if same[i] == same[j] and i != j else None for j in range(m))]
        for i in range(m)
    ]
    return Table(
        key,
        title,
        (corner, *names),
        tuple(rows),
        tuple(tuple(r) for r in marks),
        note,
        True,
        sheet,
        header_marks=(None, *objects),
    )


def distance_tables(run: ExperimentResult) -> list[Table]:
    """Step 0 · ρ, and for the Zhuravlev metric ρ_I and ρ_J — sheet *Zhuravlev Distances*."""
    sheet = "Zhuravlev Distances" if run.distances.metric == "zhuravlev" else "Distances"
    note = f"Rounded to {run.distances.decimals} decimals; shaded: pairs of the same class."
    tables = [
        _matrix(
            run,
            "distances",
            f"Step 0 · Distances ρ ({run.distances.metric})",
            "ρ",
            run.distances.matrix,
            sheet,
            note,
        )
    ]
    if run.distances.quantitative_part is not None and run.distances.nominal_part is not None:
        tables.append(
            _matrix(
                run,
                "distances-quantitative",
                "ρ_I · quantitative part Σ_{j∈I} |x′ⱼ − y′ⱼ|",
                "ρ_I",
                run.distances.quantitative_part,
                sheet,
                note,
            )
        )
        tables.append(
            _matrix(
                run,
                "distances-nominal",
                "ρ_J · nominal part Σ_{j∈J} [xⱼ ≠ yⱼ]",
                "ρ_J",
                run.distances.nominal_part,
                sheet,
                note,
            )
        )
    return tables


def neighbours_table(run: ExperimentResult) -> Table:
    """Rank of Sⱼ in the neighbour list of Sᵢ — sheet *Sorted Neighbors*."""
    c = run.result.characteristics
    names = run.object_names
    objects = _class_marks(run)
    m = c.m
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for i in range(m):
        rank = {int(j): place + 1 for place, j in enumerate(c.order[i])}
        rows.append((names[i], *(DASH if i == j else rank[j] for j in range(m))))
        marks.append(
            (
                objects[i],
                *(
                    None
                    if i == j
                    else (
                        "own"
                        if c.spheres[i, j]
                        else ("enemy" if c.classes[i] != c.classes[j] else None)
                    )
                    for j in range(m)
                ),
            )
        )
    return Table(
        "neighbours",
        "Sorted neighbours · rank of Sⱼ for Sᵢ (equal ρ → smaller index first)",
        ("Sᵢ \\ Sⱼ", *names),
        tuple(rows),
        tuple(marks),
        "Shaded: own class inside the enemy sphere; marked: enemies.",
        True,
        "Sorted Neighbors",
        header_marks=(None, *objects),
    )


def characteristics_table(run: ExperimentResult) -> Table:
    """Step 1 · r, g, z, d and the Step 2 position — sheet *ERDR Characteristics*."""
    c = run.result.characteristics
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    scope = "any class" if c.z_scope.value == "all" else "the own class"
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for i in range(c.m):
        inside = [names[j] for j in c.order[i] if c.spheres[i, j]]
        rows.append(
            (
                names[i],
                labels[i],
                names[c.nearest_enemy[i]],
                float(c.r[i]),
                int(c.g[i]),
                int(c.enemy_rank[i]),
                names[c.kth_neighbour[i]],
                float(c.z[i]),
                float(c.z[i] - c.r[i]),
                float(c.d[i]),
                int(c.position[i]),
                ", ".join([f"{names[i]} (itself)", *inside]),
            )
        )
        marks.append((_sample_mark(run, i), objects[i], *([None] * 10)))
    return Table(
        "characteristics",
        f"Step 1 · r, g, z, d (k = {c.k}, z over {scope})",
        (
            "№",
            "Class",
            "Nearest enemy",
            "r(Sᵢ)",
            "g(Sᵢ)",
            "Rank of the nearest enemy",
            "k-th neighbour",
            f"z(Sᵢ, {c.k})",
            "z − r",
            "d(Sᵢ)",
            "Priority position",
            "Own-class objects inside the sphere",
        ),
        tuple(rows),
        tuple(marks),
        "r = nearest-enemy distance · g = own-class objects strictly inside the enemy sphere "
        "(Sᵢ counts) · z = distance to the k-th neighbour · d = |z − r| / (z + r).",
        sheet="ERDR Characteristics",
        header_marks=(
            None,
            "class",
            None,
            "characteristic",
            "characteristic",
            "characteristic",
            None,
            "characteristic",
            "characteristic",
            "priority",
            "priority",
            None,
        ),
    )


def spheres_table(run: ExperimentResult) -> Table:
    """M(i, j) = 1 when Sⱼ ∈ K_t and ρ(Sᵢ, Sⱼ) < r(Sᵢ) — the enemy-sphere matrix."""
    c = run.result.characteristics
    names = run.object_names
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = [
        (names[i], *(int(c.spheres[i, j]) for j in range(c.m)), int(c.g[i])) for i in range(c.m)
    ]
    marks = [
        (objects[i], *("own" if c.spheres[i, j] else None for j in range(c.m)), None)
        for i in range(c.m)
    ]
    return Table(
        "spheres",
        "Enemy spheres · M(i, j) = 1 when Sⱼ has the class of Sᵢ and ρ(Sᵢ, Sⱼ) < r(Sᵢ)",
        ("Sphere of Sᵢ \\ Sⱼ", *names, "Row sum = g(Sᵢ)"),
        tuple(rows),
        tuple(marks),
        "Row: who is inside the sphere of Sᵢ; column: whose spheres contain Sⱼ.",
        True,
        "ERDR Characteristics",
        header_marks=(None, *objects, "characteristic"),
    )


def queue_table(run: ExperimentResult) -> Table:
    """Step 2 · the static priority order — sheet *Priority Queue*."""
    c = run.result.characteristics
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    decided = c.decided_by()
    text = {"d": "d", "r": "r (equal d)", "index": "index (equal d and r)", "—": "— (last)"}
    mark = {"r": "tie-r", "index": "tie-index"}
    rows = [
        (
            position + 1,
            names[i],
            int(i) + 1,
            labels[i],
            float(c.d[i]),
            float(c.r[i]),
            text[decided[position]],
        )
        for position, i in enumerate(c.priority)
    ]
    marks = [
        (None, None, None, objects[i], None, None, mark.get(decided[position]))
        for position, i in enumerate(c.priority)
    ]
    return Table(
        "queue",
        "Step 2 · Priority queue — d ascending, then r, then index",
        (
            "Position",
            "Object",
            "Index i",
            "Class",
            "d(Sᵢ)",
            "r(Sᵢ)",
            "Order against the next decided by",
        ),
        tuple(rows),
        tuple(marks),
        "Static order: d and r of a waiting object never change; every iteration takes the "
        "first object still in F and not processed.",
        sheet="Priority Queue",
        header_marks=("priority", None, None, "class", "priority", "characteristic", None),
    )


def iterations_table(run: ExperimentResult) -> Table:
    """Steps 2–5 · one row per iteration — sheets *ERDR Iterations* and *ERDR Trace*."""
    names = run.object_names
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for it in run.result.iterations:
        changes = [(ch.object, ch.before, ch.after) for ch in it.changes]
        moves = [(mv.object, mv.step) for mv in it.moves]
        decision = it.decision.value + (
            " (stopped at the first move, C = 2)" if it.stopped_early else ""
        )
        rows.append(
            (
                it.number,
                names[it.selected],
                it.queue_length,
                float(it.d),
                float(it.r),
                object_set(it.covering, names),
                object_set(it.excluded, names),
                object_set(it.L, names),
                len(it.L),
                decision,
                float(it.blocked_d),
                changes_text(changes, names),
                moves_text(moves, names),
                it.f_size,
                it.d_size,
                it.queue_left,
            )
        )
        mark = "moved" if it.moves else ("decreased" if it.decision is Decision.CORRECT else None)
        marks.append((None, "selected", *([None] * 7), None, None, None, mark, None, None, None))
    return Table(
        "iterations",
        "Steps 2–5 · Iterations",
        (
            "t",
            "Selected Sᵢ",
            "Queue length",
            "d(Sᵢ)",
            "r(Sᵢ)",
            "Covering Sᵢ (ρ(Sⱼ, Sᵢ) < r(Sⱼ))",
            "Left out by readings A/B",
            "L",
            "|L|",
            "Decision",
            "Blocked d ← −(d + ε)",
            "Counters g: before → after",
            "Moved to D",
            "|F| after",
            "|D| after",
            "Queue left",
        ),
        tuple(rows),
        tuple(marks),
        "L = {Sⱼ ∈ F ∩ K_t | ρ(Sⱼ, Sᵢ) < r(Sⱼ) and g(Sⱼ) > 1} is built before Sᵢ is blocked.",
        sheet="ERDR Trace",
        header_marks=(
            None,
            "selected",
            None,
            "priority",
            "characteristic",
            None,
            None,
            "L",
            "L",
            None,
            "priority",
            "characteristic",
            "D",
            "F",
            "D",
            None,
        ),
    )


def counters_table(run: ExperimentResult) -> Table:
    """G after every iteration (start = Step 1) — sheet *ERDR Trace*."""
    names = run.object_names
    objects = _class_marks(run)
    history = run.result.counter_history()
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for t, row in enumerate(history):
        state = run.result.state_after(t)
        rows.append(("start" if t == 0 else t, *(int(v) for v in row)))
        previous = history[t - 1] if t else row
        marks.append(
            (
                None,
                *(
                    "decreased" if row[j] < previous[j] else ("D" if not state.in_f[j] else None)
                    for j in range(len(names))
                ),
            )
        )
    return Table(
        "counters",
        "Counters g after every iteration",
        ("t", *names),
        tuple(rows),
        tuple(marks),
        "Marked: decreased in this iteration; shaded: already in D.",
        True,
        "ERDR Trace",
        header_marks=(None, *objects),
    )


def routes_table(run: ExperimentResult) -> Table:
    """Step 6 · every object's sample and how it got there — sheet *Training & Validation*."""
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    by = {4: "Step 4 · |L| = 1", 5: "Step 5 · g fell to 1", None: "— (stays in F)"}
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for j, route in enumerate(run.result.routes):
        rows.append(
            (
                names[j],
                labels[j],
                "D · training" if route.in_training else "F · validation",
                route.processed_in if route.processed_in is not None else DASH,
                route.entered_d_in if route.entered_d_in is not None else DASH,
                by[route.entered_by],
                route.counter_decreases,
            )
        )
        marks.append((None, objects[j], _sample_mark(run, j), None, None, None, None))
    return Table(
        "routes",
        "Step 6 · Training sample D and validation sample F = E₀ \\ D",
        (
            "№",
            "Class",
            "Sample",
            "Processed in iteration",
            "Entered D in iteration",
            "Entered D by",
            "Counter decreases",
        ),
        tuple(rows),
        tuple(marks),
        sheet="Training & Validation",
        header_marks=(None, "class", None, None, None, None, "characteristic"),
    )


def composition_table(run: ExperimentResult) -> Table:
    """Class composition of D and F."""
    result = run.result
    classes = len(run.dataset.classes)
    rows: list[tuple[Cell, ...]] = []
    for label, indices in (
        ("D · training", result.training),
        ("F · validation", result.validation),
    ):
        counts = run.class_counts(indices)
        rows.append((label, *counts, int(indices.size), indices.size / result.m))
    rows.append(("Total", *run.dataset.class_sizes, result.m, 1.0))
    marks = [
        ("D", *([None] * (classes + 2))),
        ("F", *([None] * (classes + 2))),
        tuple([None] * (classes + 3)),
    ]
    return Table(
        "composition",
        "Class composition of D and F",
        (
            "Sample",
            *(f"{class_name(i)} (class {run.dataset.classes[i]})" for i in range(classes)),
            "Total",
            "Share of N",
        ),
        tuple(rows),
        tuple(marks),
        sheet="Training & Validation",
        header_marks=(None, *_class_columns(classes), None, None),
    )


def cases_table(run: ExperimentResult) -> Table:
    """The 17 cases and where they occur — sheet *Case Checklist*."""
    rows = [
        (
            case.case.number,
            case.case.title,
            case.case.checked_on,
            "✓" if case.occurs else "✗",
            case.first,
            case.case.why,
            case.case.kind,
        )
        for case in run.cases
    ]
    marks = [
        (None, None, None, "yes" if case.occurs else "no", None, None, None) for case in run.cases
    ]
    occurring = sum(case.occurs for case in run.cases)
    return Table(
        "cases",
        f"Case checklist · {occurring} of {len(run.cases)} cases occur",
        ("#", "Case", "Checked on", "Occurs", "First", "Why it matters", "Kind"),
        tuple(rows),
        tuple(marks),
        sheet="Case Checklist",
    )


RUN_TABLES: tuple[tuple[str, Callable[[ExperimentResult], Table | list[Table]]], ...] = (
    ("summary", summary_table),
    ("dataset", dataset_table),
    ("normalized", normalized_table),
    ("distances", distance_tables),
    ("neighbours", neighbours_table),
    ("characteristics", characteristics_table),
    ("spheres", spheres_table),
    ("queue", queue_table),
    ("iterations", iterations_table),
    ("counters", counters_table),
    ("routes", routes_table),
    ("composition", composition_table),
    ("cases", cases_table),
)
"""The tables of one run, in workbook order."""


def run_tables(run: ExperimentResult) -> list[Table]:
    """Every table of one run, in workbook order."""
    tables: list[Table] = []
    for _, build in RUN_TABLES:
        made = build(run)
        tables.extend(made if isinstance(made, list) else [made])
    return tables


# ---------------------------------------------------------------- analysis tables


def readings_table(rows: Sequence[ReadingRow], names: Sequence[str], classes: int) -> Table:
    """Every reading on one sample — sheet *Readings (Switches)*."""
    out: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for row in rows:
        a, b, c = tuple(row.readings.code)
        scope = "any class" if row.readings.z_scope.value == "all" else "own class"
        if row.error:
            out.append((a, b, c, scope, row.error, DASH, DASH, DASH, *([DASH] * classes), DASH))
        else:
            out.append(
                (
                    a,
                    b,
                    c,
                    scope,
                    object_order(row.processing_order, names),
                    object_set(row.training, names),
                    object_set(row.validation, names),
                    len(row.training),
                    *row.training_by_class,
                    row.iterations,
                )
            )
        marks.append((*_switch_marks(row.readings), *([None] * (len(out[-1]) - 4))))
    return Table(
        "readings",
        "Readings of §1.1 · every combination of A, B, C",
        (
            "A",
            "B",
            "C",
            "z over",
            "Processing order (Step 3)",
            "D · training",
            "F · validation",
            "|D|",
            *(f"|D ∩ {class_name(i)}|" for i in range(classes)),
            "Iterations",
        ),
        tuple(out),
        tuple(marks),
        "A: Sᵢ in its own L · B: processed objects keep covering · C: return to Step 2 after the "
        "whole L (1) or the first move (2). Green: the literal article text; orange: a switch "
        "that differs from it.",
        sheet="Readings (Switches)",
        header_marks=(
            "parameter",
            "parameter",
            "parameter",
            "parameter",
            None,
            "D",
            "F",
            "D",
            *_class_columns(classes),
            None,
        ),
    )


def sweep_table(rows: Sequence[SweepRow], classes: int) -> Table:
    """|D| for every k and reading — sheet *Article Table 1 Check*."""
    out: list[tuple[Cell, ...]] = [
        (
            row.k,
            row.readings.label,
            row.training_size,
            *row.training_by_class,
            row.validation_size,
            row.share,
            row.iterations,
            "yes" if row.permitted else "no",
        )
        for row in rows
    ]
    marks = [
        (
            None,
            "literal" if row.readings.is_literal else "warning",
            *([None] * (classes + 4)),
            "yes" if row.permitted else "no",
        )
        for row in rows
    ]
    return Table(
        "sweep",
        "Training-sample size |D| by k",
        (
            "k",
            "Reading",
            "|D|",
            *(f"|D ∩ {class_name(i)}|" for i in range(classes)),
            "|F|",
            "Share of N",
            "Iterations",
            "Permitted by the k rule",
        ),
        tuple(out),
        tuple(marks),
        "Green: the literal article reading; orange: another reading. Permitted k: odd, "
        "3 ≤ k ≤ 2·min|Kᵢ| − 3.",
        sheet="Article Table 1 Check",
        header_marks=(
            "parameter",
            "parameter",
            "D",
            *_class_columns(classes),
            "F",
            None,
            None,
            "parameter",
        ),
    )
