"""Typed experiment configuration (pydantic v2).

One :class:`ExperimentConfig` describes an ERDR run completely. Unknown keys are errors and
instances are immutable. The defaults are the **literal** article reading on the workbook's
settings (Zhuravlev metric, min–max scaling, k = 3, ε = 0.001, A = B = C = 1), which reproduces
the ERDR workbook exactly (ADR-002); :mod:`.presets` holds the named presets. The metric is
``auto``: the Zhuravlev metric on heterogeneous data and, on single-type data, its part that
the data have — the same distances (ADR-022).

Pluggable components are :class:`PluginSpec` values (registry name + parameters). Their
parameters are validated by the component's own parameter type when they are resolved.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from erdr.core.readings import BlockedCover, Readings, SelfInL, Step5Return, ZScope


class ConfigModel(BaseModel):
    """Base of all configuration models: strict keys, immutable, field docs as descriptions."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        use_attribute_docstrings=True,
    )


class PluginSpec(ConfigModel):
    """A pluggable component chosen by registry name, with its parameters.

    In YAML a bare name is accepted as shorthand: ``normalizer: minmax``.
    """

    name: str = Field(min_length=1)
    """Registry name (case-insensitive; ``_`` and spaces count as ``-``)."""
    params: dict[str, JsonValue] = Field(default_factory=dict)
    """Keyword parameters, validated by the component's parameter type when it is resolved."""

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_name(cls, value: Any) -> Any:
        return {"name": value} if isinstance(value, str) else value


def plugin(name: str, **params: JsonValue) -> PluginSpec:
    """Shorthand constructor: ``plugin("minkowski", p=3)``."""
    return PluginSpec(name=name, params=params)


class DatasetConfig(ConfigModel):
    """Where the data comes from and how to read it."""

    path: str | None = None
    """A dataset file (relative paths: against the configuration file's folder), a dataset of the
    project's ``datasets`` folder by id or name (``heart-disease-270``), ``builtin:<name>``, or
    ``None`` for the default dataset (``datasets/default.dat``; ADR-007)."""
    format: Literal[
        "auto", "erdr-workbook", "extended", "template-extended", "csv", "xlsx", "parquet"
    ] = "auto"
    """``auto`` picks the loader from the file extension and content."""
    sheet: str | None = None
    """Sheet name for Excel files (the ERDR workbook uses ``Dataset``)."""
    class_column: str | None = None
    """Column holding the class label (tabular formats)."""
    id_column: str | None = None
    """Optional column of object ids."""
    feature_types: dict[str, Literal["quantitative", "nominal"]] | None = None
    """Feature name → type (set I or J); overrides types stored in the file."""
    missing_values: Literal["error"] = "error"
    """Policy for missing values; only ``error`` (ADR-007)."""


class PreprocessingConfig(ConfigModel):
    """Step 0 · scale unification, fitted on the objects of E₀."""

    normalizer: PluginSpec = Field(default_factory=lambda: plugin("minmax"))
    """Fractional-linear (min–max) transform of the quantitative features by default."""


AUTO_METRIC = "auto"
"""``distance.metric: auto`` — the metric of the dataset's type (``distance.type_metrics``)."""


class TypeMetricsConfig(ConfigModel):
    """The metric ``distance.metric: auto`` chooses for each dataset type (ADR-022).

    The defaults are the Zhuravlev metric of the article (§3) and its two parts: on a dataset
    without nominal features it is the Manhattan distance of the unified values, on a dataset
    without quantitative features the Hamming distance — bit for bit, so ``auto`` gives the
    literal results on every dataset.
    """

    quantitative: PluginSpec = Field(default_factory=lambda: plugin("manhattan"))
    """For datasets whose features are all quantitative: a quantitative or heterogeneous metric."""
    nominal: PluginSpec = Field(default_factory=lambda: plugin("hamming"))
    """For datasets whose features are all nominal: a nominal or heterogeneous metric."""
    heterogeneous: PluginSpec = Field(default_factory=lambda: plugin("zhuravlev"))
    """For datasets with both feature types: a heterogeneous metric."""

    def for_type(self, dataset_type: str) -> PluginSpec:
        """The metric for ``quantitative``, ``nominal`` or ``heterogeneous`` datasets."""
        spec: PluginSpec = getattr(self, str(dataset_type))
        return spec


class DistanceConfig(ConfigModel):
    """Step 0 · the metric ρ and the features it sees."""

    metric: PluginSpec = Field(default_factory=lambda: plugin(AUTO_METRIC))
    """``auto`` (default): the metric of the dataset's type from ``type_metrics`` — the Zhuravlev
    metric of the article (§3) on heterogeneous data; or a metric by name for every dataset."""
    type_metrics: TypeMetricsConfig = Field(default_factory=TypeMetricsConfig)
    """The metric of each dataset type when ``metric`` is ``auto``."""
    features: Literal["auto", "all", "quantitative", "nominal"] | tuple[str, ...] = "auto"
    """``auto`` (the metric's domain: all features for heterogeneous metrics, set I for Euclidean
    and the like, set J for Hamming), ``all``, ``quantitative``, ``nominal`` or feature names."""
    decimals: int = Field(10, ge=0, le=15)
    """Distances are rounded to this many decimals so that equal distances tie exactly."""

    @field_validator("features")
    @classmethod
    def _explicit_subset_is_a_set(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        if isinstance(value, tuple):
            if not value:
                raise ValueError("an explicit feature subset must not be empty")
            if len(set(value)) != len(value):
                raise ValueError("an explicit feature subset must not repeat a feature")
        return value


class ReadingsConfig(ConfigModel):
    """The readings of the points §1.1 leaves open (ADR-003); the defaults are literal."""

    self_in_l: SelfInL = SelfInL.INCLUDED
    """A · ``included`` (A = 1, literal): Sᵢ ∈ L whenever g(Sᵢ) > 1; ``excluded`` (A = 2)."""
    blocked_cover: BlockedCover = BlockedCover.KEPT
    """B · ``kept`` (B = 1, literal): processed objects still cover; ``dropped`` (B = 2)."""
    step5_return: Step5Return = Step5Return.AFTER_ALL
    """C · ``after-all`` (C = 1): back to Step 2 after the whole L; ``first-move`` (C = 2)."""
    z_scope: ZScope = ZScope.ALL
    """z(Sᵢ, k) over neighbours of ``all`` classes (workbook) or of the ``own-class`` only."""

    def to_readings(self) -> Readings:
        """The core's :class:`~erdr.core.readings.Readings`."""
        return Readings(self.self_in_l, self.blocked_cover, self.step5_return, self.z_scope)

    @classmethod
    def from_readings(cls, readings: Readings) -> ReadingsConfig:
        """The configuration section of a core reading."""
        return cls(
            self_in_l=readings.self_in_l,
            blocked_cover=readings.blocked_cover,
            step5_return=readings.step5_return,
            z_scope=readings.z_scope,
        )


class ERDRConfig(ConfigModel):
    """Steps 1–6 · the parameters of the algorithm."""

    k: int = Field(3, ge=1)
    """k of z(Sᵢ, k), the distance to the k-th nearest neighbour."""
    k_rule: Literal["enforce", "warn", "off"] = "enforce"
    """The k rule (odd k from 3 to 2·min|Kᵢ| − 3, ADR-005): ``enforce`` rejects another k,
    ``warn`` logs a warning, ``off`` only requires that z(Sᵢ, k) exists."""
    epsilon: float = Field(0.001, gt=0.0)
    """ε > 0 of the blocking d(Sᵢ) ← −(d(Sᵢ) + ε); any ε > 0 gives the same result."""
    d_decimals: int = Field(10, ge=0, le=15)
    """d(Sᵢ) is rounded to this many decimals so that equal priorities tie exactly."""
    readings: ReadingsConfig = Field(default_factory=ReadingsConfig)
    """The readings A, B, C and the scope of z."""


class OutputConfig(ConfigModel):
    """Where runs are written and what they contain."""

    runs_dir: str = "runs"
    """Each run gets ``<runs_dir>/<YYYYMMDD_HHMMSS>_<config hash>/`` with its manifest."""
    dataset_formats: tuple[Literal["dat", "csv"], ...] = ("dat", "csv")
    """Formats of the training and validation samples written to a run folder."""


class ExperimentConfig(ConfigModel):
    """Complete description of one ERDR experiment."""

    schema_version: Literal[1] = 1
    """Version of this configuration format."""
    name: str = "erdr"
    """Short name of the experiment."""
    description: str = ""
    """Free text."""
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    preprocessing: PreprocessingConfig = Field(default_factory=PreprocessingConfig)
    distance: DistanceConfig = Field(default_factory=DistanceConfig)
    erdr: ERDRConfig = Field(default_factory=ERDRConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
