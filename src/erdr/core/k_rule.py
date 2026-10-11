"""The k rule: which k may be used for z(Sᵢ, k) (ADR-005).

The same rule as in the author's other experiments (workbook sheet *Parameters*): odd k from
k_min = 3 (fixed for every dataset) to k_max = 2·min|Kᵢ| − 3, the class sizes counted from the
sample. Independently of the rule, z(Sᵢ, k) exists only if every object has at least k
neighbours in the scope of z: k ≤ m − 1 for neighbours of any class, k ≤ min|Kᵢ| − 1 for the
own class.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from erdr.core.readings import ZScope

K_MIN = 3
"""The smallest permitted k — fixed for every dataset."""


@dataclass(frozen=True)
class PermittedK:
    """The permitted k of a sample."""

    k_min: int
    """Always :data:`K_MIN`."""
    k_max: int
    """2·min|Kᵢ| − 3 (may be smaller than k_min: then no k is permitted)."""
    ks: tuple[int, ...]
    """Odd k = k_min, k_min + 2, …, k_max (empty when k_max < k_min)."""

    def __contains__(self, k: object) -> bool:
        """Whether ``k`` is permitted."""
        return k in self.ks

    @property
    def text(self) -> str:
        """``3, 5, …, 237`` or ``3`` or ``none`` — as the workbook lists them."""
        if not self.ks:
            return "none"
        if len(self.ks) <= 3:
            return ", ".join(str(k) for k in self.ks)
        return f"{self.ks[0]}, {self.ks[1]}, …, {self.ks[-1]}"


def permitted_k(class_sizes: Sequence[int]) -> PermittedK:
    """Odd k from 3 to 2·min|Kᵢ| − 3 (workbook *Parameters*, rows k_min … permitted k)."""
    smallest = min(class_sizes) if class_sizes else 0
    k_max = 2 * smallest - 3
    return PermittedK(K_MIN, k_max, tuple(range(K_MIN, k_max + 1, 2)))


def largest_defined_k(class_sizes: Sequence[int], z_scope: ZScope = ZScope.ALL) -> int:
    """The largest k for which z(Sᵢ, k) exists for every object (0 if none).

    Any class: every object has m − 1 neighbours. Own class: an object of the smallest class has
    min|Kᵢ| − 1 neighbours of its class.
    """
    if not class_sizes:
        return 0
    if ZScope(z_scope) is ZScope.OWN_CLASS:
        return max(min(class_sizes) - 1, 0)
    return max(sum(class_sizes) - 1, 0)
