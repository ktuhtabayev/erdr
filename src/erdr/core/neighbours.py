"""Sorted neighbours (sheet *Sorted Neighbors*): every object's other objects by distance.

Equal distances are ordered by the smaller original index (ADR-008), so the order — and with it
the nearest enemy, the k-th neighbour and the queue — is unique.
"""

from __future__ import annotations

import numpy as np

from erdr.core.arrays import BoolArray, FloatArray, IntArray, readonly


def neighbour_order(matrix: FloatArray, allowed: BoolArray | None = None) -> IntArray:
    """For every object, the other objects by ascending (ρ, index).

    Args:
        matrix: The distance matrix, shape (m, m).
        allowed: Optional (m, m) mask: ``allowed[i, j]`` keeps Sⱼ in the list of Sᵢ. Rows may then
            have different lengths; missing places are filled with −1 at the end.

    Returns:
        Shape (m, m − 1): row i lists the 0-based indices of the neighbours of Sᵢ, nearest first.
    """
    m = matrix.shape[0]
    order = np.full((m, max(m - 1, 0)), -1, dtype=np.int64)
    index = np.arange(m)
    for i in range(m):
        keep = index != i
        if allowed is not None:
            keep &= allowed[i]
        others = index[keep]
        # lexsort: the last key is the primary one — distance first, then the index
        ranked = others[np.lexsort((others, matrix[i, others]))]
        order[i, : ranked.size] = ranked
    return readonly(order)


def rank_matrix(order: IntArray) -> IntArray:
    """Rank of Sⱼ in the neighbour list of Sᵢ (1 = nearest; 0 on the diagonal and if absent)."""
    m = order.shape[0]
    ranks = np.zeros((m, m), dtype=np.int64)
    for i in range(m):
        listed = order[i][order[i] >= 0]
        ranks[i, listed] = np.arange(1, listed.size + 1)
    return readonly(ranks)
