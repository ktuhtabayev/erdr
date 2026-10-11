"""Analyses over many runs: every reading of §1.1, and the training-sample size for many k.

``compare_readings`` is the sheet *Readings (Switches)* — all eight combinations of A, B, C (and,
optionally, both scopes of z) on one sample. ``sweep_k`` is the sheet *Article Table 1 Check* —
|D| and its class composition for a list of k, per reading. Step 0 is computed once and shared;
Step 1 once per (k, scope of z).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from erdr.config.models import ExperimentConfig
from erdr.core.algorithm import ERDRResult, run_erdr
from erdr.core.characteristics import Characteristics, compute_characteristics
from erdr.core.k_rule import largest_defined_k, permitted_k
from erdr.core.readings import CLOSEST, LITERAL, Readings, ZScope, all_readings
from erdr.data.schema import Dataset
from erdr.errors import AlgorithmUndefinedError
from erdr.services.experiment import step0

logger = logging.getLogger(__name__)

Progress = Callable[[int, int], None]
"""Called with (runs done, runs in total) — for progress bars."""


@dataclass(frozen=True)
class ReadingRow:
    """One reading on one sample (a row of *Readings (Switches)*)."""

    readings: Readings
    """The reading."""
    processing_order: tuple[int, ...]
    """The objects in the order Step 3 selected them."""
    training: tuple[int, ...]
    """D (0-based, ascending)."""
    validation: tuple[int, ...]
    """F (0-based, ascending)."""
    training_by_class: tuple[int, ...]
    """|D ∩ K1|, |D ∩ K2|, …"""
    iterations: int
    """Number of iterations."""
    error: str | None = None
    """Why the reading is undefined here (e.g. own-class z with too small a class)."""


@dataclass(frozen=True)
class SweepRow:
    """|D| for one k and one reading (a cell group of *Article Table 1 Check*)."""

    k: int
    """k of z(Sᵢ, k)."""
    readings: Readings
    """The reading."""
    training_size: int
    """|D|."""
    training_by_class: tuple[int, ...]
    """|D ∩ K1|, |D ∩ K2|, …"""
    validation_size: int
    """|F|."""
    iterations: int
    """Number of iterations."""
    permitted: bool
    """Whether k is permitted by the k rule."""

    @property
    def share(self) -> float:
        """|D| / m."""
        total = self.training_size + self.validation_size
        return self.training_size / total if total else 0.0


def _by_class(classes: np.ndarray, indices: np.ndarray, count: int) -> tuple[int, ...]:
    return tuple(int(c) for c in np.bincount(classes[indices], minlength=count))


def compare_readings(
    dataset: Dataset,
    config: ExperimentConfig | None = None,
    *,
    z_scopes: Sequence[ZScope] = (ZScope.ALL,),
    progress: Progress | None = None,
) -> tuple[ReadingRow, ...]:
    """Run every combination of A, B, C (per scope of z) with the other settings of ``config``.

    A reading that is undefined for the sample (own-class z with k ≥ min|Kᵢ|) gets a row with
    :attr:`ReadingRow.error` instead of a result.
    """
    chosen = config or ExperimentConfig()
    matrix, classes = step0(chosen, dataset).matrix, dataset.class_index
    count = len(dataset.classes)
    readings = all_readings(tuple(z_scopes))
    step1: dict[ZScope, Characteristics | str] = {}
    rows: list[ReadingRow] = []
    for done, reading in enumerate(readings, start=1):
        if reading.z_scope not in step1:
            try:
                step1[reading.z_scope] = compute_characteristics(
                    matrix,
                    classes,
                    chosen.erdr.k,
                    z_scope=reading.z_scope,
                    decimals=chosen.erdr.d_decimals,
                )
            except AlgorithmUndefinedError as error:
                step1[reading.z_scope] = str(error)
        found = step1[reading.z_scope]
        if isinstance(found, str):
            rows.append(ReadingRow(reading, (), (), (), (0,) * count, 0, found))
        else:
            result = run_erdr(
                matrix,
                classes,
                chosen.erdr.k,
                epsilon=chosen.erdr.epsilon,
                readings=reading,
                decimals=chosen.erdr.d_decimals,
                characteristics=found,
            )
            rows.append(_reading_row(result, count))
        if progress is not None:
            progress(done, len(readings))
    return tuple(rows)


def _reading_row(result: ERDRResult, count: int) -> ReadingRow:
    classes = result.characteristics.classes
    return ReadingRow(
        readings=result.readings,
        processing_order=result.processing_order,
        training=tuple(int(i) for i in result.training),
        validation=tuple(int(i) for i in result.validation),
        training_by_class=_by_class(classes, result.training, count),
        iterations=len(result.iterations),
    )


def sweep_k(
    dataset: Dataset,
    config: ExperimentConfig | None = None,
    *,
    ks: Sequence[int] | None = None,
    readings: Sequence[Readings] = (LITERAL, CLOSEST),
    progress: Progress | None = None,
) -> tuple[SweepRow, ...]:
    """|D| for every k of ``ks`` (default: every permitted k) and every reading.

    Pairs (k, reading) for which z(Sᵢ, k) does not exist are skipped. The other settings
    (normalizer, metric, ε, rounding) come from ``config``; its k and readings are ignored.
    """
    chosen = config or ExperimentConfig()
    matrix, classes = step0(chosen, dataset).matrix, dataset.class_index
    sizes = [size for size in dataset.class_sizes if size > 0]
    permitted = permitted_k(sizes)
    wanted = list(ks) if ks is not None else list(permitted.ks)
    count = len(dataset.classes)
    total = len(wanted) * len(readings)
    rows: list[SweepRow] = []
    done = 0
    for k in wanted:
        step1: dict[ZScope, Characteristics] = {}
        for reading in readings:
            done += 1
            if k > largest_defined_k(sizes, reading.z_scope) or k < 1:
                continue
            if reading.z_scope not in step1:
                step1[reading.z_scope] = compute_characteristics(
                    matrix, classes, k, z_scope=reading.z_scope, decimals=chosen.erdr.d_decimals
                )
            result = run_erdr(
                matrix,
                classes,
                k,
                epsilon=chosen.erdr.epsilon,
                readings=reading,
                decimals=chosen.erdr.d_decimals,
                characteristics=step1[reading.z_scope],
            )
            rows.append(
                SweepRow(
                    k=k,
                    readings=reading,
                    training_size=int(result.training.size),
                    training_by_class=_by_class(classes, result.training, count),
                    validation_size=int(result.validation.size),
                    iterations=len(result.iterations),
                    permitted=k in permitted,
                )
            )
            if progress is not None:
                progress(done, total)
    logger.info("k sweep finished", extra={"dataset": dataset.name, "runs": len(rows)})
    return tuple(rows)
