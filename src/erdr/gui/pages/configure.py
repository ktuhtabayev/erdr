"""Configure page: Step 0 (normalizer, metric), Steps 1–6 (k, ε) and the readings A, B, C, z.

A switch set to something other than the literal article text is shown in the warning colours,
and so is the preset badge whenever the reading is not the literal one (ADR-003, ADR-019).

The metric follows the dataset type (ADR-022): ``auto`` takes the metric of the type — one per
type, chosen below it among the metrics that suit the type — and a metric that is not defined
on the loaded dataset's features cannot be chosen.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from erdr.config.io import load_config, save_config
from erdr.config.models import (
    AUTO_METRIC,
    DistanceConfig,
    ERDRConfig,
    ExperimentConfig,
    PluginSpec,
    PreprocessingConfig,
    ReadingsConfig,
    TypeMetricsConfig,
)
from erdr.config.presets import PresetName, matching_preset, preset, reading_notes
from erdr.core.k_rule import permitted_k
from erdr.core.metrics import METRICS, traits_of
from erdr.core.normalizers import NORMALIZERS
from erdr.core.readings import BlockedCover, SelfInL, Step5Return, ZScope
from erdr.data.schema import Dataset, DatasetType
from erdr.errors import ERDRError
from erdr.gui.forms import ParamsForm
from erdr.gui.state import AppState
from erdr.gui.widgets import Page, WarningBox, badge, hint
from erdr.services.datasets import (
    Suitability,
    choose_metric,
    is_auto,
    suitability,
    suited_metrics,
)

CONFIG_FILTER = "Configurations (*.yaml *.yml *.toml *.json);;All files (*)"
READING_CHOICES: dict[str, list[tuple[str, Any]]] = {
    "self_in_l": [
        ("A = 1 · Sᵢ is in its own L when g(Sᵢ) > 1 (literal)", SelfInL.INCLUDED),
        ("A = 2 · only other objects form L", SelfInL.EXCLUDED),
    ],
    "blocked_cover": [
        ("B = 1 · processed objects keep covering (literal)", BlockedCover.KEPT),
        ("B = 2 · only waiting objects (and Sᵢ) can be in L", BlockedCover.DROPPED),
    ],
    "step5_return": [
        ("C = 1 · back to Step 2 after the whole L (literal)", Step5Return.AFTER_ALL),
        ("C = 2 · back to Step 2 after the first move", Step5Return.FIRST_MOVE),
    ],
    "z_scope": [
        ("z(Sᵢ, k) over neighbours of any class (workbook)", ZScope.ALL),
        ("z(Sᵢ, k) over the own class only", ZScope.OWN_CLASS),
    ],
}


class ConfigurePage(Page):
    """Edit the experiment configuration; every change goes to the shared state at once."""

    title = "Configure"
    explanation = (
        "The defaults reproduce the ERDR workbook: min–max scaling, the Zhuravlev metric, k = 3, "
        "ε = 0.001 and the literal reading of §1.1 (A = B = C = 1). The metric follows the "
        "dataset type (auto): Zhuravlev on heterogeneous data, its Manhattan or Hamming part on "
        "quantitative or nominal data — the same distances. The article leaves three points "
        "open; the readings A, B, C and the scope of z switch between them — a reading other "
        "than the literal one is flagged everywhere."
    )

    def __init__(
        self, state: AppState, report: Callable[[str, str], None], parent: QWidget | None = None
    ) -> None:
        """The editors, grouped by the steps of the algorithm."""
        super().__init__(parent)
        self.state = state
        self.report = report
        self._loading = False

        # the title row, as in the template: which preset matches, and the presets
        self.preset_badge = badge()
        self.literal_button = QPushButton("Literal preset")
        self.closest_button = QPushButton("Closest preset")
        self.reset_button = QPushButton("Reset")
        self.literal_button.setToolTip("A = B = C = 1, z over any class — the article's text")
        self.closest_button.setToolTip(
            "B = 2 with the own-class z — closest to the article's Table 1"
        )
        self.reset_button.setToolTip("Every setting back to the default (the workbook's)")
        self.header.addWidget(QLabel("Matches preset:"))
        self.header.addWidget(self.preset_badge)
        for button in (self.literal_button, self.closest_button, self.reset_button):
            self.header.addWidget(button)
        self.warning = WarningBox()
        self.content.addWidget(self.warning)

        columns = QHBoxLayout()
        step0 = QGroupBox("Step 0 · scale unification and metric")
        form0 = QFormLayout(step0)
        self.normalizer_box = QComboBox()
        for normalizer_info in NORMALIZERS:
            self.normalizer_box.addItem(normalizer_info.name, normalizer_info.name)
            self.normalizer_box.setItemData(
                self.normalizer_box.count() - 1,
                normalizer_info.summary,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.normalizer_params = ParamsForm()
        self.normalizer_note = hint("", "note")
        self.metric_box = QComboBox()
        self.metric_box.addItem("auto — the metric of the dataset type", AUTO_METRIC)
        self.metric_box.setItemData(
            0,
            "Quantitative, nominal and heterogeneous datasets each get their metric "
            "(distance.type_metrics, below)",
            Qt.ItemDataRole.ToolTipRole,
        )
        for info in METRICS:
            domain = traits_of(info.obj).domain
            label = info.name + ("" if domain == "any" else f"  ({domain} features)")
            self.metric_box.addItem(label, info.name)
            self.metric_box.setItemData(
                self.metric_box.count() - 1, info.summary, Qt.ItemDataRole.ToolTipRole
            )
        self.metric_params = ParamsForm()
        self.metric_note = hint("", "note")
        self.type_metric_boxes: dict[DatasetType, QComboBox] = {}
        for kind in DatasetType:
            type_box = QComboBox()
            for name in suited_metrics(kind):
                type_box.addItem(name, name)
                type_box.setItemData(
                    type_box.count() - 1, METRICS.info(name).summary, Qt.ItemDataRole.ToolTipRole
                )
            type_box.setToolTip(f"The metric auto takes on {kind.value} datasets")
            self.type_metric_boxes[kind] = type_box
        self.features = QComboBox()
        for value, text in (
            ("auto", "auto — the metric's domain"),
            ("all", "all features (I ∪ J)"),
            ("quantitative", "quantitative features (I)"),
            ("nominal", "nominal features (J)"),
        ):
            self.features.addItem(text, value)
        self.decimals = QSpinBox()
        self.decimals.setRange(0, 15)
        form0.addRow("Normalizer", self.normalizer_box)
        form0.addRow("", self.normalizer_note)
        form0.addRow(self.normalizer_params)
        form0.addRow("Metric ρ", self.metric_box)
        for kind, type_box in self.type_metric_boxes.items():
            form0.addRow(f"  auto · {kind.value}", type_box)
        form0.addRow("", self.metric_note)
        form0.addRow(self.metric_params)
        self.form0 = form0
        form0.addRow("Features", self.features)
        form0.addRow("Distance decimals", self.decimals)
        columns.addWidget(step0, 1)

        right = QGroupBox("Steps 1–6 · k, ε and the readings of §1.1")
        form1 = QFormLayout(right)
        self.k = QSpinBox()
        self.k.setRange(1, 100_000)
        self.permitted = QLabel()
        self.permitted.setObjectName("note")
        self.k_rule = QComboBox()
        for value in ("enforce", "warn", "off"):
            self.k_rule.addItem(value, value)
        self.epsilon = QDoubleSpinBox()
        self.epsilon.setDecimals(6)
        self.epsilon.setRange(0.000001, 1000.0)
        self.d_decimals = QSpinBox()
        self.d_decimals.setRange(0, 15)
        form1.addRow("k of z(Sᵢ, k)", self.k)
        form1.addRow("", self.permitted)
        form1.addRow("k rule", self.k_rule)
        form1.addRow("ε (blocking)", self.epsilon)
        form1.addRow("d decimals", self.d_decimals)
        self.readings: dict[str, QComboBox] = {}
        for field, choices in READING_CHOICES.items():
            box = QComboBox()
            for text, value in choices:
                box.addItem(text, value)
            self.readings[field] = box
        form1.addRow("Reading A", self.readings["self_in_l"])
        form1.addRow("Reading B", self.readings["blocked_cover"])
        form1.addRow("Reading C", self.readings["step5_return"])
        form1.addRow("Scope of z", self.readings["z_scope"])
        columns.addWidget(right, 1)
        self.content.addLayout(columns)
        self.content.addStretch(1)

        for box in (
            self.normalizer_box,
            self.metric_box,
            *self.type_metric_boxes.values(),
            self.features,
            self.k_rule,
            *self.readings.values(),
        ):
            box.currentIndexChanged.connect(self._edited)
        for spin in (self.decimals, self.k, self.d_decimals):
            spin.valueChanged.connect(self._edited)
        self.epsilon.valueChanged.connect(self._edited)
        self.normalizer_params.changed.connect(self._edited)
        self.metric_params.changed.connect(self._edited)
        self.literal_button.clicked.connect(lambda: self.apply_preset(PresetName.LITERAL))
        self.closest_button.clicked.connect(lambda: self.apply_preset(PresetName.CLOSEST))
        self.reset_button.clicked.connect(lambda: self.show_config(ExperimentConfig()))
        state.configChanged.connect(self._external)
        state.datasetChanged.connect(self._dataset)
        self.show_config(state.config)

    # ------------------------------------------------------------------ state → widgets

    def show_config(self, config: ExperimentConfig) -> None:
        """Put ``config`` into the editors and the shared state."""
        self._loading = True
        try:
            self._select(self.normalizer_box, config.preprocessing.normalizer.name)
            self.normalizer_params.set_plugin(
                NORMALIZERS,
                config.preprocessing.normalizer.name,
                dict(config.preprocessing.normalizer.params),
            )
            metric = config.distance.metric
            if is_auto(metric):
                self._select(self.metric_box, AUTO_METRIC)
                self.metric_params.clear()
            else:
                self._select(self.metric_box, METRICS.info(metric.name).name)
                self.metric_params.set_plugin(METRICS, metric.name, dict(metric.params))
            for kind, type_box in self.type_metric_boxes.items():
                spec = config.distance.type_metrics.for_type(kind.value)
                self._select(type_box, METRICS.info(spec.name).name)
            features = (
                config.distance.features if isinstance(config.distance.features, str) else "auto"
            )
            self._select(self.features, features)
            self.decimals.setValue(config.distance.decimals)
            self.k.setValue(config.erdr.k)
            self._select(self.k_rule, config.erdr.k_rule)
            self.epsilon.setValue(config.erdr.epsilon)
            self.d_decimals.setValue(config.erdr.d_decimals)
            r = config.erdr.readings
            for field, value in (
                ("self_in_l", r.self_in_l),
                ("blocked_cover", r.blocked_cover),
                ("step5_return", r.step5_return),
                ("z_scope", r.z_scope),
            ):
                self._select(self.readings[field], value)
            self._base = config
        finally:
            self._loading = False
        self.state.set_config(config)
        self._refresh(config)

    @staticmethod
    def _select(box: QComboBox, value: object) -> None:
        index = box.findData(value)
        if index >= 0:
            box.setCurrentIndex(index)

    def _external(self, config: ExperimentConfig) -> None:
        if config != self.current():
            self.show_config(config)

    def _dataset(self, dataset: Dataset | None) -> None:
        self._refresh(self.state.config)

    # ------------------------------------------------------------------ widgets → state

    def current(self) -> ExperimentConfig:
        """The configuration the editors describe."""
        base = getattr(self, "_base", self.state.config)
        normalizer = str(self.normalizer_box.currentData())
        metric = str(self.metric_box.currentData())
        params = {} if metric == AUTO_METRIC else self.metric_params.values()
        readings = ReadingsConfig(
            self_in_l=self.readings["self_in_l"].currentData(),
            blocked_cover=self.readings["blocked_cover"].currentData(),
            step5_return=self.readings["step5_return"].currentData(),
            z_scope=self.readings["z_scope"].currentData(),
        )
        explicit = base.distance.features if not isinstance(base.distance.features, str) else None
        chosen_features = self.features.currentData()
        return base.model_copy(
            update={
                "preprocessing": PreprocessingConfig(
                    normalizer=PluginSpec(name=normalizer, params=self.normalizer_params.values())
                ),
                "distance": DistanceConfig(
                    metric=PluginSpec(name=metric, params=params),
                    type_metrics=self._type_metrics(base),
                    features=explicit
                    if explicit and chosen_features == "auto"
                    else chosen_features,
                    decimals=self.decimals.value(),
                ),
                "erdr": ERDRConfig(
                    k=self.k.value(),
                    k_rule=self.k_rule.currentData(),
                    epsilon=self.epsilon.value(),
                    d_decimals=self.d_decimals.value(),
                    readings=readings,
                ),
            }
        )

    def _type_metrics(self, base: ExperimentConfig) -> TypeMetricsConfig:
        """The metric of each dataset type; a metric kept from ``base`` keeps its parameters."""
        chosen: dict[str, PluginSpec] = {}
        for kind, type_box in self.type_metric_boxes.items():
            name = str(type_box.currentData())
            before = base.distance.type_metrics.for_type(kind.value)
            chosen[kind.value] = PluginSpec(
                name=name, params=before.params if before.name == name else {}
            )
        return TypeMetricsConfig(**chosen)

    def _edited(self) -> None:
        if self._loading:
            return
        sender = self.sender()
        if sender is self.normalizer_box:
            self.normalizer_params.set_plugin(
                NORMALIZERS, str(self.normalizer_box.currentData()), {}
            )
        if sender is self.metric_box:
            metric = str(self.metric_box.currentData())
            if metric == AUTO_METRIC:
                self.metric_params.clear()
            else:
                self.metric_params.set_plugin(METRICS, metric, {})
        try:
            config = self.current()
        except (ERDRError, ValueError) as error:
            self.report("Invalid setting", str(error))
            return
        self.state.set_config(config)
        self._refresh(config)

    @staticmethod
    def _flag(widget: QWidget, name: str, value: object) -> None:
        """Set a style-sheet property and restyle the widget."""
        if widget.property(name) != value:
            widget.setProperty(name, value)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _refresh(self, config: ExperimentConfig) -> None:
        chosen = matching_preset(config)
        self.preset_badge.setText(chosen.value if chosen else "custom")
        self.normalizer_note.setText(NORMALIZERS.info(config.preprocessing.normalizer.name).summary)
        dataset = self.state.dataset
        metric_note, metric_warning = self._metric_texts(config, dataset)
        self.metric_note.setText(metric_note)
        self._mark_metrics(dataset)
        automatic = is_auto(config.distance.metric)
        for type_box in self.type_metric_boxes.values():
            self.form0.setRowVisible(type_box, automatic)
        notes = reading_notes(config)
        for field, box in self.readings.items():
            literal = READING_CHOICES[field][0][1]  # the first choice is the article's text
            flagged = box.currentData() != literal
            self._flag(box, "flagged", flagged)
            box.setToolTip(
                "⚠ Not the literal article reading" if flagged else "The literal article reading"
            )
        self.preset_badge.setObjectName("warningBadge" if notes else "badge")
        self._flag(self.preset_badge, "literal", not notes)
        messages = []
        if notes:
            messages.append(
                "⚠ Not the literal article reading: " + "; ".join(n.statement for n in notes)
            )
        if metric_warning:
            messages.append(f"⚠ {metric_warning}")
        self.warning.set_text("\n".join(messages))
        if dataset is None:
            self.permitted.setText("k rule: odd k from 3 to 2·min|Kᵢ| − 3 (load a dataset)")
        else:
            sizes = [s for s in dataset.class_sizes if s > 0]
            rule = permitted_k(sizes)
            ok = "✓" if config.erdr.k in rule else "⚠ outside the rule"
            self.permitted.setText(f"permitted for {dataset.name}: {rule.text}   {ok}")

    @staticmethod
    def _metric_texts(config: ExperimentConfig, dataset: Dataset | None) -> tuple[str, str]:
        """(note under the metric, ⚠ text or ``""``) for ``config`` on ``dataset``."""
        metric = config.distance.metric
        if dataset is None:
            if is_auto(metric):
                return (
                    "the metric of the dataset type: "
                    + " · ".join(
                        f"{kind.value} → {config.distance.type_metrics.for_type(kind.value).name}"
                        for kind in DatasetType
                    ),
                    "",
                )
            return METRICS.info(metric.name).summary, ""
        try:
            choice = choose_metric(config, dataset)
        except ERDRError as error:
            return "", str(error)
        summary = METRICS.info(choice.name).summary
        if choice.automatic:
            summary = f"{dataset.name} is a {choice.dataset_type.value} dataset → {choice.name}: "
            summary += METRICS.info(choice.name).summary
        return summary, choice.note

    def _mark_metrics(self, dataset: Dataset | None) -> None:
        """Disable the metrics that are not defined on the dataset's features (ADR-022)."""
        model = self.metric_box.model()
        if not isinstance(model, QStandardItemModel):
            return
        for row in range(self.metric_box.count()):
            name = str(self.metric_box.itemData(row))
            if name == AUTO_METRIC:
                continue
            fit = suitability(name, dataset.dataset_type) if dataset else Suitability.SUITED
            domain = traits_of(METRICS.get(name)).domain
            item = model.item(row)
            item.setEnabled(fit is not Suitability.UNSUITED)
            reason = {
                Suitability.SUITED: "",
                Suitability.PARTIAL: f" — sees only the {domain} features of this dataset",
                Suitability.UNSUITED: f" — not defined here: the dataset has no {domain} features",
            }[fit]
            item.setToolTip(METRICS.info(name).summary + reason)

    def apply_preset(self, name: PresetName | str) -> None:
        """Apply the readings of a preset (the other settings stay)."""
        current = self.current()
        readings = preset(name).erdr.readings
        self.show_config(
            current.model_copy(
                update={"erdr": current.erdr.model_copy(update={"readings": readings})}
            )
        )

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a configuration", "", CONFIG_FILTER)
        if path:
            self.open(Path(path))

    def open(self, path: Path) -> bool:
        """Load a configuration file."""
        try:
            config = load_config(path)
        except ERDRError as error:
            self.report("Cannot load the configuration", str(error))
            return False
        self.show_config(config)
        return True

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the configuration", "erdr.yaml", CONFIG_FILTER
        )
        if path:
            try:
                save_config(self.current(), Path(path), overwrite=True)
            except ERDRError as error:
                self.report("Cannot save the configuration", str(error))
