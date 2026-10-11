"""Readings of §1.1: the points the article's text leaves open, as switches (ADR-003).

The workbook (*Readings (Switches)*) names three of them A, B and C, with 1 = the literal article
text and 2 = the alternative; this module adds the class scope of z(Sᵢ, k), which the workbook
studies on the sheet *Article Table 1 Check*:

A · Sᵢ in its own L (:class:`SelfInL`)
    L = {Sⱼ ∈ F ∩ K_t | ρ(Sⱼ, Sᵢ) < r(Sⱼ) and g(Sⱼ) > 1}. Literally Sᵢ satisfies the condition
    itself whenever g(Sᵢ) > 1, because ρ(Sᵢ, Sᵢ) = 0 < r(Sᵢ).
B · processed objects keep covering (:class:`BlockedCover`)
    Blocked objects (d < 0) stay in F, so literally they can still be members of L.
C · return to Step 2 (:class:`Step5Return`)
    «Перейти к шагу 2» stands after the move inside the loop over L; read as "after the whole
    set L has been corrected" (literal default) or "right after the first move".
z · class scope of z(Sᵢ, k) (:class:`ZScope`)
    «расстояние от объекта Sᵢ до его k-го ближайшего соседа» — of any class (default) or of the
    own class. With B = 2 the own-class scope is the reading closest to the article's Table 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import product


class SelfInL(StrEnum):
    """Reading A: can the selected object Sᵢ be a member of its own set L?"""

    INCLUDED = "included"
    """A = 1 (literal): Sᵢ ∈ L whenever g(Sᵢ) > 1, since ρ(Sᵢ, Sᵢ) = 0 < r(Sᵢ)."""
    EXCLUDED = "excluded"
    """A = 2: only other objects Sⱼ ≠ Sᵢ form L."""


class BlockedCover(StrEnum):
    """Reading B: do processed (blocked) objects still belong to L?"""

    KEPT = "kept"
    """B = 1 (literal): blocked objects stay in F and can be members of L later."""
    DROPPED = "dropped"
    """B = 2: besides Sᵢ, only objects still waiting in the queue (d ≥ 0) can be in L."""


class Step5Return(StrEnum):
    """Reading C: where does «Перейти к шагу 2» stand in Step 5?"""

    AFTER_ALL = "after-all"
    """C = 1 (literal default): after every member of L has been corrected."""
    FIRST_MOVE = "first-move"
    """C = 2: right after the first member whose g falls to 1 (L taken by ascending index)."""


class ZScope(StrEnum):
    """Over which objects z(Sᵢ, k) — the distance to the k-th nearest neighbour — is taken."""

    ALL = "all"
    """Neighbours of any class (Sᵢ excluded) — the workbook's reading."""
    OWN_CLASS = "own-class"
    """Neighbours of Sᵢ's own class only; needs k ≤ |K_t| − 1 for every class."""


_A = {SelfInL.INCLUDED: 1, SelfInL.EXCLUDED: 2}
_B = {BlockedCover.KEPT: 1, BlockedCover.DROPPED: 2}
_C = {Step5Return.AFTER_ALL: 1, Step5Return.FIRST_MOVE: 2}


@dataclass(frozen=True)
class Readings:
    """One reading of §1.1: the switches A, B, C and the scope of z."""

    self_in_l: SelfInL = SelfInL.INCLUDED
    """A — Sᵢ in its own L."""
    blocked_cover: BlockedCover = BlockedCover.KEPT
    """B — processed objects keep covering."""
    step5_return: Step5Return = Step5Return.AFTER_ALL
    """C — return to Step 2 in Step 5."""
    z_scope: ZScope = ZScope.ALL
    """Class scope of z(Sᵢ, k)."""

    def __post_init__(self) -> None:
        """Accept the switch values as text (``"excluded"``) as well as enum members."""
        object.__setattr__(self, "self_in_l", SelfInL(self.self_in_l))
        object.__setattr__(self, "blocked_cover", BlockedCover(self.blocked_cover))
        object.__setattr__(self, "step5_return", Step5Return(self.step5_return))
        object.__setattr__(self, "z_scope", ZScope(self.z_scope))

    @property
    def code(self) -> str:
        """The workbook's code of A, B, C: ``"111"`` for the literal reading."""
        return f"{_A[self.self_in_l]}{_B[self.blocked_cover]}{_C[self.step5_return]}"

    @property
    def is_literal(self) -> bool:
        """Whether this is the literal article reading (A = B = C = 1, z of any class)."""
        return self == LITERAL

    @property
    def label(self) -> str:
        """``A=1 B=2 C=1 · z: own class`` — a short description for tables and messages."""
        a, b, c = tuple(self.code)
        scope = "any class" if self.z_scope is ZScope.ALL else "own class"
        return f"A={a} B={b} C={c} · z: {scope}"

    @classmethod
    def from_code(cls, code: str, z_scope: ZScope | str = ZScope.ALL) -> Readings:
        """The reading of the workbook code ``"121"`` (digits A, B, C; 1 or 2 each).

        Raises:
            ValueError: ``code`` is not three digits 1 or 2.
        """
        text = code.strip()
        if len(text) != 3 or any(digit not in "12" for digit in text):
            raise ValueError(f"a reading code is three digits 1 or 2 (A, B, C), got {code!r}")
        a, b, c = (int(digit) for digit in text)
        return cls(
            self_in_l=SelfInL.INCLUDED if a == 1 else SelfInL.EXCLUDED,
            blocked_cover=BlockedCover.KEPT if b == 1 else BlockedCover.DROPPED,
            step5_return=Step5Return.AFTER_ALL if c == 1 else Step5Return.FIRST_MOVE,
            z_scope=ZScope(z_scope),
        )


LITERAL = Readings()
"""The literal article reading — the workbook's default (A = B = C = 1, z of any class)."""
CLOSEST = Readings(blocked_cover=BlockedCover.DROPPED, z_scope=ZScope.OWN_CLASS)
"""B = 2 with the own-class z: the reading closest to the article's Table 1 (ADR-004)."""


def all_readings(z_scopes: tuple[ZScope, ...] = (ZScope.ALL,)) -> tuple[Readings, ...]:
    """Every combination of A, B, C (in the workbook's order 111, 112, …, 222) per z scope."""
    return tuple(
        Readings.from_code(f"{a}{b}{c}", scope)
        for scope in z_scopes
        for a, b, c in product((1, 2), repeat=3)
    )
