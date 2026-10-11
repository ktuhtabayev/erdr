"""The application state shared by the pages: dataset, configuration, run, analyses.

Pages change the state and listen to its signals; nothing else connects them (ADR-012).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from erdr.config.models import ExperimentConfig
from erdr.data.schema import Dataset
from erdr.services.analysis import ReadingRow, SweepRow
from erdr.services.experiment import ExperimentResult


class AppState(QObject):
    """Dataset → configuration → run → analyses, with a signal for each change."""

    datasetChanged = Signal(object)
    """The new :class:`~erdr.data.schema.Dataset` (or ``None``)."""
    configChanged = Signal(object)
    """The new :class:`~erdr.config.models.ExperimentConfig`."""
    resultChanged = Signal(object)
    """The new :class:`~erdr.services.experiment.ExperimentResult` (or ``None``)."""
    analysisChanged = Signal()
    """The readings comparison or the k sweep changed."""

    def __init__(self, parent: QObject | None = None) -> None:
        """Start with no dataset and the literal configuration."""
        super().__init__(parent)
        self.dataset: Dataset | None = None
        self.config = ExperimentConfig()
        self.result: ExperimentResult | None = None
        self.readings: tuple[ReadingRow, ...] | None = None
        self.sweep: tuple[SweepRow, ...] | None = None
        self.saved_run: str | None = None

    def set_dataset(self, dataset: Dataset | None) -> None:
        """Replace the dataset; the run and the analyses of the previous one are dropped."""
        self.dataset = dataset
        self.datasetChanged.emit(dataset)
        self.clear_result()

    def set_config(self, config: ExperimentConfig) -> None:
        """Replace the configuration (the run stays until the next one)."""
        if config == self.config:
            return
        self.config = config
        self.configChanged.emit(config)

    def set_result(self, result: ExperimentResult | None, saved: str | None = None) -> None:
        """Replace the run."""
        self.result = result
        self.saved_run = saved
        self.resultChanged.emit(result)

    def set_readings(self, rows: tuple[ReadingRow, ...] | None) -> None:
        """Replace the readings comparison."""
        self.readings = rows
        self.analysisChanged.emit()

    def set_sweep(self, rows: tuple[SweepRow, ...] | None) -> None:
        """Replace the k sweep."""
        self.sweep = rows
        self.analysisChanged.emit()

    def clear_result(self) -> None:
        """Drop the run and the analyses."""
        self.set_result(None)
        self.readings = None
        self.sweep = None
        self.analysisChanged.emit()
