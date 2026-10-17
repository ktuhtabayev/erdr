"""Dataset summaries: sizes, types, classes, metrics, the permitted k and the memory of a run.

The metric follows the dataset type (ADR-022). A metric declares the feature types it is defined
on (:func:`~erdr.core.metrics.traits`); on a quantitative dataset the quantitative and the
heterogeneous metrics suit, on a nominal one the nominal and the heterogeneous metrics, on a
heterogeneous one the heterogeneous metrics. ``distance.metric: auto`` takes the metric of the
type from ``distance.type_metrics``; a metric named explicitly must be defined on the dataset's
features — one that sees only part of a heterogeneous dataset is allowed and flagged.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from enum import StrEnum

from erdr.config.models import AUTO_METRIC, ExperimentConfig, PluginSpec
from erdr.core.distances import FeatureSelection, select_features
from erdr.core.k_rule import PermittedK, largest_defined_k, permitted_k
from erdr.core.metrics import METRICS, traits_of
from erdr.core.readings import ZScope
from erdr.core.registry import normalize_name
from erdr.data.schema import Dataset, DatasetType, Label
from erdr.errors import ConfigError, ERDRError
from erdr.notation import class_name


class Suitability(StrEnum):
    """How a metric suits a dataset type (ADR-022)."""

    SUITED = "suited"
    """The metric is defined on every feature of datasets of the type."""
    PARTIAL = "partial"
    """A single-type metric on a heterogeneous dataset: it sees one feature type only."""
    UNSUITED = "unsuited"
    """The metric is defined on a feature type that datasets of the type do not have."""


def suitability(metric: str, dataset_type: DatasetType) -> Suitability:
    """How the metric ``metric`` suits datasets of ``dataset_type``.

    Raises:
        RegistryError: Unknown metric.
    """
    domain = traits_of(METRICS.get(metric)).domain
    if domain == "any" or domain == dataset_type.value:
        return Suitability.SUITED
    if dataset_type is DatasetType.HETEROGENEOUS:
        return Suitability.PARTIAL
    return Suitability.UNSUITED


def suited_metrics(dataset_type: DatasetType) -> tuple[str, ...]:
    """The metrics defined on every feature of datasets of ``dataset_type``, registry order."""
    return tuple(
        info.name for info in METRICS if suitability(info.name, dataset_type) is Suitability.SUITED
    )


def is_auto(spec: PluginSpec) -> bool:
    """Whether ``spec`` is ``distance.metric: auto``."""
    return normalize_name(spec.name) == AUTO_METRIC


def feature_selection(config: ExperimentConfig, dataset: Dataset) -> FeatureSelection:
    """``distance.features`` as the core takes it: a keyword, or the indices of named features.

    Raises:
        ConfigError: A named feature is not in the dataset.
    """
    features = config.distance.features
    if isinstance(features, str):
        return features
    unknown = [name for name in features if name not in dataset.feature_names]
    if unknown:
        raise ConfigError(
            f"distance.features names unknown features {unknown} "
            f"(the dataset has {', '.join(dataset.feature_names)})"
        )
    return [dataset.feature_names.index(name) for name in features]


@dataclass(frozen=True)
class MetricChoice:
    """The metric a configuration runs on a dataset (ADR-022)."""

    spec: PluginSpec
    """The metric that is run, by its registry name, with its parameters — never ``auto``."""
    dataset_type: DatasetType
    """The type of the dataset."""
    automatic: bool
    """Chosen from ``distance.type_metrics`` because ``distance.metric`` is ``auto``."""
    quantitative_seen: int
    """Quantitative features the metric sees."""
    nominal_seen: int
    """Nominal features the metric sees."""
    quantitative: int
    """Quantitative features of the dataset."""
    nominal: int
    """Nominal features of the dataset."""

    @property
    def name(self) -> str:
        """Registry name of the metric."""
        return self.spec.name

    @property
    def label(self) -> str:
        """``manhattan (auto · quantitative dataset)``, ``minkowski {'p': 3.0}``."""
        params = f" {dict(self.spec.params)}" if self.spec.params else ""
        how = f" (auto · {self.dataset_type.value} dataset)" if self.automatic else ""
        return f"{self.spec.name}{params}{how}"

    @property
    def partial(self) -> bool:
        """The dataset has both feature types and the metric sees only one of them."""
        return self.dataset_type is DatasetType.HETEROGENEOUS and (
            self.quantitative_seen == 0 or self.nominal_seen == 0
        )

    @property
    def note(self) -> str:
        """Why the choice is flagged, or ``""``.

        It is flagged when ρ sees one feature type of a heterogeneous dataset.
        """
        if not self.partial:
            return ""
        seen, kind, other, missing = (
            (self.quantitative_seen, "quantitative", "nominal", self.nominal)
            if self.nominal_seen == 0
            else (self.nominal_seen, "nominal", "quantitative", self.quantitative)
        )
        return (
            f"{self.spec.name} sees only {seen} {kind} feature(s) of this heterogeneous dataset; "
            f"its {missing} {other} feature(s) do not count (a heterogeneous metric sees all)"
        )


def choose_metric(config: ExperimentConfig, dataset: Dataset) -> MetricChoice:
    """The metric ``config`` runs on ``dataset``: ``auto`` → the metric of its type (ADR-022).

    Raises:
        ConfigError: The metric is not defined on the dataset's features (a nominal metric on a
            quantitative dataset, a quantitative one on a nominal dataset), a metric of
            ``distance.type_metrics`` does not suit its type, or the feature selection is
            invalid.
        RegistryError: Unknown metric.
    """
    dataset_type = dataset.dataset_type
    configured = config.distance.metric
    automatic = is_auto(configured)
    spec = config.distance.type_metrics.for_type(dataset_type.value) if automatic else configured
    info = METRICS.info(spec.name)
    fit = suitability(info.name, dataset_type)
    domain = traits_of(info.obj).domain
    if automatic and fit is not Suitability.SUITED:
        raise ConfigError(
            f"distance.type_metrics.{dataset_type.value} = {info.name} is defined on {domain} "
            f"features only; {dataset_type.value} datasets need one of "
            f"{', '.join(suited_metrics(dataset_type))}"
        )
    if fit is Suitability.UNSUITED:
        raise ConfigError(
            f"{info.name} is defined on {domain} features only, and {dataset.name} is a "
            f"{dataset_type.value} dataset without {domain} features — choose auto or one of "
            f"{', '.join(suited_metrics(dataset_type))}"
        )
    mask = dataset.quantitative
    index = select_features(
        mask,
        feature_selection(config, dataset),
        domain=domain,
        names=dataset.feature_names,
        metric=info.name,
    )
    seen = mask[index]
    return MetricChoice(
        spec=PluginSpec(name=info.name, params=spec.params),
        dataset_type=dataset_type,
        automatic=automatic,
        quantitative_seen=int(seen.sum()),
        nominal_seen=int((~seen).sum()),
        quantitative=int(mask.sum()),
        nominal=int((~mask).sum()),
    )


def check_type_metrics(config: ExperimentConfig) -> None:
    """Check ``distance.type_metrics`` without a dataset.

    Every metric must be known, take its parameters and suit its type.

    Raises:
        ConfigError: A metric does not suit its type or has invalid parameters.
        RegistryError: Unknown metric.
    """
    for dataset_type in DatasetType:
        spec = config.distance.type_metrics.for_type(dataset_type.value)
        METRICS.make_params(spec.name, spec.params)
        if suitability(spec.name, dataset_type) is not Suitability.SUITED:
            raise ConfigError(
                f"distance.type_metrics.{dataset_type.value} = {spec.name} does not suit "
                f"{dataset_type.value} datasets; choose one of "
                f"{', '.join(suited_metrics(dataset_type))}"
            )


# ---------------------------------------------------------------- memory


def memory_estimate(m: int, n: int) -> int:
    """Bytes a run needs at its peak, roughly.

    The values of E₀ three times (as read, as stored, unified) and about four m × m matrices of
    8 bytes (distances, the metric's sum, the neighbour order). Measured: 46 MB for German
    (1000, 20, 2) and 410 MB for Spambase (4204, 57, 2), where this gives 31 MB and 545 MB.
    """
    return 8 * (3 * m * n + 4 * m * m)


def available_memory() -> int | None:
    """Free physical memory in bytes, or ``None`` where it cannot be asked (not Windows)."""
    if sys.platform != "win32":
        return None

    class _Status(ctypes.Structure):
        _fields_ = [  # the layout of MEMORYSTATUSEX
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("free_physical", ctypes.c_ulonglong),
            ("total_paging", ctypes.c_ulonglong),
            ("free_paging", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("free_virtual", ctypes.c_ulonglong),
            ("free_extended", ctypes.c_ulonglong),
        ]

    status = _Status()
    status.length = ctypes.sizeof(_Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.free_physical)


def megabytes(size: int) -> str:
    """``850 MB``, ``4.8 GB``."""
    return f"{size / 2**30:.1f} GB" if size >= 2**30 else f"{size / 2**20:.0f} MB"


def memory_warning(m: int, n: int, free: int | None = None) -> str:
    """A warning when a run on m objects and n features needs more memory than is free, or ``""``.

    ``free`` defaults to :func:`available_memory`.
    """
    need = memory_estimate(m, n)
    have = available_memory() if free is None else free
    if have is None or need <= have:
        return ""
    return (
        f"a run on {m} objects and {n} features needs about {megabytes(need)} of memory; "
        f"{megabytes(have)} are free — it may be slow or fail"
    )


# ---------------------------------------------------------------- summaries


@dataclass(frozen=True)
class DatasetSummary:
    """What ``erdr data info`` and the GUI's dataset page show."""

    name: str
    source: str | None
    m: int
    n: int
    classes: tuple[Label, ...]
    """Class labels in class order (K1, K2, …)."""
    class_sizes: tuple[int, ...]
    """|K1|, |K2|, …"""
    quantitative: tuple[str, ...]
    """Names of the features of set I."""
    nominal: tuple[str, ...]
    """Names of the features of set J."""
    dataset_type: DatasetType
    """Quantitative, nominal or heterogeneous (ADR-021)."""
    metrics: tuple[str, ...]
    """The metrics that suit the dataset type (ADR-022)."""
    metric: MetricChoice | None
    """The metric the configuration runs on the dataset; ``None`` if it cannot run."""
    metric_problem: str
    """Why the configured metric cannot run on the dataset, or ``""``."""
    permitted: PermittedK
    """The k rule: odd k from 3 to 2·min|Kᵢ| − 3."""
    largest_k: int
    """Largest k for which z(Sᵢ, k) exists (neighbours of any class)."""
    largest_k_own_class: int
    """Largest k for which z(Sᵢ, k) exists over the own class."""
    memory: int
    """Bytes a run needs, roughly (:func:`memory_estimate`)."""
    content_hash: str

    @property
    def shape(self) -> str:
        """``(7, 13, 2)``."""
        return f"({self.m}, {self.n}, {len(self.classes)})"

    @property
    def class_text(self) -> str:
        """``K1 = 1: 3 · K2 = 2: 4``."""
        return " · ".join(
            f"{class_name(i)} = {label}: {size}"
            for i, (label, size) in enumerate(zip(self.classes, self.class_sizes, strict=True))
        )


def summarize(dataset: Dataset, config: ExperimentConfig | None = None) -> DatasetSummary:
    """Summarize ``dataset`` for display.

    The metric is the one ``config`` (the default configuration when omitted) runs on it.
    """
    sizes = dataset.class_sizes
    present = [s for s in sizes if s > 0]
    names = dataset.feature_names
    quantitative = dataset.quantitative
    metric: MetricChoice | None = None
    problem = ""
    try:
        metric = choose_metric(config or ExperimentConfig(), dataset)
    except ERDRError as error:
        problem = str(error)
    return DatasetSummary(
        name=dataset.name,
        source=dataset.source,
        m=dataset.m,
        n=dataset.n,
        classes=dataset.classes,
        class_sizes=sizes,
        quantitative=tuple(name for name, q in zip(names, quantitative, strict=True) if q),
        nominal=tuple(name for name, q in zip(names, quantitative, strict=True) if not q),
        dataset_type=dataset.dataset_type,
        metrics=suited_metrics(dataset.dataset_type),
        metric=metric,
        metric_problem=problem,
        permitted=permitted_k(present),
        largest_k=largest_defined_k(present, ZScope.ALL) if len(present) > 1 else 0,
        largest_k_own_class=(
            largest_defined_k(present, ZScope.OWN_CLASS) if len(present) > 1 else 0
        ),
        memory=memory_estimate(dataset.m, dataset.n),
        content_hash=dataset.content_hash(),
    )
