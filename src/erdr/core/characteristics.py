"""Step 1: the auxiliary functions r, g, z, d of every object (sheet *ERDR Characteristics*).

For Sᵢ ∈ K_t (article §1.1):

* r(Sᵢ) = min {ρ(Sᵢ, Sⱼ) : Sⱼ ∉ K_t} — the enemy radius, distance to the nearest enemy;
* g(Sᵢ) = |{Sⱼ ∈ K_t : ρ(Sᵢ, Sⱼ) < r(Sᵢ)}| — own-class objects strictly inside the enemy sphere,
  Sᵢ itself included (ρ(Sᵢ, Sᵢ) = 0 < r(Sᵢ)), so g ≥ 1;
* z(Sᵢ, k) — the distance to the k-th nearest neighbour (Sᵢ excluded; class scope: ADR-003);
* d(Sᵢ) = |z(Sᵢ, k) − r(Sᵢ)| / (z(Sᵢ, k) + r(Sᵢ)) — the priority (smaller = earlier), rounded
  like the distances so that equal values tie exactly.

The Step 2 order — by d, then r, then the index — is static: d and r of a waiting object never
change, so the queue of every iteration is this order restricted to the waiting objects of F.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from erdr.core.arrays import BoolArray, FloatArray, IntArray, freeze_fields
from erdr.core.k_rule import largest_defined_k
from erdr.core.neighbours import neighbour_order
from erdr.core.readings import ZScope
from erdr.errors import AlgorithmUndefinedError
from erdr.notation import class_name

logger = logging.getLogger(__name__)


@dataclass(frozen=True, eq=False)
class Characteristics:
    """The result of Step 1 and the static order of Step 2."""

    k: int
    """k of z(Sᵢ, k)."""
    z_scope: ZScope
    """Class scope of z (ADR-003)."""
    classes: IntArray
    """0-based class index of every object (0 = K1)."""
    order: IntArray
    """Sorted neighbours of every object (any class), shape (m, m − 1)."""
    r: FloatArray
    """Enemy radius r(Sᵢ)."""
    g: IntArray
    """Own-class objects strictly inside the enemy sphere, Sᵢ included — the initial counters."""
    z: FloatArray
    """Distance to the k-th neighbour z(Sᵢ, k)."""
    d: FloatArray
    """Priority d(Sᵢ) = |z − r| / (z + r) (0 when z + r = 0)."""
    nearest_enemy: IntArray
    """The enemy at distance r(Sᵢ) (the first one in the sorted neighbours)."""
    enemy_rank: IntArray
    """1-based rank of the nearest enemy among the sorted neighbours."""
    kth_neighbour: IntArray
    """The neighbour at distance z(Sᵢ, k)."""
    spheres: BoolArray
    """M(i, j) = 1 when Sⱼ is in the class of Sᵢ and ρ(Sᵢ, Sⱼ) < r(Sᵢ); row sums are g."""
    priority: IntArray
    """The objects in Step 2 order: by d ↑, then r ↑, then index ↑."""
    position: IntArray
    """1-based Step 2 position of every object."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        freeze_fields(self)

    @property
    def m(self) -> int:
        """Number of objects."""
        return int(self.r.size)

    def decided_by(self) -> tuple[str, ...]:
        """For every Step 2 position, what orders it before the next object.

        ``d``, ``r`` or ``index``; ``—`` for the last position (sheet *Priority Queue*).
        """
        out: list[str] = []
        for a, b in zip(self.priority[:-1], self.priority[1:], strict=True):
            if self.d[a] != self.d[b]:
                out.append("d")
            elif self.r[a] != self.r[b]:
                out.append("r")
            else:
                out.append("index")
        return (*out, "—") if self.m else ()


def priority_order(d: FloatArray, r: FloatArray) -> IntArray:
    """Objects by d ↑, then r ↑, then index ↑ — Step 2 of the article."""
    index = np.arange(d.size)
    return np.lexsort((index, r, d)).astype(np.int64)


def compute_characteristics(
    matrix: FloatArray,
    classes: IntArray,
    k: int,
    *,
    z_scope: ZScope | str = ZScope.ALL,
    decimals: int = 10,
) -> Characteristics:
    """Step 1 of ERDR: r, g, z and d of every object, and the static Step 2 order.

    Args:
        matrix: Distances ρ of E₀ (Step 0), shape (m, m).
        classes: 0-based class index of every object.
        k: k of z(Sᵢ, k).
        z_scope: Neighbours of any class (default) or of the own class only.
        decimals: Rounding of d (the distances' rounding in the workbook).

    Raises:
        AlgorithmUndefinedError: The sample has fewer than two classes (no enemies), or k is
            larger than the number of neighbours some object has in the scope of z.
    """
    scope = ZScope(z_scope)
    y = np.asarray(classes, dtype=np.int64)
    m = y.size
    sizes = np.bincount(y) if m else np.zeros(0, dtype=np.int64)
    present = sizes[sizes > 0]
    if present.size < 2:
        raise AlgorithmUndefinedError(
            "ERDR needs at least two classes: with one class no object has an enemy, so the "
            "enemy radius r(Sᵢ) does not exist"
        )
    largest = largest_defined_k(present.tolist(), scope)
    if not 1 <= k <= largest:
        where = "objects of any class" if scope is ZScope.ALL else "own-class objects"
        smallest = class_name(int(np.flatnonzero(sizes == present.min())[0]))
        detail = (
            f" ({smallest} has {int(present.min())} objects)" if scope is ZScope.OWN_CLASS else ""
        )
        raise AlgorithmUndefinedError(
            f"z(Sᵢ, k) needs k between 1 and {largest} here: every object has at most {largest} "
            f"neighbours among the {where}{detail}; got k = {k}"
        )

    order = neighbour_order(matrix)
    same = y[:, None] == y[None, :]
    z_order = neighbour_order(matrix, allowed=same) if scope is ZScope.OWN_CLASS else order

    r = np.empty(m)
    g = np.empty(m, dtype=np.int64)
    z = np.empty(m)
    d = np.empty(m)
    nearest_enemy = np.empty(m, dtype=np.int64)
    enemy_rank = np.empty(m, dtype=np.int64)
    kth = np.empty(m, dtype=np.int64)
    for i in range(m):
        row = order[i]
        enemy_places = np.flatnonzero(y[row] != y[i])
        first = int(enemy_places[0])
        nearest_enemy[i] = row[first]
        enemy_rank[i] = first + 1
        r[i] = matrix[i, row[first]]
        kth[i] = z_order[i, k - 1]
        z[i] = matrix[i, kth[i]]
    spheres = same & (matrix < r[:, None])
    g[:] = spheres.sum(axis=1)
    total = z + r
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(total > 0.0, np.abs(z - r) / np.where(total > 0.0, total, 1.0), 0.0)
    d[:] = np.round(ratio, decimals)
    priority = priority_order(d, r)
    position = np.empty(m, dtype=np.int64)
    position[priority] = np.arange(1, m + 1)
    logger.info("characteristics computed", extra={"m": m, "k": k, "z_scope": scope.value})
    return Characteristics(
        k=k,
        z_scope=scope,
        classes=y.copy(),
        order=order,
        r=r,
        g=g,
        z=z,
        d=d,
        nearest_enemy=nearest_enemy,
        enemy_rank=enemy_rank,
        kth_neighbour=kth,
        spheres=spheres,
        priority=priority,
        position=position,
    )
