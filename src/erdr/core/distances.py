"""Step 0: the distance matrix ρ(Sᵢ, Sⱼ) of the sample E₀.

The article (§3) normalizes the quantitative features to [0; 1] before the Zhuravlev metric is
applied; the step-by-step guide calls this Step 0. Here it is a pipeline of three exchangeable
parts — the feature selection, a normalizer (:mod:`.normalizers`) and a metric (:mod:`.metrics`)
— whose result, :class:`Distances`, is everything Steps 1–6 need besides the classes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

from erdr.core.arrays import BoolArray, FloatArray, IntArray, as_float_matrix, freeze_fields
from erdr.core.metrics import METRICS, round_distances, traits_of, zhuravlev
from erdr.core.normalizers import NORMALIZERS, Scaling
from erdr.errors import ConfigError

logger = logging.getLogger(__name__)

FeatureSelection = Literal["auto", "all", "quantitative", "nominal"] | Sequence[int]
"""Which features the metric sees: ``auto`` (the metric's domain), ``all`` (I ∪ J),
``quantitative`` (I), ``nominal`` (J) or explicit 0-based feature indices."""


@dataclass(frozen=True, eq=False)
class Distances:
    """The result of Step 0."""

    matrix: FloatArray
    """ρ(Sᵢ, Sⱼ), shape (m, m), symmetric, zero diagonal, rounded to :attr:`decimals`."""
    unified: FloatArray
    """The unified values x′ of all features, shape (m, n) — sheet *Normalized Dataset*."""
    scaling: Scaling
    """The fitted scale unification (min and max per feature for min–max)."""
    metric: str
    """Registry name of the metric."""
    features: IntArray
    """0-based indices of the features the metric used."""
    decimals: int
    """Rounding of the distances."""
    quantitative_part: FloatArray | None = None
    """ρ_I = Σ_{j∈I} |x′ⱼ − y′ⱼ| (Zhuravlev metric only; ``None`` for other metrics)."""
    nominal_part: FloatArray | None = None
    """ρ_J = Σ_{j∈J} [xⱼ ≠ yⱼ] (Zhuravlev metric only; ``None`` for other metrics)."""

    def __post_init__(self) -> None:
        """Freeze the arrays."""
        freeze_fields(self)

    @property
    def m(self) -> int:
        """Number of objects."""
        return int(self.matrix.shape[0])


def select_features(
    quantitative: BoolArray,
    selection: FeatureSelection = "auto",
    *,
    domain: str = "any",
    names: Sequence[str] | None = None,
    metric: str = "metric",
) -> IntArray:
    """0-based indices of the features the metric sees.

    Args:
        quantitative: Mask of set I over all features.
        selection: See :data:`FeatureSelection`.
        domain: The metric's domain (``any``, ``quantitative``, ``nominal``).
        names: Feature names for messages (``x₁ …`` when omitted).
        metric: The metric's name for messages.

    Raises:
        ConfigError: The selection is empty, names an unknown feature, or contains features
            outside the metric's domain.
    """
    mask = np.asarray(quantitative, dtype=bool)
    n = mask.size
    labels = list(names) if names is not None else [f"x{j + 1}" for j in range(n)]
    if isinstance(selection, str):
        chosen = domain if selection == "auto" else selection
        if chosen == "any" or chosen == "all":
            index = np.arange(n)
        elif chosen == "quantitative":
            index = np.flatnonzero(mask)
        elif chosen == "nominal":
            index = np.flatnonzero(~mask)
        else:
            raise ConfigError(f"unknown feature selection {selection!r}")
    else:
        index = np.asarray(list(selection), dtype=np.int64)
        bad = [int(j) for j in index if not 0 <= j < n]
        if bad:
            raise ConfigError(f"feature indices {bad} are out of range (the dataset has {n})")
        if len(set(index.tolist())) != index.size:
            raise ConfigError("the feature selection repeats a feature")
    if index.size == 0:
        raise ConfigError(
            f"{metric}: the feature selection {selection!r} is empty for this dataset"
        )
    if domain == "quantitative" and not mask[index].all():
        wrong = ", ".join(labels[j] for j in index if not mask[j])
        raise ConfigError(
            f"{metric} is defined on quantitative features only; the selection contains the "
            f"nominal features {wrong} (select 'quantitative' or 'auto')"
        )
    if domain == "nominal" and mask[index].any():
        wrong = ", ".join(labels[j] for j in index if mask[j])
        raise ConfigError(
            f"{metric} is defined on nominal features only; the selection contains the "
            f"quantitative features {wrong} (select 'nominal' or 'auto')"
        )
    return index.astype(np.int64)


def zhuravlev_parts(
    Z: FloatArray, quantitative: BoolArray, decimals: int
) -> tuple[FloatArray, FloatArray]:
    """ρ_I and ρ_J of the Zhuravlev metric — sheet *Zhuravlev Distances*, lower tables."""
    mask = np.asarray(quantitative, dtype=bool)
    m = Z.shape[0]
    quantitative_part = (
        zhuravlev(Z[:, mask], Z[:, mask], mask[mask], decimals, None)
        if mask.any()
        else np.zeros((m, m))
    )
    nominal_part = (
        zhuravlev(Z[:, ~mask], Z[:, ~mask], mask[~mask], decimals, None)
        if (~mask).any()
        else np.zeros((m, m))
    )
    return quantitative_part, nominal_part


def compute_distances(
    X: FloatArray,
    quantitative: BoolArray,
    *,
    normalizer: str = "minmax",
    normalizer_params: Mapping[str, object] | None = None,
    metric: str = "zhuravlev",
    metric_params: Mapping[str, object] | None = None,
    features: FeatureSelection = "auto",
    decimals: int = 10,
    names: Sequence[str] | None = None,
) -> Distances:
    """Step 0: scale unification on E₀, then the metric on the selected features.

    Args:
        X: Original feature values of E₀, shape (m, n); nominal columns hold category codes.
        quantitative: Mask of set I.
        normalizer: Registry name in :data:`~erdr.core.normalizers.NORMALIZERS`.
        normalizer_params: The normalizer's parameters.
        metric: Registry name in :data:`~erdr.core.metrics.METRICS`.
        metric_params: The metric's parameters.
        features: The features the metric sees (:data:`FeatureSelection`).
        decimals: Rounding of the distances (10 in the workbook).
        names: Feature names for messages.

    Raises:
        RegistryError: Unknown normalizer or metric.
        ConfigError: Invalid parameters or feature selection.
    """
    values = as_float_matrix(X)
    mask = np.asarray(quantitative, dtype=bool)
    if mask.size != values.shape[1]:
        raise ConfigError(f"{mask.size} feature types for {values.shape[1]} features")
    scaling = NORMALIZERS.get(normalizer)(
        values, mask, NORMALIZERS.make_params(normalizer, normalizer_params)
    )
    unified = scaling.transform(values)

    info = METRICS.info(metric)
    distance = info.obj
    declared = traits_of(distance)
    index = select_features(mask, features, domain=declared.domain, names=names, metric=info.name)
    sub_mask = mask[index]
    params: Any = METRICS.make_params(info.name, metric_params)
    if declared.check is not None:
        declared.check(sub_mask, params)
    Z = unified[:, index]
    if declared.fit is not None:
        params = declared.fit(Z, sub_mask, params)
    matrix = np.array(distance(Z, Z, sub_mask, decimals, params), dtype=np.float64)
    # an object is at distance 0 from itself, whatever the metric's rounding
    np.fill_diagonal(matrix, 0.0)
    if not np.array_equal(matrix, matrix.T):  # never re-round a symmetric matrix: ties stay exact
        matrix = round_distances((matrix + matrix.T) / 2.0, decimals)

    parts: tuple[FloatArray | None, FloatArray | None] = (None, None)
    if info.name == "zhuravlev":
        parts = zhuravlev_parts(Z, sub_mask, decimals)
    logger.info(
        "distances computed",
        extra={"m": values.shape[0], "metric": info.name, "normalizer": scaling.normalizer},
    )
    return Distances(
        matrix=matrix,
        unified=unified,
        scaling=scaling,
        metric=info.name,
        features=index,
        decimals=decimals,
        quantitative_part=parts[0],
        nominal_part=parts[1],
    )
