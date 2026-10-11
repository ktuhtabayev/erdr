r"""Steps 1–5 as hyperspheres (sheets *Hyperspheres (Step 1)*, *Hyperspheres (Iterations)*).

Step 1 in geometric terms: every object Sᵢ ∈ K_t is the centre of two spheres of the metric ρ.

The enemy sphere (Sᵢ, r(Sᵢ))
    open, through the nearest enemy: no enemy lies strictly inside it, and g(Sᵢ) counts the
    own-class objects strictly inside, Sᵢ included. Objects on the sphere (ρ = r) are not
    counted — the closed count ρ ≤ r of other k-NN analyses differs from g exactly by them.
The k-sphere (Sᵢ, z(Sᵢ, k))
    closed, through the k-th neighbour.

d(Sᵢ) compares the two radii only: with q = min(r, z) / max(r, z), d = (1 − q) / (1 + q). It does
not change when every distance is scaled; the Step 2 queue starts with the objects whose two
spheres are closest in size, and on the radius plane (r, z) d is constant along every line through
the origin. z = r ⇔ d = 0; when z is taken over every class, z < r gives g ≥ k + 1 and z > r gives
g ≤ k − 1.

Steps 2–5 never change a sphere — only F and the counters g. Sⱼ is in L exactly when Sⱼ is in F,
of the class of the selected Sᵢ, its enemy sphere contains Sᵢ (ρ(Sⱼ, Sᵢ) < r(Sⱼ)), g(Sⱼ) > 1 and
the readings A and B allow it: the "inverse view" of the sphere matrix (its column of Sᵢ).

The diagrams place the other objects around a centre at their true distance ρ, in the centre's
neighbour order clockwise from the top, at equal angles — only the distance to the centre is
meaningful (the workbook's *Hypersphere Data*). Everything here is pure and computed from Step 1
and the trace; nothing reads a file.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from erdr.core.algorithm import ERDRResult
from erdr.core.arrays import BoolArray, FloatArray, IntArray, freeze_fields
from erdr.core.cases import SHORT_TITLES, CaseResult, cases_in_iteration
from erdr.core.characteristics import Characteristics
from erdr.core.readings import BlockedCover, Readings, SelfInL, ZScope
from erdr.notation import DASH, changes_text, moves_text, object_set

RATIO_LINES = (0.0, 0.1, 0.2, 0.3)
"""Priorities d drawn as lines through the origin of the radius plane (the workbook's)."""
RAY_FACTOR = 1.12
"""Rays of the radius plane reach 1.12 · the largest radius (the workbook's)."""


class Relation(StrEnum):
    """How the k-sphere of an object relates to its enemy sphere."""

    INSIDE = "z < r · k-sphere inside the enemy sphere"
    """z < r: the k nearest neighbours are inside the enemy sphere."""
    EQUAL = "z = r · the two spheres coincide"
    """z = r: d = 0, the object comes first in the Step 2 queue."""
    OUTSIDE = "z > r · the enemy lies inside the k-sphere"
    """z > r: the nearest enemy comes before the k-th neighbour."""


def priority_from_ratio(q: float) -> float:
    """The priority d = (1 − q) / (1 + q) of the radius ratio q = min(r, z) / max(r, z)."""
    return (1.0 - q) / (1.0 + q)


def ratio_from_priority(d: float) -> float:
    """The radius ratio q = (1 − d) / (1 + d) of a priority d (the slope z / r below z = r)."""
    return (1.0 - d) / (1.0 + d)


@dataclass(frozen=True, eq=False)
class SphereProfile:
    """Step 1 as spheres: what the enemy sphere and the k-sphere of every object contain."""

    own_inside: IntArray
    """Own-class objects strictly inside the enemy sphere, Sᵢ excluded (g − 1)."""
    own_on_sphere: IntArray
    """Own-class objects on the enemy sphere (ρ = r): not counted in g."""
    enemies_inside: IntArray
    """Enemies strictly inside the enemy sphere — 0 by the definition of r."""
    enemies_on_sphere: IntArray
    """Enemies on the enemy sphere (ρ = r) — at least the nearest enemy."""
    closed_count: IntArray
    """Every object with ρ ≤ r, Sᵢ included (the closed count of other k-NN analyses)."""
    on_sphere: IntArray
    """Every object on the sphere (ρ = r) — Sᵢ itself too when r = 0."""
    self_inside: BoolArray
    """Sᵢ lies inside its own sphere: ρ(Sᵢ, Sᵢ) = 0 < r(Sᵢ) — false only when r = 0."""
    k_members: IntArray
    """Neighbours in the closed k-sphere (ρ ≤ z), Sᵢ excluded."""
    k_own: IntArray
    """… of the own class."""
    k_enemies: IntArray
    """… enemies."""
    ratio: FloatArray
    """q = min(r, z) / max(r, z) (1 when both are 0)."""
    d_from_ratio: FloatArray
    """(1 − q) / (1 + q), rounded like d — equals d(Sᵢ)."""
    relation: tuple[Relation, ...]
    """z < r, z = r or z > r for every object."""
    containing: BoolArray
    """containing[i, j]: the enemy sphere of Sⱼ contains Sᵢ — the transposed sphere matrix."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        freeze_fields(self)

    @property
    def m(self) -> int:
        """Number of objects."""
        return int(self.own_inside.size)

    @property
    def g_from_spheres(self) -> IntArray:
        """The own class strictly inside, and Sᵢ when r > 0 — g of Step 1 counted on the spheres."""
        counted: IntArray = self.own_inside + self.self_inside.astype(np.int64)
        return counted

    @property
    def strictly_inside(self) -> IntArray:
        """The closed count less the objects on the sphere — g again (no enemy is inside)."""
        inside: IntArray = self.closed_count - self.on_sphere
        return inside

    def spheres_containing(self, i: int) -> tuple[int, ...]:
        """The objects whose enemy sphere contains Sᵢ, Sᵢ included (ascending index)."""
        return tuple(int(j) for j in np.flatnonzero(self.containing[i]))

    def objects_with(self, relation: Relation) -> tuple[int, ...]:
        """The objects whose two spheres stand in ``relation`` (ascending index)."""
        return tuple(i for i, found in enumerate(self.relation) if found is relation)


def sphere_profile(
    matrix: FloatArray, characteristics: Characteristics, *, decimals: int = 10
) -> SphereProfile:
    """What the enemy sphere and the k-sphere of every object contain (Step 1 as spheres).

    Args:
        matrix: Distances ρ of E₀ (Step 0), shape (m, m).
        characteristics: Step 1 of the same matrix.
        decimals: Rounding of d (the rounding of Step 1).
    """
    c = characteristics
    y = c.classes
    same = y[:, None] == y[None, :]
    other = ~np.eye(c.m, dtype=bool)
    r = c.r[:, None]
    z = c.z[:, None]
    inside = matrix < r
    on = matrix == r
    within_k = (matrix <= z) & other
    largest = np.maximum(c.r, c.z)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(largest > 0.0, np.minimum(c.r, c.z) / np.where(largest > 0, largest, 1), 1)
    relation = tuple(
        Relation.EQUAL if zi == ri else (Relation.INSIDE if zi < ri else Relation.OUTSIDE)
        for ri, zi in zip(c.r.tolist(), c.z.tolist(), strict=True)
    )
    return SphereProfile(
        own_inside=(same & inside & other).sum(axis=1).astype(np.int64),
        own_on_sphere=(same & on & other).sum(axis=1).astype(np.int64),
        enemies_inside=(~same & inside).sum(axis=1).astype(np.int64),
        enemies_on_sphere=(~same & on).sum(axis=1).astype(np.int64),
        closed_count=(matrix <= r).sum(axis=1).astype(np.int64),
        on_sphere=on.sum(axis=1).astype(np.int64),
        self_inside=c.r > 0.0,
        k_members=within_k.sum(axis=1).astype(np.int64),
        k_own=(within_k & same).sum(axis=1).astype(np.int64),
        k_enemies=(within_k & ~same).sum(axis=1).astype(np.int64),
        ratio=ratio.astype(np.float64),
        d_from_ratio=np.round((1.0 - ratio) / (1.0 + ratio), decimals),
        relation=relation,
        containing=c.spheres.T.copy(),
    )


def containing_text(spheres: Sequence[int], i: int, names: Sequence[str]) -> str:
    """``S₁, S₂ (itself), S₅`` — the spheres that contain Sᵢ, in ascending index."""
    return ", ".join(f"{names[j]} (itself)" if j == i else names[j] for j in spheres)


def density_text(g: int, own_on_sphere: int) -> str:
    """What the enemy sphere says about an object (column *Reading* of the workbook)."""
    if g == 0:
        return "empty sphere: r = 0, an enemy at the same point"
    if g == 1:
        return "border object — it can never cover another object"
    if own_on_sphere > 0:
        return "dense; own-class objects on the sphere are not counted"
    inside = g - 1
    return f"dense: {inside} own-class object{'' if inside == 1 else 's'} inside"


def relation_meaning(relation: Relation, enemy_rank: int, k: int, z_scope: ZScope) -> str:
    """What the relation of the two spheres means for ERDR (column *What it means*).

    With z over every class the rank e of the nearest enemy decides: e = k ⇔ z = r. With the
    own-class z (not the literal reading) z > r only bounds g by k.
    """
    if z_scope is ZScope.OWN_CLASS:
        return {
            Relation.EQUAL: "the k-th own-class neighbour is on the enemy sphere → d = 0",
            Relation.INSIDE: "the k nearest own-class objects are inside → g ≥ k + 1",
            Relation.OUTSIDE: "fewer than k own-class objects inside → g ≤ k",
        }[relation]
    if relation is Relation.EQUAL:
        if enemy_rank == k:
            return "e = k: the nearest enemy is the k-th neighbour → d = 0"
        return "tie at distance r: the k-th neighbour is on the enemy sphere → d = 0"
    if relation is Relation.INSIDE:
        return "e > k: the k nearest are own class → g ≥ k + 1"
    return "e < k: the enemy comes before the k-th → g ≤ k − 1"


@dataclass(frozen=True)
class SummaryLine:
    """One line of the Step 1 sphere summary: a count with its objects, or a check."""

    label: str
    value: int | str
    text: str
    """The objects (``S₄, S₆`` or ``—``), or the outcome of a check (``✓ …`` / ``✗ …``)."""
    passed: bool | None = None
    """``None`` for a count; whether a check holds."""


def step1_summary(
    characteristics: Characteristics, profile: SphereProfile, names: Sequence[str]
) -> tuple[SummaryLine, ...]:
    """Border and dense objects, the relations of the two spheres, and four checks of Step 1."""
    c, p, m = characteristics, profile, characteristics.m

    def listed(indices: tuple[int, ...]) -> str:
        return ", ".join(names[i] for i in indices) if indices else DASH

    border = tuple(int(i) for i in np.flatnonzero(c.g == 1))
    dense = tuple(int(i) for i in np.flatnonzero(c.g >= 2))
    lines = [
        SummaryLine(
            "Border objects — g = 1, no own-class object inside the enemy sphere",
            len(border),
            listed(border),
        ),
        SummaryLine(
            "Dense objects — g ≥ 2 (only these can cover another object in Step 4)",
            len(dense),
            listed(dense),
        ),
    ]
    for label, relation in (
        ("Spheres that coincide — z = r, d = 0 (first in the queue)", Relation.EQUAL),
        ("k-sphere inside the enemy sphere — z < r", Relation.INSIDE),
        ("Nearest enemy inside the k-sphere — z > r", Relation.OUTSIDE),
    ):
        found = p.objects_with(relation)
        lines.append(SummaryLine(label, len(found), listed(found)))
    g_ok = int(np.sum(c.g == p.g_from_spheres))
    enemies = int(p.enemies_inside.sum())
    d_ok = int(np.sum(np.abs(p.d_from_ratio - c.d) < 1e-9))
    closed_ok = int(np.sum(p.strictly_inside == c.g))
    checks: tuple[tuple[str, int | str, bool, str, str], ...] = (
        (
            "Check · g from the spheres = g of Step 1",
            f"{g_ok} of {m}",
            g_ok == m,
            "every count agrees with ERDR Characteristics",
            "a count differs",
        ),
        (
            "Check · no enemy strictly inside any enemy sphere (r is the nearest-enemy distance)",
            enemies,
            enemies == 0,
            "by the definition of r",
            "an enemy lies inside",
        ),
        (
            "Check · d from the radius ratio = d of Step 1",
            f"{d_ok} of {m}",
            d_ok == m,
            "d = (1 − q)/(1 + q) for every object",
            "a value differs",
        ),
        (
            "Check · ML 7.20 closed count − objects on the sphere = g",
            f"{closed_ok} of {m}",
            closed_ok == m,
            "the two definitions differ only by the boundary",
            "a value differs",
        ),
    )
    for label, value, ok, good, bad in checks:
        lines.append(SummaryLine(label, value, f"✓ {good}" if ok else f"✗ {bad}", ok))
    return tuple(lines)


def possible_cover(g: int, containing: int, readings: Readings) -> int:
    """Spheres that could put their owners in L when Sᵢ is selected, as at the start.

    Every sphere that contains Sᵢ (Sᵢ's own included) — except Sᵢ's own when g(Sᵢ) = 1 or
    reading A leaves Sᵢ out of its L.
    """
    own_left_out = g == 1 or readings.self_in_l is SelfInL.EXCLUDED
    return containing - int(own_left_out)


def cover_change_text(
    selected_in: int | None, size_of_l: int, possible: int, readings: Readings
) -> str:
    """How L at Sᵢ's turn compares with the spheres that contained Sᵢ at the start."""
    if selected_in is None:
        return "moved to D by Step 5 before its turn"
    if size_of_l < possible:
        why = (
            " or were processed (B = 2)"
            if readings.blocked_cover is BlockedCover.DROPPED
            else " first"
        )
        return f"{possible} possible at the start — covering objects left F{why}"
    return "the same spheres as at the start"


# ---------------------------------------------------------------- Steps 2–5 as spheres


class Role(StrEnum):
    """What an object's sphere does in one iteration (column *Role in this iteration*)."""

    SELECTED_IN_L = "Sᵢ (selected) · own sphere with g > 1 → in L"
    SELECTED_BORDER = "Sᵢ (selected) · g = 1 → not in its own L"
    SELECTED_EXCLUDED = "Sᵢ (selected) · reading A = 2 → not in its own L"
    ENEMY = "enemy (other class)"
    ENEMY_IN_D = "enemy (other class) · in D"
    D_CONTAINS = "in D — its sphere contains Sᵢ but no longer counts"
    D_APART = "in D — its sphere does not reach Sᵢ"
    F_APART = "own class in F — its sphere does not reach Sᵢ (ρ ≥ r)"
    IN_L = "own class in F — its sphere contains Sᵢ → in L"
    EXCLUDED = "own class in F — contains Sᵢ, excluded by reading B = 2 (processed)"
    FINAL_F = "in F — stays in the validation sample"
    FINAL_D = "in D — training sample"


@dataclass(frozen=True, eq=False)
class IterationSpheres:
    """One iteration around the selected Sᵢ — or Step 6 when ``selected`` is ``None``."""

    number: int
    """1-based iteration t (past the last iteration: Step 6)."""
    selected: int | None
    """0-based index of Sᵢ; ``None`` when the queue is empty (Step 6)."""
    in_f: BoolArray
    """In F before the iteration."""
    processed: BoolArray
    """Processed (blocked) before the iteration."""
    own_class: BoolArray
    """Of the class of Sᵢ (Sᵢ included); all ``False`` at Step 6."""
    distance: FloatArray
    """ρ(Sⱼ, Sᵢ) (NaN at Step 6)."""
    radius: FloatArray
    """r(Sⱼ) — the radius of the enemy sphere of Sⱼ."""
    contains: BoolArray
    """The enemy sphere of Sⱼ contains Sᵢ: ρ(Sⱼ, Sᵢ) < r(Sⱼ) (never for an enemy)."""
    g_before: IntArray
    """Counters before the iteration."""
    allowed: BoolArray
    """Readings A (Sᵢ itself) and B (processed Sⱼ) let Sⱼ into L."""
    in_l: BoolArray
    """Sⱼ ∈ L (Step 4)."""
    g_after: IntArray
    """Counters after the iteration."""
    moved_by: IntArray
    """4 or 5 when Sⱼ moves to D in this iteration, else 0."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        freeze_fields(self)

    @property
    def m(self) -> int:
        """Number of objects."""
        return int(self.in_f.size)

    @property
    def stop(self) -> bool:
        """The queue is empty: Step 6."""
        return self.selected is None

    @property
    def margin(self) -> FloatArray:
        """r(Sⱼ) − ρ(Sⱼ, Sᵢ): positive exactly when the sphere of Sⱼ contains Sᵢ."""
        return self.radius - self.distance

    @property
    def candidates(self) -> tuple[int, ...]:
        """Own-class objects in F, Sᵢ included — the candidates for L."""
        return tuple(int(j) for j in np.flatnonzero(self.own_class & self.in_f))

    @property
    def covering(self) -> tuple[int, ...]:
        """Candidates whose sphere contains Sᵢ."""
        return tuple(int(j) for j in np.flatnonzero(self.own_class & self.in_f & self.contains))

    @property
    def covering_in_d(self) -> tuple[int, ...]:
        """Own-class objects already in D whose sphere would contain Sᵢ."""
        return tuple(int(j) for j in np.flatnonzero(self.own_class & ~self.in_f & self.contains))

    @property
    def members(self) -> tuple[int, ...]:
        """L (ascending index)."""
        return tuple(int(j) for j in np.flatnonzero(self.in_l))

    def sphere_test(self) -> BoolArray:
        """L rebuilt from the sphere test alone: F ∩ K_t, r − ρ > 0, g > 1, allowed by A and B."""
        test: BoolArray = (
            self.in_f & self.own_class & (self.margin > 0.0) & (self.g_before > 1) & self.allowed
        )
        return test

    def role(self, j: int) -> str:
        """What the sphere of Sⱼ does in this iteration, with its move to D."""
        if self.selected is None:
            return Role.FINAL_F.value if self.in_f[j] else Role.FINAL_D.value
        if j == self.selected:
            if self.in_l[j]:
                found = Role.SELECTED_IN_L
            elif self.g_before[j] <= 1:
                found = Role.SELECTED_BORDER
            else:
                found = Role.SELECTED_EXCLUDED
        elif not self.own_class[j]:
            found = Role.ENEMY if self.in_f[j] else Role.ENEMY_IN_D
        elif not self.in_f[j]:
            found = Role.D_CONTAINS if self.contains[j] else Role.D_APART
        elif not self.contains[j]:
            found = Role.F_APART
        else:
            found = Role.IN_L if self.in_l[j] else Role.EXCLUDED
        moved = int(self.moved_by[j])
        return found.value + (f"  ·  moves to D (Step {moved})" if moved else "")


def iteration_spheres(result: ERDRResult, matrix: FloatArray, t: int) -> IterationSpheres:
    """Iteration ``t`` (1-based) as spheres around the selected object.

    ``t`` past the last iteration gives the final state (Step 6), as the workbook's later blocks.

    Raises:
        IndexError: ``t`` is smaller than 1.
    """
    if t < 1:
        raise IndexError(f"iteration {t} does not exist (iterations start at 1)")
    c = result.characteristics
    m = result.m
    last = len(result.iterations)
    before = result.state_after(min(t - 1, last))
    if t > last:
        final = result.state_after(last)
        nothing = np.zeros(m, dtype=bool)
        return IterationSpheres(
            number=t,
            selected=None,
            in_f=final.in_f.copy(),
            processed=final.processed.copy(),
            own_class=nothing,
            distance=np.full(m, np.nan),
            radius=c.r.copy(),
            contains=nothing.copy(),
            g_before=final.g.copy(),
            allowed=nothing.copy(),
            in_l=nothing.copy(),
            g_after=final.g.copy(),
            moved_by=np.zeros(m, dtype=np.int64),
        )
    it = result.iterations[t - 1]
    i = it.selected
    readings = result.readings
    index = np.arange(m)
    allowed = np.where(
        index == i,
        readings.self_in_l is SelfInL.INCLUDED,
        (readings.blocked_cover is BlockedCover.KEPT) | ~before.processed,
    )
    in_l = np.zeros(m, dtype=bool)
    in_l[list(it.L)] = True
    after = result.state_after(t)
    moved_by = np.zeros(m, dtype=np.int64)
    for move in it.moves:
        moved_by[move.object] = move.step
    distance = matrix[:, i].astype(np.float64)
    return IterationSpheres(
        number=t,
        selected=i,
        in_f=before.in_f.copy(),
        processed=before.processed.copy(),
        own_class=c.classes == c.classes[i],
        distance=distance,
        radius=c.r.copy(),
        contains=distance < c.r,
        g_before=before.g.copy(),
        allowed=allowed.astype(bool),
        in_l=in_l,
        g_after=after.g.copy(),
        moved_by=moved_by,
    )


# ---------------------------------------------------------------- the layout of the diagrams


@dataclass(frozen=True, eq=False)
class RadialLayout:
    """The other objects around a centre: true distance ρ, neighbour order clockwise from the top.

    Only the distance from the centre is meaningful; the direction is a convention (equal steps
    of 2π / (m − 1)), so distances between two outer objects are not drawn.
    """

    centre: int
    """0-based index of the centre."""
    rank: IntArray
    """Rank of every object in the centre's neighbour order (0 for the centre)."""
    angle: FloatArray
    """Angle θ of every object (0 for the centre)."""
    distance: FloatArray
    """ρ(centre, Sⱼ)."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        freeze_fields(self)

    def xy(self, scale: float = 1.0) -> tuple[FloatArray, FloatArray]:
        """Positions (ρ · cos θ, ρ · sin θ) / ``scale``."""
        radius = self.distance / scale
        x: FloatArray = radius * np.cos(self.angle)
        y: FloatArray = radius * np.sin(self.angle)
        return x, y


def angle_step(m: int) -> float:
    """The angle between two neighbours of one centre: 2π / (m − 1)."""
    return 2.0 * math.pi / max(m - 1, 1)


def radial_layout(
    matrix: FloatArray, characteristics: Characteristics, centre: int
) -> RadialLayout:
    """Place every object around ``centre`` at its true distance, in neighbour order.

    The nearest neighbour stands at the top (θ = π/2), the next ones clockwise at equal steps.
    """
    m = characteristics.m
    rank = np.zeros(m, dtype=np.int64)
    rank[characteristics.order[centre]] = np.arange(1, m)
    angle = np.where(rank > 0, math.pi / 2.0 - (rank - 1) * angle_step(m), 0.0)
    return RadialLayout(
        centre=centre,
        rank=rank,
        angle=angle.astype(np.float64),
        distance=matrix[centre].astype(np.float64),
    )


def strip_levels(characteristics: Characteristics) -> IntArray:
    """The level of every object's neighbourhood strip: m for the first in the queue, 1 last."""
    levels: IntArray = characteristics.m + 1 - characteristics.position
    return levels


def ray_length(characteristics: Characteristics) -> float:
    """How far the lines of the radius plane reach: 1.12 · the largest radius r or z."""
    if characteristics.m == 0:
        return 0.0
    return RAY_FACTOR * float(max(characteristics.r.max(), characteristics.z.max()))


def ratio_line(d: float, length: float) -> tuple[tuple[float, float], tuple[float, float]]:
    """End points of the two lines of priority ``d`` on the radius plane (z < r, then z > r).

    Each line starts at the origin and stops where one coordinate reaches ``length``.
    """
    q = ratio_from_priority(d)
    return (length, q * length), (q * length, length)


def coinciding_points(characteristics: Characteristics) -> list[tuple[int, ...]]:
    """Objects that share a point (r, z) of the radius plane, each group in ascending index."""
    groups: dict[tuple[float, float], list[int]] = {}
    points = zip(characteristics.r.tolist(), characteristics.z.tolist(), strict=True)
    for i, key in enumerate(points):
        groups.setdefault(key, []).append(i)
    return [tuple(members) for members in groups.values()]


# ---------------------------------------------------------------- titles (the workbook's wording)

SEPARATOR = "  ·  "
"""Between the parts of a diagram title."""


def object_title(name: str, label: str, g: int, d: float, position: int) -> str:
    """``S₁ (class 2)  ·  g = 3  ·  d = 0.000  ·  queue 1`` — the title of an object's spheres."""
    parts = (f"{name} (class {label})", f"g = {g}", f"d = {d:.3f}", f"queue {position}")
    return SEPARATOR.join(parts)


def iteration_title(t: int, selected: str | None, members: str = "", decision: str = "") -> str:
    """``Iteration 1  ·  Sᵢ = S₁  ·  L = {S₁, S₂, S₅}  ·  |L| > 1 → Step 5 corrects g``.

    ``selected`` is ``None`` when the queue is empty (Step 6).
    """
    if selected is None:
        return f"Iteration {t}{SEPARATOR}queue empty → Step 6 (stop)"
    return SEPARATOR.join((f"Iteration {t}", f"Sᵢ = {selected}", f"L = {members}", decision))


WIDE = "   ·   "
"""Between the parts of a summary line."""


def iteration_summary(
    result: ERDRResult,
    view: IterationSpheres,
    cases: tuple[CaseResult, ...],
    names: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """The summary of an iteration's spheres, line by line (the workbook's block summary)."""
    if view.selected is None:
        final = result.iterations[-1] if result.iterations else None
        sizes = (
            f"|F| = {final.f_size}{WIDE}|D| = {final.d_size}{WIDE}"
            f"objects left in the queue: {final.queue_left}"
            if final is not None
            else f"|F| = {result.m}{WIDE}|D| = 0{WIDE}objects left in the queue: 0"
        )
        return (
            ("Spheres that contain Sᵢ (own class, in F)", DASH),
            ("Own-class spheres in D that would contain Sᵢ", DASH),
            ("Step 4 · L  ·  |L|  ·  decision", f"{DASH} (queue empty)"),
            ("Step 5 · counters g: before → after", DASH),
            ("Moved to D", DASH),
            ("After the iteration", sizes),
            ("Cases of the Case Checklist shown here", DASH),
            ("Check · L from the sphere test r − ρ > 0", DASH),
        )
    it = result.iterations[view.number - 1]
    numbers = cases_in_iteration(cases, view.number)
    shown = WIDE.join(f"{n} {SHORT_TITLES[n]}" for n in numbers) if numbers else DASH
    agrees = bool(np.array_equal(view.sphere_test(), view.in_l))
    return (
        ("Spheres that contain Sᵢ (own class, in F)", object_set(view.covering, names)),
        ("Own-class spheres in D that would contain Sᵢ", object_set(view.covering_in_d, names)),
        (
            "Step 4 · L  ·  |L|  ·  decision",
            f"{object_set(it.L, names)}{WIDE}|L| = {len(it.L)}{WIDE}{it.decision.value}",
        ),
        (
            "Step 5 · counters g: before → after",
            changes_text([(ch.object, ch.before, ch.after) for ch in it.changes], names),
        ),
        ("Moved to D", moves_text([(mv.object, mv.step) for mv in it.moves], names)),
        (
            "After the iteration",
            (
                f"|F| = {it.f_size}{WIDE}|D| = {it.d_size}{WIDE}"
                f"objects left in the queue: {it.queue_left}"
            ),
        ),
        ("Cases of the Case Checklist shown here", shown),
        (
            "Check · L from the sphere test r − ρ > 0",
            "✓ the sphere test gives exactly the L of ERDR Iterations" if agrees else "✗ differs",
        ),
    )
