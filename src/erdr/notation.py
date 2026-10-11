"""The article's notation for display: S₁, x₁, K1, {S₁, S₂} (1-based, subscript digits).

Code is 0-based internally; everything shown to a user (tables, messages, exports, the GUI) uses
these 1-based names, as the workbook and the article do (ADR-006).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

_SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

DASH = "—"
"""Shown for an undefined or empty value, as in the workbook."""
EMPTY_SET = "∅"
"""The empty set (L = ∅, D = ∅)."""
ARROW = " → "
"""Separator of an order (S₁ → S₃ → S₅)."""


def subscript(number: int) -> str:
    """``12`` → ``₁₂``."""
    return str(number).translate(_SUBSCRIPT_DIGITS)


def object_name(index: int) -> str:
    """Name of the object with 0-based ``index``: ``S₁`` for 0."""
    return f"S{subscript(index + 1)}"


def feature_name(index: int) -> str:
    """Name of the feature with 0-based ``index``: ``x₁`` for 0."""
    return f"x{subscript(index + 1)}"


def class_name(index: int) -> str:
    """Name of the class with 0-based ``index``: ``K1`` for 0 (the article writes K1, K2)."""
    return f"K{index + 1}"


def object_set(indices: Iterable[int], names: Sequence[str] | None = None) -> str:
    """``[0, 2]`` → ``{S₁, S₃}``; ``∅`` when empty. ``names`` replaces the default names."""
    items = [names[i] if names is not None else object_name(i) for i in indices]
    return "{" + ", ".join(items) + "}" if items else EMPTY_SET


def object_order(indices: Iterable[int], names: Sequence[str] | None = None) -> str:
    """``[0, 2, 4]`` → ``S₁ → S₃ → S₅``; ``—`` when empty."""
    items = [names[i] if names is not None else object_name(i) for i in indices]
    return ARROW.join(items) if items else DASH


def join_values(values: Iterable[int]) -> str:
    """``(3, 5)`` → ``3, 5`` — the workbook's way of listing the permitted k."""
    return ", ".join(str(value) for value in values)


def moves_text(moves: Iterable[tuple[int, int]], names: Sequence[str] | None = None) -> str:
    """``[(6, 5)]`` → ``S₇ (Step 5)``; ``—`` when nothing moved (sheet *ERDR Trace*)."""
    items = [
        f"{names[j] if names is not None else object_name(j)} (Step {step})" for j, step in moves
    ]
    return ", ".join(items) if items else DASH


def changes_text(
    changes: Iterable[tuple[int, int, int]], names: Sequence[str] | None = None
) -> str:
    """``[(0, 3, 2)]`` → ``S₁: 3 → 2``; ``—`` when no counter changed (sheet *ERDR Trace*)."""
    items = [
        f"{names[j] if names is not None else object_name(j)}: {before} → {after}"
        for j, before, after in changes
    ]
    return ", ".join(items) if items else DASH
