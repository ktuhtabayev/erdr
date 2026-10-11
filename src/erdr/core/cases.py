"""The cases of the algorithm (sheet *Case Checklist*): which ones a run shows, and where.

Cases 1–4, 6–14 and 16 are the 14 branch cases of Steps 1–6; 5, 15 and 17 are the extra cases
for which the workbook's sample needs its seventh object. A case that cannot happen is not
listed: "an object covers Sᵢ but is left out of L because g(Sⱼ) = 1" — if Sⱼ ≠ Sᵢ covers Sᵢ, then
g(Sⱼ) ≥ 2 at the start, g only falls in Step 5, and an object whose g falls to 1 leaves F at once.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from erdr.core.algorithm import Decision, ERDRResult
from erdr.core.k_rule import permitted_k


@dataclass(frozen=True)
class CaseDefinition:
    """One case of the checklist."""

    number: int
    """1 … 17."""
    title: str
    """What happens."""
    checked_on: str
    """The workbook sheet where it is visible."""
    why: str
    """Why it matters."""
    kind: str
    """``branch`` or ``extra``."""


@dataclass(frozen=True)
class CaseResult:
    """Whether a case occurs in a run, and where it first does."""

    case: CaseDefinition
    """The case."""
    occurs: bool
    """Whether it occurs."""
    first: str
    """Where it first occurs: an iteration number, or the stage (``Step 1``, ``k rule``, …)."""
    iterations: tuple[int, ...] = ()
    """For iteration cases: every iteration in which it occurs."""


CASES: tuple[CaseDefinition, ...] = (
    CaseDefinition(
        1,
        "Every class has at least 3 objects — k_min = 3 is permitted (k_max = 2·min|Kᵢ| − 3 ≥ 3)",
        "Parameters",
        "The k rule; with fewer objects in a class no k is permitted",
        "branch",
    ),
    CaseDefinition(
        2,
        "An object with g = 1: no own-class object inside its enemy sphere (border object)",
        "ERDR Characteristics",
        "Such an object can never be in another object's L",
        "branch",
    ),
    CaseDefinition(
        3,
        "An object with g ≥ 2: own-class objects inside its enemy sphere (dense object)",
        "ERDR Characteristics",
        "Only these objects can cover others in Step 4",
        "branch",
    ),
    CaseDefinition(
        4,
        "Two objects with equal d — Step 2 orders them by r",
        "Priority Queue",
        "Second criterion of Step 2",
        "branch",
    ),
    CaseDefinition(
        5,
        "Two objects with equal d and equal r — Step 2 orders them by the index",
        "Priority Queue",
        "Third criterion of Step 2 (needs mutual nearest enemies with z = r)",
        "extra",
    ),
    CaseDefinition(
        6,
        "|L| = 1 with L = {Sᵢ}: no other object covers Sᵢ → Sᵢ moves to D",
        "ERDR Iterations",
        "Step 4, first form",
        "branch",
    ),
    CaseDefinition(
        7,
        "|L| = 1 with L = {Sⱼ}, j ≠ i: exactly one other object covers Sᵢ → Sᵢ moves to D",
        "ERDR Iterations",
        "Step 4, second form",
        "branch",
    ),
    CaseDefinition(
        8,
        "|L| = 0: Sᵢ is only blocked and stays in F",
        "ERDR Iterations",
        "Not stated in the article; the literal text leaves Sᵢ in F (validation)",
        "branch",
    ),
    CaseDefinition(
        9,
        "|L| > 1 and some g(Sⱼ) falls to 1 → Sⱼ moves to D",
        "ERDR Iterations",
        "Step 5 move",
        "branch",
    ),
    CaseDefinition(
        10,
        "|L| > 1 and some g(Sⱼ) stays above 1 after the decrease",
        "ERDR Iterations",
        "Step 5 correction without a move",
        "branch",
    ),
    CaseDefinition(
        11,
        "Step 5 moves an object that has not been processed yet (it leaves the queue early)",
        "ERDR Iterations",
        "Step 5 changes the queue of later iterations",
        "branch",
    ),
    CaseDefinition(
        12,
        "Step 5 moves an object that was processed earlier and stayed in F",
        "ERDR Iterations",
        "Possible only because processed objects stay in F (reading B)",
        "branch",
    ),
    CaseDefinition(
        13,
        "Sᵢ belongs to its own L and its own counter is decreased",
        "ERDR Iterations",
        "Literal reading A: Sᵢ lies inside its own sphere",
        "branch",
    ),
    CaseDefinition(
        14,
        "One counter g(Sⱼ) is decreased in two different iterations",
        "ERDR Trace",
        "State carried from one iteration to the next",
        "branch",
    ),
    CaseDefinition(
        15,
        "Two objects move to D in the same Step 5",
        "ERDR Iterations",
        "Where «Перейти к шагу 2» stands matters (reading C)",
        "extra",
    ),
    CaseDefinition(
        16,
        "Result: D contains every class and the validation set F is not empty",
        "Training & Validation",
        "A usable training sample",
        "branch",
    ),
    CaseDefinition(
        17,
        "Result: the validation set F contains every class",
        "Training & Validation",
        "A usable validation sample",
        "extra",
    ),
)
"""The 17 cases, numbered as on the workbook's *Case Checklist*."""

ITERATION_CASES = (6, 7, 8, 9, 10, 11, 12, 13, 15)
"""Cases detected per iteration (the per-iteration flags of the checklist)."""


def _iteration_flags(result: ERDRResult) -> dict[int, list[int]]:
    """For every iteration case, the iterations in which it occurs."""
    flags: dict[int, list[int]] = {number: [] for number in ITERATION_CASES}
    processed_before: set[int] = set()
    for it in result.iterations:
        t, i = it.number, it.selected
        step5_moves = [move.object for move in it.moves if move.step == 5]
        if it.decision is Decision.MOVE:
            flags[6 if (i,) == it.L else 7].append(t)
        elif it.decision is Decision.STAY:
            flags[8].append(t)
        else:
            if step5_moves:
                flags[9].append(t)
            if any(change.after > 1 for change in it.changes):
                flags[10].append(t)
            if any(j != i and j not in processed_before for j in step5_moves):
                flags[11].append(t)
            if any(j != i and j in processed_before for j in step5_moves):
                flags[12].append(t)
            if any(change.object == i for change in it.changes):
                flags[13].append(t)
            if len(step5_moves) >= 2:
                flags[15].append(t)
        processed_before.add(i)
    return flags


def detect_cases(result: ERDRResult) -> tuple[CaseResult, ...]:
    """Which of the 17 cases occur in ``result``, and where they first do.

    Iteration cases name the first iteration; the others the stage of the algorithm that shows
    them (``k rule``, ``Step 1``, ``Step 2``, ``Step 5 (run)``, ``Step 6``), as the workbook does.
    """
    c = result.characteristics
    sizes = np.bincount(c.classes)
    sizes = sizes[sizes > 0]
    flags = _iteration_flags(result)
    decided = c.decided_by()
    occurs: dict[int, bool] = {
        1: bool(permitted_k(sizes.tolist()).ks),
        2: bool(np.any(c.g == 1)),
        3: bool(np.any(c.g >= 2)),
        4: "r" in decided,
        5: "index" in decided,
        14: any(route.counter_decreases >= 2 for route in result.routes),
        16: bool(
            result.validation.size > 0 and np.unique(c.classes[result.training]).size == sizes.size
        ),
        17: bool(np.unique(c.classes[result.validation]).size == sizes.size),
    }
    stages = {1: "k rule", 2: "Step 1", 3: "Step 1", 4: "Step 2", 5: "Step 2", 14: "Step 5 (run)"}
    stages |= {16: "Step 6", 17: "Step 6"}
    out: list[CaseResult] = []
    for case in CASES:
        if case.number in flags:
            iterations = tuple(flags[case.number])
            first = str(iterations[0]) if iterations else "—"
            out.append(CaseResult(case, bool(iterations), first, iterations))
        else:
            happened = occurs[case.number]
            out.append(CaseResult(case, happened, stages[case.number] if happened else "—"))
    return tuple(out)
