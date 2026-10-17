"""The experiment runner: a configuration and a dataset in, an :class:`ExperimentResult` out.

It resolves the plug-ins of the configuration — the metric from the dataset type when
``distance.metric`` is ``auto`` (ADR-022) —, checks the k rule (ADR-005), runs Step 0 and ERDR,
detects the cases, and records everything a run folder, an export or the GUI needs: the
configuration and its hash, the metric chosen, the dataset and its content hash, timings and
warnings.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from erdr.config.io import config_hash
from erdr.config.models import ExperimentConfig
from erdr.config.presets import reading_notes
from erdr.core.algorithm import ERDRResult, run_erdr
from erdr.core.cases import CaseResult, detect_cases
from erdr.core.distances import Distances, compute_distances
from erdr.core.k_rule import PermittedK, permitted_k
from erdr.data.loaders import load_from_config
from erdr.data.schema import Dataset
from erdr.data.writers import shape_name
from erdr.errors import ConfigError
from erdr.services.datasets import MetricChoice, choose_metric, feature_selection

logger = logging.getLogger(__name__)


@dataclass(frozen=True, eq=False)
class ExperimentResult:
    """One ERDR run with everything needed to show, save, export or repeat it."""

    config: ExperimentConfig
    """The configuration that was run."""
    dataset: Dataset
    """The sample E₀."""
    distances: Distances
    """Step 0: unified values and the distance matrix."""
    result: ERDRResult
    """Steps 1–6: characteristics, trace, D and F."""
    cases: tuple[CaseResult, ...]
    """The 17 cases of the checklist."""
    permitted: PermittedK
    """The permitted k of the sample (k rule)."""
    config_hash: str
    """SHA-256 of the canonical configuration."""
    dataset_hash: str
    """Content hash of the dataset."""
    started: datetime
    """When the run started (UTC)."""
    seconds: float
    """Wall-clock duration of Step 0 to Step 6."""
    warnings: tuple[str, ...] = field(default_factory=tuple)
    """Warnings raised while running (k outside the rule with ``k_rule: warn``, a metric that
    sees one feature type of a heterogeneous dataset, …)."""
    metric_choice: MetricChoice | None = None
    """The metric that was run and why (``auto``: the metric of the dataset type)."""

    @property
    def metric_label(self) -> str:
        """``zhuravlev (auto · heterogeneous dataset)`` — the metric as the exports show it."""
        return self.metric_choice.label if self.metric_choice else self.distances.metric

    @property
    def k(self) -> int:
        """K of z(Sᵢ, k)."""
        return self.result.characteristics.k

    @property
    def training_dataset(self) -> Dataset:
        """D as a dataset — e.g. ``Heart-Disease (5, 13, 2)`` — keeping the object ids."""
        return self._part(self.result.training, "training")

    @property
    def validation_dataset(self) -> Dataset:
        """F = E₀ minus D as a dataset, keeping the object ids."""
        return self._part(self.result.validation, "validation")

    def _part(self, indices: np.ndarray, role: str) -> Dataset:
        part = self.dataset.subset(indices)
        return self.dataset.subset(indices, name=f"{shape_name(self.dataset.name, part)} {role}")

    @property
    def object_names(self) -> tuple[str, ...]:
        """The object ids (S₁ … Sₘ by default)."""
        return self.dataset.object_ids

    @property
    def notes(self) -> tuple[str, ...]:
        """The readings that differ from the literal article text, as text."""
        return tuple(f"{note.switch}: {note.statement}" for note in reading_notes(self.config))

    def class_counts(self, indices: np.ndarray) -> tuple[int, ...]:
        """Objects of every class (K1, K2, …) among ``indices``."""
        classes = self.result.characteristics.classes[indices]
        return tuple(int(c) for c in np.bincount(classes, minlength=len(self.dataset.classes)))


def check_k_rule(config: ExperimentConfig, dataset: Dataset) -> tuple[PermittedK, tuple[str, ...]]:
    """The permitted k of ``dataset`` and the warnings of the k rule (ADR-005).

    Raises:
        ConfigError: ``k_rule: enforce`` and k is not permitted.
    """
    sizes = [size for size in dataset.class_sizes if size > 0]
    permitted = permitted_k(sizes)
    k = config.erdr.k
    if k in permitted or config.erdr.k_rule == "off":
        return permitted, ()
    message = (
        f"k = {k} is outside the k rule for {dataset.name} (odd k from 3 to 2·min|Kᵢ| − 3 = "
        f"{permitted.k_max}; permitted: {permitted.text})"
    )
    if config.erdr.k_rule == "enforce":
        raise ConfigError(message + " — choose a permitted k or set erdr.k_rule to warn or off")
    logger.warning(message)
    return permitted, (message,)


def step0(
    config: ExperimentConfig, dataset: Dataset, choice: MetricChoice | None = None
) -> Distances:
    """Step 0 as configured: scale unification and the distance matrix of ``dataset``.

    Args:
        config: The configuration.
        dataset: The sample E₀.
        choice: The metric chosen for ``dataset`` (:func:`choose_metric` when omitted).

    Raises:
        ConfigError: Invalid plug-ins or parameters, a metric not defined on the dataset's
            feature types, or an invalid feature selection.
    """
    metric = choice or choose_metric(config, dataset)
    return compute_distances(
        dataset.X,
        dataset.quantitative,
        normalizer=config.preprocessing.normalizer.name,
        normalizer_params=config.preprocessing.normalizer.params,
        metric=metric.name,
        metric_params=metric.spec.params,
        features=feature_selection(config, dataset),
        decimals=config.distance.decimals,
        names=dataset.feature_names,
    )


def run_experiment(
    config: ExperimentConfig | None = None,
    dataset: Dataset | None = None,
    *,
    base_dir: Path | None = None,
) -> ExperimentResult:
    """Run ERDR as configured.

    Args:
        config: The configuration (the ``literal`` preset when omitted).
        dataset: The sample E₀; when omitted it is loaded as ``config.dataset`` describes.
        base_dir: Folder against which relative dataset paths are resolved.

    Raises:
        ConfigError: Invalid plug-ins, parameters, feature selection, or a k outside the rule.
        DatasetError: The dataset cannot be loaded.
        AlgorithmUndefinedError: ERDR is undefined for the data (one class, k too large).
    """
    chosen = config or ExperimentConfig()
    data = dataset if dataset is not None else load_from_config(chosen.dataset, base_dir)
    started = datetime.now(UTC)
    clock = time.perf_counter()
    permitted, warnings = check_k_rule(chosen, data)
    choice = choose_metric(chosen, data)
    if choice.note:
        logger.warning(choice.note)
        warnings = (*warnings, choice.note)
    distances = step0(chosen, data, choice)
    result = run_erdr(
        distances.matrix,
        data.class_index,
        chosen.erdr.k,
        epsilon=chosen.erdr.epsilon,
        readings=chosen.erdr.readings.to_readings(),
        decimals=chosen.erdr.d_decimals,
    )
    cases = detect_cases(result)
    seconds = time.perf_counter() - clock
    logger.info(
        "experiment finished",
        extra={"dataset": data.name, "seconds": round(seconds, 3), "D": int(result.training.size)},
    )
    return ExperimentResult(
        config=chosen,
        dataset=data,
        distances=distances,
        result=result,
        cases=cases,
        permitted=permitted,
        config_hash=config_hash(chosen),
        dataset_hash=data.content_hash(),
        started=started,
        seconds=seconds,
        warnings=warnings,
        metric_choice=choice,
    )
