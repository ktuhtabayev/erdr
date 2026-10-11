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
from erdr.core.hyperspheres import (
    IterationSpheres,
    Relation,
    SphereProfile,
    containing_text,
    cover_change_text,
    density_text,
    iteration_spheres,
    iteration_summary,
    iteration_title,
    possible_cover,
    relation_meaning,
    sphere_profile,
    step1_summary,
)
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
HYPERSPHERES_STEP1 = "Hyperspheres (Step 1)"
"""The workbook sheet of the enemy spheres and k-spheres of Step 1."""
HYPERSPHERES_ITERATIONS = "Hyperspheres (Iterations)"
"""The workbook sheet of the spheres around the selected object of every iteration."""
TICK = "✓"
CROSS = "✗"


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


# ---------------------------------------------------------------- Step 1 as hyperspheres


def profile(run: ExperimentResult) -> SphereProfile:
    """What the enemy sphere and the k-sphere of every object of ``run`` contain."""
    return sphere_profile(
        run.distances.matrix, run.result.characteristics, decimals=run.config.erdr.d_decimals
    )


def enemy_spheres_table(run: ExperimentResult) -> Table:
    """The enemy sphere (Sᵢ, r(Sᵢ)) of every object — sheet *Hyperspheres (Step 1)*."""
    c = run.result.characteristics
    p = profile(run)
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for i in range(c.m):
        g = int(c.g[i])
        agrees = g == int(p.g_from_spheres[i])
        boundary = int(p.strictly_inside[i]) == g
        inside = [names[j] for j in c.order[i] if c.spheres[i, j]]
        rows.append(
            (
                names[i],
                labels[i],
                float(c.r[i]),
                names[c.nearest_enemy[i]],
                int(p.own_inside[i]),
                int(p.own_on_sphere[i]),
                int(p.enemies_inside[i]),
                int(p.enemies_on_sphere[i]),
                g,
                TICK if agrees else CROSS,
                int(p.closed_count[i]),
                TICK if boundary else CROSS,
                ", ".join([f"{names[i]} (itself)", *inside]),
                density_text(g, int(p.own_on_sphere[i])),
            )
        )
        marks.append(
            (
                _sample_mark(run, i),
                objects[i],
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "yes" if agrees else "no",
                None,
                "yes" if boundary else "no",
                "own",
                None,
            )
        )
    return Table(
        "enemy-spheres",
        "Step 1 · Enemy spheres (Sᵢ, r(Sᵢ)) — open, through the nearest enemy",
        (
            "№",
            "Class",
            "r(Sᵢ) · radius",
            "Nearest enemy (on the sphere)",
            "Own class strictly inside (Sᵢ excluded)",
            "Own class on the sphere (ρ = r, not counted)",
            "Enemies strictly inside",
            "Enemies on the sphere",
            "g(Sᵢ) = 1 + inside",
            "= Step 1",
            "Closed count ρ ≤ r (all classes)",
            "Closed count − on the sphere = g",
            "Members of the enemy sphere (g)",
            "Reading",
        ),
        tuple(rows),
        tuple(marks),
        "Only own-class objects strictly inside count (Sᵢ itself included); objects on the "
        "sphere do not — a closed count ρ ≤ r differs from g exactly by them.",
        sheet=HYPERSPHERES_STEP1,
        header_marks=(
            None,
            "class",
            "characteristic",
            "enemy",
            "own",
            "own",
            "enemy",
            "enemy",
            "characteristic",
            None,
            None,
            None,
            "own",
            None,
        ),
    )


def k_spheres_table(run: ExperimentResult) -> Table:
    """The k-sphere (Sᵢ, z(Sᵢ, k)) against the enemy sphere — sheet *Hyperspheres (Step 1)*."""
    c = run.result.characteristics
    p = profile(run)
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for i in range(c.m):
        agrees = abs(float(p.d_from_ratio[i]) - float(c.d[i])) < 1e-9
        relation = p.relation[i]
        rows.append(
            (
                names[i],
                labels[i],
                names[c.kth_neighbour[i]],
                float(c.z[i]),
                float(c.r[i]),
                int(p.k_members[i]),
                int(p.k_own[i]),
                int(p.k_enemies[i]),
                int(c.enemy_rank[i]),
                float(p.ratio[i]),
                float(p.d_from_ratio[i]),
                TICK if agrees else CROSS,
                relation.value,
                relation_meaning(relation, int(c.enemy_rank[i]), c.k, c.z_scope),
            )
        )
        marks.append(
            (
                _sample_mark(run, i),
                objects[i],
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "priority",
                "yes" if agrees else "no",
                "selected" if relation is Relation.EQUAL else None,
                None,
            )
        )
    scope = "any class" if c.z_scope is ZScope.ALL else "the own class"
    return Table(
        "k-spheres",
        f"Step 1 · k-spheres (Sᵢ, z(Sᵢ, {c.k})) against the enemy spheres — d from the radii",
        (
            "№",
            "Class",
            "k-th neighbour (on the k-sphere)",
            f"z(Sᵢ, {c.k}) · radius",
            "r(Sᵢ) · radius",
            "Neighbours in the k-sphere (ρ ≤ z)",
            "… of the own class",
            "… enemies",
            "Rank e of the nearest enemy",
            "q = min(r, z) / max(r, z)",
            "d = (1 − q) / (1 + q)",
            "= Step 1",
            "Relation of the two spheres",
            "What it means for ERDR",
        ),
        tuple(rows),
        tuple(marks),
        f"d depends only on the ratio q of the two radii (z over {scope}); marked: the spheres "
        "coincide (z = r, d = 0) — these objects come first in the Step 2 queue.",
        sheet=HYPERSPHERES_STEP1,
        header_marks=(
            None,
            "class",
            None,
            "characteristic",
            "characteristic",
            None,
            "own",
            "enemy",
            "characteristic",
            "priority",
            "priority",
            None,
            None,
            None,
        ),
    )


def covering_table(run: ExperimentResult) -> Table:
    """The spheres that contain every object, and its L — sheet *Hyperspheres (Step 1)*.

    The forward view (the sphere of Sᵢ counts its members, g) and the inverse view (the spheres
    that contain Sᵢ can put their owners in L when Sᵢ is selected).
    """
    result = run.result
    c = result.characteristics
    p = profile(run)
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for i in range(c.m):
        spheres = p.spheres_containing(i)
        route = result.routes[i]
        selected_in = route.processed_in
        it = result.iterations[selected_in - 1] if selected_in is not None else None
        possible = possible_cover(int(c.g[i]), len(spheres), result.readings)
        rows.append(
            (
                names[i],
                labels[i],
                int(c.g[i]),
                containing_text(spheres, i, names),
                len(spheres),
                selected_in if selected_in is not None else DASH,
                object_set(it.L, names) if it is not None else f"{DASH} never selected",
                len(it.L) if it is not None else DASH,
                cover_change_text(selected_in, len(it.L) if it else 0, possible, result.readings),
            )
        )
        marks.append((_sample_mark(run, i), objects[i], None, "own", None, None, "L", None, None))
    return Table(
        "covering",
        "Step 1 · Forward and inverse view — the spheres that contain Sᵢ and the L of its turn",
        (
            "№",
            "Class",
            "g(Sᵢ)",
            "Spheres that contain Sᵢ — own-class Sⱼ with ρ(Sⱼ, Sᵢ) < r(Sⱼ)",
            "Number",
            "Selected in iteration",
            "L when Sᵢ was selected (Step 4)",
            "|L| then",
            "Change from the start",
        ),
        tuple(rows),
        tuple(marks),
        "Row of the sphere matrix: the members of the sphere of Sᵢ (g); its column: the spheres "
        "that contain Sᵢ — those still in F (and allowed by A and B) form L at Sᵢ's turn.",
        sheet=HYPERSPHERES_STEP1,
        header_marks=(None, "class", "characteristic", "own", None, None, "L", "L", None),
    )


def _check_mark(passed: bool) -> str:
    return "yes" if passed else "no"


def sphere_checks_table(run: ExperimentResult) -> Table:
    """Border and dense objects, the relations of the spheres and the checks of Step 1."""
    lines = step1_summary(run.result.characteristics, profile(run), run.object_names)
    rows: list[tuple[Cell, ...]] = [(line.label, line.value, line.text) for line in lines]
    marks: list[tuple[str | None, ...]] = [
        (None, None, None) if line.passed is None else (None, *[_check_mark(line.passed)] * 2)
        for line in lines
    ]
    return Table(
        "sphere-checks",
        "Step 1 · Spheres — border and dense objects, relations and checks",
        ("Quantity", "Value", "Objects"),
        tuple(rows),
        tuple(marks),
        "The spheres (r, z) never change during ERDR; Steps 4–5 only change F and lower g.",
        sheet=HYPERSPHERES_STEP1,
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


# ---------------------------------------------------------------- Steps 2–5 as hyperspheres


def iteration_view(run: ExperimentResult, t: int) -> IterationSpheres:
    """Iteration ``t`` of ``run`` as spheres around its selected object (Step 6 past the end)."""
    return iteration_spheres(run.result, run.distances.matrix, t)


def iteration_heading(run: ExperimentResult, t: int) -> str:
    """``Iteration 1  ·  Sᵢ = S₁  ·  L = {S₁, S₂, S₅}  ·  |L| > 1 → Step 5 corrects g``."""
    names = run.object_names
    if t > len(run.result.iterations):
        return iteration_title(t, None)
    it = run.result.iterations[t - 1]
    return iteration_title(t, names[it.selected], object_set(it.L, names), it.decision.value)


def iteration_spheres_table(run: ExperimentResult) -> Table:
    """Every iteration as spheres around Sᵢ — the overview of *Hyperspheres (Iterations)*."""
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for it in run.result.iterations:
        view = iteration_view(run, it.number)
        moved = moves_text([(mv.object, mv.step) for mv in it.moves], names)
        rows.append(
            (
                it.number,
                names[it.selected],
                labels[it.selected],
                float(it.r),
                object_set(view.candidates, names),
                object_set(view.covering, names),
                object_set(view.covering_in_d, names),
                object_set(it.L, names),
                len(it.L),
                it.decision.value + ("" if moved == DASH else f"  ·  {moved}"),
            )
        )
        marks.append(
            (
                None,
                "selected",
                objects[it.selected],
                None,
                None,
                "own",
                "D" if view.covering_in_d else None,
                "L",
                None,
                "moved" if it.moves else None,
            )
        )
    return Table(
        "iteration-spheres",
        "Steps 2–5 · Spheres around the selected Sᵢ — the spheres in F that contain Sᵢ give L",
        (
            "t",
            "Selected Sᵢ",
            "Class",
            "r(Sᵢ)",
            "Own-class objects in F (Sᵢ included) — the candidates for L",
            "… whose sphere contains Sᵢ",
            "In D, but the sphere would contain Sᵢ",
            "L (Step 4)",
            "|L|",
            "Decision  ·  moved to D",
        ),
        tuple(rows),
        tuple(marks),
        "The spheres never change; only F and the counters g do. A sphere of an object already "
        "in D no longer counts, even where it contains Sᵢ.",
        sheet=HYPERSPHERES_ITERATIONS,
        header_marks=(
            None,
            "selected",
            "class",
            "characteristic",
            "own",
            "own",
            "D",
            "L",
            "L",
            None,
        ),
    )


ITERATION_DETAIL_COLUMNS = (
    "Sⱼ",
    "Class",
    "In F",
    "Own class of Sᵢ",
    "ρ(Sⱼ, Sᵢ)",
    "r(Sⱼ)",
    "r(Sⱼ) − ρ(Sⱼ, Sᵢ)",
    "Sphere of Sⱼ contains Sᵢ",
    "g before",
    "g > 1",
    "Allowed (A, B)",
    "Sⱼ ∈ L",
    "g after",
    "Moves to D",
    "Role in this iteration",
)
"""The columns of one iteration's spheres (the workbook's iteration block)."""
_DETAIL_HEADER_MARKS: tuple[str | None, ...] = (
    None,
    "class",
    "F",
    "own",
    None,
    "characteristic",
    None,
    "own",
    "characteristic",
    None,
    "parameter",
    "L",
    "characteristic",
    "D",
    None,
)


def _detail_rows(
    run: ExperimentResult, view: IterationSpheres
) -> tuple[list[tuple[Cell, ...]], list[tuple[str | None, ...]]]:
    """One row per object: its sphere in iteration ``view.number`` (Step 6: the final state)."""
    names = run.object_names
    labels = _labels(run)
    objects = _class_marks(run)
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for j in range(view.m):
        stop = view.stop
        distance: Cell = DASH if stop else float(view.distance[j])
        margin: Cell = DASH if stop else float(view.margin[j])
        moved = int(view.moved_by[j])
        rows.append(
            (
                names[j],
                labels[j],
                int(view.in_f[j]),
                int(view.own_class[j]),
                distance,
                float(view.radius[j]),
                margin,
                int(view.contains[j]),
                int(view.g_before[j]),
                int(view.g_before[j] > 1),
                int(view.allowed[j]),
                int(view.in_l[j]),
                int(view.g_after[j]),
                f"Step {moved}" if moved else DASH,
                view.role(j),
            )
        )
        own = "own" if view.own_class[j] else ("enemy" if not stop else None)
        marks.append(
            (
                "selected" if j == view.selected else None,
                objects[j],
                "F" if view.in_f[j] else "D",
                own,
                None,
                None,
                None,
                "own" if view.contains[j] and view.own_class[j] else None,
                None,
                None,
                "warning" if view.own_class[j] and not view.allowed[j] else None,
                "L" if view.in_l[j] else None,
                "decreased" if view.g_after[j] < view.g_before[j] else None,
                "moved" if moved else None,
                None,
            )
        )
    return rows, marks


def iteration_detail_table(run: ExperimentResult, t: int) -> Table:
    """Every object's sphere in iteration ``t`` — one block of *Hyperspheres (Iterations)*.

    Its :attr:`Table.extra` holds the block's summary (L, counters, moves, sizes, cases, check).
    """
    view = iteration_view(run, t)
    rows, marks = _detail_rows(run, view)
    summary = iteration_summary_lines(run, view)
    return Table(
        f"iteration-spheres-{t}",
        iteration_heading(run, t),
        ITERATION_DETAIL_COLUMNS,
        tuple(rows),
        tuple(marks),
        "Sⱼ ∈ L exactly when Sⱼ is in F, of the class of Sᵢ, its sphere contains Sᵢ "
        "(r(Sⱼ) − ρ(Sⱼ, Sᵢ) > 0), g(Sⱼ) > 1 and the readings A and B allow it.",
        sheet=HYPERSPHERES_ITERATIONS,
        extra=dict(summary),
        header_marks=_DETAIL_HEADER_MARKS,
    )


def iteration_summary_lines(
    run: ExperimentResult, view: IterationSpheres
) -> tuple[tuple[str, str], ...]:
    """The summary of one iteration's spheres (L, counters, moves, sizes, cases, check)."""
    return iteration_summary(run.result, view, run.cases, run.object_names)


def sphere_trace_table(run: ExperimentResult) -> list[Table]:
    """Every object's sphere in every iteration — the blocks of *Hyperspheres (Iterations)*.

    m rows per iteration: built for samples up to :data:`MATRIX_LIMIT` objects only (the
    desktop application shows any iteration of a larger sample on demand).
    """
    if run.result.m > MATRIX_LIMIT:
        return []
    names = run.object_names
    rows: list[tuple[Cell, ...]] = []
    marks: list[tuple[str | None, ...]] = []
    for it in run.result.iterations:
        detail, detail_marks = _detail_rows(run, iteration_view(run, it.number))
        rows += [(it.number, names[it.selected], *row) for row in detail]
        marks += [(None, "selected", *mark) for mark in detail_marks]
    return [
        Table(
            "sphere-trace",
            "Steps 2–5 · Every sphere in every iteration — r(Sⱼ) − ρ(Sⱼ, Sᵢ) > 0 puts Sⱼ in L",
            ("t", "Sᵢ", *ITERATION_DETAIL_COLUMNS),
            tuple(rows),
            tuple(marks),
            "One block per iteration (the workbook's); Sⱼ ∈ L = in F × own class × contains Sᵢ "
            "× g > 1 × allowed by A and B.",
            True,
            HYPERSPHERES_ITERATIONS,
            header_marks=(None, "selected", *_DETAIL_HEADER_MARKS),
        )
    ]


def object_spheres_table(run: ExperimentResult, i: int) -> Table:
    """Everything the two spheres of Sᵢ say, as a list of figures (one object of Step 1)."""
    result = run.result
    c = result.characteristics
    p = profile(run)
    names = run.object_names
    spheres = p.spheres_containing(i)
    route = result.routes[i]
    selected_in = route.processed_in
    it = result.iterations[selected_in - 1] if selected_in is not None else None
    inside = [names[j] for j in c.order[i] if c.spheres[i, j]]
    possible = possible_cover(int(c.g[i]), len(spheres), result.readings)
    rows: list[tuple[Cell, ...]] = [
        ("Class", f"{class_name(int(c.classes[i]))} (class {_labels(run)[i]})"),
        ("r(Sᵢ) — radius of the enemy sphere", float(c.r[i])),
        ("Nearest enemy (on the sphere)", names[c.nearest_enemy[i]]),
        ("Own class strictly inside (Sᵢ excluded)", int(p.own_inside[i])),
        ("Own class on the sphere (not counted)", int(p.own_on_sphere[i])),
        ("g(Sᵢ) — members of the enemy sphere", int(c.g[i])),
        ("Members", ", ".join([f"{names[i]} (itself)", *inside])),
        ("Reading", density_text(int(c.g[i]), int(p.own_on_sphere[i]))),
        (f"z(Sᵢ, {c.k}) — radius of the k-sphere", float(c.z[i])),
        ("k-th neighbour (on the k-sphere)", names[c.kth_neighbour[i]]),
        (
            "Neighbours in the k-sphere · own class · enemies",
            (f"{int(p.k_members[i])} · {int(p.k_own[i])} · {int(p.k_enemies[i])}"),
        ),
        ("Rank e of the nearest enemy", int(c.enemy_rank[i])),
        ("q = min(r, z) / max(r, z)", float(p.ratio[i])),
        ("d(Sᵢ) = (1 − q) / (1 + q)", float(c.d[i])),
        ("Relation of the two spheres", p.relation[i].value),
        ("What it means", relation_meaning(p.relation[i], int(c.enemy_rank[i]), c.k, c.z_scope)),
        ("Step 2 queue position", int(c.position[i])),
        ("Spheres that contain Sᵢ", containing_text(spheres, i, names)),
        ("Selected in iteration", selected_in if selected_in is not None else DASH),
        ("L when Sᵢ was selected", object_set(it.L, names) if it else f"{DASH} never selected"),
        (
            "Change from the start",
            cover_change_text(selected_in, len(it.L) if it else 0, possible, result.readings),
        ),
        ("Sample", "D · training" if route.in_training else "F · validation"),
    ]
    marks: list[tuple[str | None, ...]] = [(None, None)] * len(rows)
    marks[0] = (None, class_mark(int(c.classes[i])))
    for row in (1, 5, 8, 11):
        marks[row] = ("characteristic", None)
    marks[13] = ("priority", "priority")
    marks[6] = (None, "own")
    marks[19] = (None, "L")
    marks[-1] = (None, _sample_mark(run, i))
    return Table(
        f"object-spheres-{i + 1}",
        f"Step 1 · The spheres of {names[i]}",
        ("Figure", "Value"),
        tuple(rows),
        tuple(marks),
        sheet=HYPERSPHERES_STEP1,
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
    ("enemy-spheres", enemy_spheres_table),
    ("k-spheres", k_spheres_table),
    ("covering", covering_table),
    ("sphere-checks", sphere_checks_table),
    ("queue", queue_table),
    ("iterations", iterations_table),
    ("iteration-spheres", iteration_spheres_table),
    ("sphere-trace", sphere_trace_table),
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
