r"""Steps 2–6 of ERDR: the queue, the set L, blocking, the counter corrections and the result.

One iteration (article §1.1, reading switches in :mod:`.readings`):

Step 2
    queue = objects of F with d ≥ 0 in the static order d ↑, r ↑, index ↑; an empty queue
    ends the loop (Step 6).
Step 3
    Sᵢ = the first object of the queue.
Step 4
    L = {Sⱼ ∈ F ∩ K_t | ρ(Sⱼ, Sᵢ) < r(Sⱼ) and g(Sⱼ) > 1} (readings A and B); block Sᵢ by
    d(Sᵢ) ← −(d(Sᵢ) + ε); if |L| = 1, Sᵢ moves from F to D.
Step 5
    if |L| > 1, every Sⱼ ∈ L (ascending index) loses 1 from g(Sⱼ), and Sⱼ moves to D when
    g(Sⱼ) = 1 (reading C: go back to Step 2 after the whole set, or right after the first move).
Step 6
    D is the training sample, F = E₀ \ D the validation sample.

|L| = 0 is not described in the article; read literally, Sᵢ is only blocked and stays in F.

Every iteration blocks one object of the queue, so the loop ends after at most m iterations.
The trace (:class:`Iteration`) records only what changes; :meth:`ERDRResult.state_after` replays
it into the full state of any iteration, as the workbook's *ERDR Iterations* blocks show it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from erdr.core.arrays import BoolArray, FloatArray, IntArray, readonly
from erdr.core.characteristics import Characteristics, compute_characteristics
from erdr.core.readings import LITERAL, BlockedCover, Readings, SelfInL, Step5Return
from erdr.errors import AlgorithmUndefinedError

logger = logging.getLogger(__name__)

DEFAULT_EPSILON = 0.001
"""ε of the workbook; any ε > 0 gives the same result (the value only marks a processed object)."""


class Decision(StrEnum):
    """What Step 4 decided for the selected object, by the size of L."""

    MOVE = "|L| = 1 → Sᵢ moves to D"
    """Step 4: exactly one object covers Sᵢ."""
    CORRECT = "|L| > 1 → Step 5 corrects g"
    """Step 5: every member of L loses 1 from its counter."""
    STAY = "|L| = 0 → Sᵢ is only blocked and stays in F"
    """Not described in the article; literally Sᵢ stays in F."""


@dataclass(frozen=True)
class CounterChange:
    """Step 5: g(Sⱼ) before → after one decrease."""

    object: int
    """0-based index of Sⱼ."""
    before: int
    """g(Sⱼ) before the decrease."""
    after: int
    """g(Sⱼ) after the decrease."""

    @property
    def moved(self) -> bool:
        """Whether Sⱼ moved to D (its counter fell to 1)."""
        return self.after == 1


@dataclass(frozen=True)
class Move:
    """An object that moved from F to D."""

    object: int
    """0-based index."""
    step: int
    """4 (|L| = 1, the selected object) or 5 (its counter fell to 1)."""


@dataclass(frozen=True)
class Iteration:
    """One pass through Steps 2–5 (one block of the sheet *ERDR Iterations*)."""

    number: int
    """1-based iteration t."""
    selected: int
    """0-based index of the selected object Sᵢ (Step 3)."""
    queue_length: int
    """Objects in the Step 2 queue, Sᵢ included."""
    d: float
    """d(Sᵢ) when it was selected."""
    r: float
    """r(Sᵢ)."""
    covering: tuple[int, ...]
    """Objects of F ∩ K_t whose enemy sphere contains Sᵢ: ρ(Sⱼ, Sᵢ) < r(Sⱼ) (ascending)."""
    excluded: tuple[int, ...]
    """Covering objects with g > 1 left out of L by reading A (Sᵢ itself) or B (processed)."""
    L: tuple[int, ...]
    """The set L of Step 4 (ascending index)."""
    decision: Decision
    """Step 4 / Step 5 outcome by |L|."""
    blocked_d: float
    """The value −(d(Sᵢ) + ε) that blocks Sᵢ."""
    changes: tuple[CounterChange, ...] = ()
    """Step 5 counter decreases, in the order they happened."""
    moves: tuple[Move, ...] = ()
    """Objects moved to D in this iteration."""
    stopped_early: bool = False
    """Reading C = 2: Step 5 went back to Step 2 before the end of L."""
    f_size: int = 0
    """|F| after the iteration."""
    d_size: int = 0
    """|D| after the iteration."""
    queue_left: int = 0
    """Objects still waiting in the queue after the iteration."""


@dataclass(frozen=True)
class ObjectRoute:
    """How an object went through the run (sheet *Training & Validation*)."""

    processed_in: int | None
    """Iteration in which it was selected (Step 3), ``None`` if never."""
    entered_d_in: int | None
    """Iteration in which it moved to D, ``None`` if it stays in F."""
    entered_by: int | None
    """4 or 5 — the step that moved it — or ``None``."""
    counter_decreases: int
    """How often Step 5 lowered its counter over the whole run."""

    @property
    def in_training(self) -> bool:
        """Whether the object ends in the training sample D."""
        return self.entered_d_in is not None


@dataclass(frozen=True)
class State:
    """The full state after an iteration (replayed from the trace)."""

    in_f: BoolArray
    """Object is in the working set F."""
    processed: BoolArray
    """Object was selected (blocked: d < 0)."""
    g: IntArray
    """Current counters."""
    d: FloatArray
    """Current d (−(d + ε) once processed)."""

    @property
    def in_d(self) -> BoolArray:
        """Object is in the training sample D."""
        return ~self.in_f

    @property
    def in_queue(self) -> BoolArray:
        """Object waits in the Step 2 queue: in F and not processed."""
        return self.in_f & ~self.processed


@dataclass(frozen=True, eq=False)
class ERDRResult:
    """The result of ERDR: the training sample D, the validation sample F and the trace."""

    characteristics: Characteristics
    """Step 1 (r, g, z, d) and the static Step 2 order."""
    readings: Readings
    """The reading of §1.1 that was run."""
    epsilon: float
    """ε of the blocking."""
    iterations: tuple[Iteration, ...]
    """Every iteration that selected an object."""
    training: IntArray
    """D — 0-based indices, ascending."""
    validation: IntArray
    """F = E₀ \\ D — 0-based indices, ascending."""
    routes: tuple[ObjectRoute, ...]
    """Per object: processed in, entered D in and by, counter decreases."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        readonly(self.training)
        readonly(self.validation)

    @property
    def m(self) -> int:
        """Number of objects of E₀."""
        return self.characteristics.m

    @property
    def processing_order(self) -> tuple[int, ...]:
        """The objects in the order Step 3 selected them."""
        return tuple(it.selected for it in self.iterations)

    @property
    def entry_order(self) -> tuple[Move, ...]:
        """The moves to D in the order they happened."""
        return tuple(move for it in self.iterations for move in it.moves)

    @property
    def training_mask(self) -> BoolArray:
        """True for the objects of D."""
        mask = np.zeros(self.m, dtype=bool)
        mask[self.training] = True
        return mask

    def initial_state(self) -> State:
        """F = E₀, nothing processed, g and d of Step 1."""
        c = self.characteristics
        return State(
            in_f=np.ones(self.m, dtype=bool),
            processed=np.zeros(self.m, dtype=bool),
            g=c.g.copy(),
            d=c.d.copy(),
        )

    def state_after(self, t: int) -> State:
        """The state after iteration ``t`` (0 = the start, before iteration 1).

        Raises:
            IndexError: ``t`` is negative or larger than the number of iterations.
        """
        if not 0 <= t <= len(self.iterations):
            raise IndexError(f"iteration {t} does not exist (0 … {len(self.iterations)})")
        state = self.initial_state()
        for it in self.iterations[:t]:
            state.processed[it.selected] = True
            state.d[it.selected] = it.blocked_d
            for change in it.changes:
                state.g[change.object] = change.after
            for move in it.moves:
                state.in_f[move.object] = False
        return state

    def queue_before(self, t: int) -> tuple[int, ...]:
        """The Step 2 queue of iteration ``t`` (1-based): waiting objects in static order."""
        waiting = self.state_after(t - 1).in_queue
        return tuple(int(i) for i in self.characteristics.priority if waiting[i])

    def counter_history(self) -> IntArray:
        """Counters g after every iteration: row 0 = Step 1, row t = after iteration t."""
        rows = [self.characteristics.g.copy()]
        for it in self.iterations:
            row = rows[-1].copy()
            for change in it.changes:
                row[change.object] = change.after
            rows.append(row)
        return readonly(np.array(rows, dtype=np.int64))


def run_erdr(
    matrix: FloatArray,
    classes: IntArray,
    k: int,
    *,
    epsilon: float = DEFAULT_EPSILON,
    readings: Readings = LITERAL,
    decimals: int = 10,
    characteristics: Characteristics | None = None,
) -> ERDRResult:
    """Run ERDR (article §1.1, Steps 1–6) on a distance matrix.

    Args:
        matrix: Distances ρ of E₀ (Step 0), shape (m, m).
        classes: 0-based class index of every object.
        k: k of z(Sᵢ, k).
        epsilon: ε > 0 of the blocking d(Sᵢ) ← −(d(Sᵢ) + ε).
        readings: The reading of the open points A, B, C and the scope of z.
        decimals: Rounding of d.
        characteristics: Step 1 computed before (must match ``k`` and the scope of z).

    Raises:
        AlgorithmUndefinedError: ε ≤ 0, fewer than two classes, or k too large for z(Sᵢ, k).
    """
    if not epsilon > 0.0:
        raise AlgorithmUndefinedError(f"ε must be positive, got {epsilon}")
    y = np.asarray(classes, dtype=np.int64)
    c = characteristics or compute_characteristics(
        matrix, y, k, z_scope=readings.z_scope, decimals=decimals
    )
    if c.k != k or c.z_scope is not readings.z_scope:
        raise ValueError("the given characteristics were computed for another k or scope of z")
    m = y.size
    r = c.r
    g = c.g.copy()
    d = c.d.copy()
    in_f = np.ones(m, dtype=bool)
    processed = np.zeros(m, dtype=bool)
    processed_in: list[int | None] = [None] * m
    entered_in: list[int | None] = [None] * m
    entered_by: list[int | None] = [None] * m
    decreases = [0] * m
    iterations: list[Iteration] = []
    queue_cursor = 0  # the static order: objects before the cursor have left the queue for good
    priority = c.priority

    def waits(index: int) -> bool:
        return bool(in_f[index] and d[index] >= 0.0)

    while True:
        # Step 2 — the first waiting object of the static order (a left object never returns)
        while queue_cursor < m and not waits(int(priority[queue_cursor])):
            queue_cursor += 1
        if queue_cursor >= m:
            break  # Step 6
        queue_length = int((in_f & (d >= 0.0)).sum())
        i = int(priority[queue_cursor])  # Step 3
        t = len(iterations) + 1

        # Step 4 — the set L, built before Sᵢ is blocked: Sⱼ ∈ F ∩ K_t with ρ(Sⱼ, Sᵢ) < r(Sⱼ)
        covering = [int(j) for j in np.flatnonzero(in_f & (y == y[i]) & (matrix[:, i] < r))]
        members: list[int] = []
        excluded: list[int] = []
        for j in covering:
            if g[j] <= 1:
                continue
            own = j == i and readings.self_in_l is SelfInL.EXCLUDED  # reading A
            blocked = j != i and readings.blocked_cover is BlockedCover.DROPPED and processed[j]
            if own or blocked:  # reading B
                excluded.append(j)
            else:
                members.append(j)
        d_selected = float(d[i])
        blocked = -(d_selected + epsilon)
        d[i] = blocked
        processed[i] = True
        processed_in[i] = t

        changes: list[CounterChange] = []
        moves: list[Move] = []
        stopped = False
        if len(members) == 1:
            decision = Decision.MOVE
            in_f[i] = False
            moves.append(Move(i, 4))
        elif len(members) > 1:
            decision = Decision.CORRECT
            for position, j in enumerate(members):  # Step 5
                before = int(g[j])
                g[j] = before - 1
                decreases[j] += 1
                changes.append(CounterChange(j, before, int(g[j])))
                if g[j] == 1:
                    in_f[j] = False
                    moves.append(Move(j, 5))
                    if readings.step5_return is Step5Return.FIRST_MOVE:
                        stopped = position < len(members) - 1
                        break
        else:
            decision = Decision.STAY
        for move in moves:
            entered_in[move.object] = t
            entered_by[move.object] = move.step

        iterations.append(
            Iteration(
                number=t,
                selected=i,
                queue_length=queue_length,
                d=d_selected,
                r=float(r[i]),
                covering=tuple(covering),
                excluded=tuple(excluded),
                L=tuple(members),
                decision=decision,
                blocked_d=blocked,
                changes=tuple(changes),
                moves=tuple(moves),
                stopped_early=stopped,
                f_size=int(in_f.sum()),
                d_size=int(m - in_f.sum()),
                queue_left=int((in_f & (d >= 0.0)).sum()),
            )
        )
        if len(iterations) > m:  # pragma: no cover - impossible: every iteration blocks one object
            raise AlgorithmUndefinedError("ERDR did not stop after m iterations")

    training = np.flatnonzero(~in_f).astype(np.int64)
    validation = np.flatnonzero(in_f).astype(np.int64)
    routes = tuple(
        ObjectRoute(processed_in[j], entered_in[j], entered_by[j], decreases[j]) for j in range(m)
    )
    logger.info(
        "ERDR finished",
        extra={
            "k": k,
            "reading": readings.code,
            "z_scope": readings.z_scope.value,
            "iterations": len(iterations),
            "D": int(training.size),
            "F": int(validation.size),
        },
    )
    return ERDRResult(
        characteristics=c,
        readings=readings,
        epsilon=epsilon,
        iterations=tuple(iterations),
        training=training,
        validation=validation,
        routes=routes,
    )
