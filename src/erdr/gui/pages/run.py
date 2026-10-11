"""Run page: run ERDR in the background, watch the log, optionally save a run folder.

The settings of the run are shown as parameter chips, the reading in the warning colours when it
is not the literal one, and the outcome in the colours of the samples D and F (ADR-019).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from erdr.config.models import ExperimentConfig
from erdr.data.schema import Dataset
from erdr.gui.state import AppState
from erdr.gui.widgets import LogBridge, Page, chip
from erdr.gui.workers import TaskRunner
from erdr.notation import object_set
from erdr.services.experiment import ExperimentResult, run_experiment
from erdr.services.runs import save_run


def run_job(
    config: ExperimentConfig, dataset: Dataset, save: bool, runs_dir: Path
) -> tuple[ExperimentResult, str | None]:
    """Run ERDR and, if asked, save the run folder (in the worker thread)."""
    result = run_experiment(config, dataset)
    folder = save_run(result, runs_dir) if save else None
    return result, str(folder) if folder else None


class RunPage(Page):
    """Start a run of the current dataset and configuration."""

    title = "Run"
    explanation = (
        "Runs Step 0 (scaling and distances), Step 1 (r, g, z, d), the queue and every iteration "
        "of Steps 2–5 in the background. The result — the training sample D and the validation "
        "sample F — appears on the Results page; a saved run folder can be repeated and exported."
    )
    finished = Signal(bool)
    """The run ended (``True`` if it succeeded)."""

    def __init__(
        self, state: AppState, report: Callable[[str, str], None], parent: QWidget | None = None
    ) -> None:
        """The button, the options, the progress bar, the log and the result."""
        super().__init__(parent)
        self.state = state
        self.report = report
        self.tasks = TaskRunner(self)
        self.runs_dir = Path("runs")
        self.context = QLabel()
        self.context.setWordWrap(True)
        self.content.addWidget(self.context)
        row = QHBoxLayout()
        self.start_button = QPushButton("Run ERDR")
        self.start_button.setObjectName("primary")
        self.save = QCheckBox("Save a run folder (runs/…)")
        row.addWidget(self.start_button)
        row.addWidget(self.save)
        row.addStretch(1)
        self.content.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.content.addWidget(self.progress)
        self.outcome = QLabel()
        self.outcome.setWordWrap(True)
        self.content.addWidget(self.outcome)
        self.log = QPlainTextEdit()
        self.log.setObjectName("console")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.content.addWidget(self.log, 1)
        self.log_bridge = LogBridge(self)
        self.log_bridge.attach(self.log.appendPlainText)
        self.start_button.clicked.connect(self.start)
        state.datasetChanged.connect(lambda _: self._context())
        state.configChanged.connect(lambda _: self._context())
        state.resultChanged.connect(self._show)
        self._context()

    def _context(self) -> None:
        dataset = self.state.dataset
        config = self.state.config
        reading = config.erdr.readings.to_readings()
        name = dataset.name if dataset else "no dataset loaded"
        parameters = " ".join(
            chip(text, "parameter")
            for text in (
                f"k = {config.erdr.k}",
                config.preprocessing.normalizer.name,
                config.distance.metric.name,
                f"ε = {config.erdr.epsilon:g}",
            )
        )
        flag = "literal" if reading.is_literal else "warning"
        self.context.setText(f"<b>{name}</b> &nbsp; {parameters} {chip(reading.label, flag)}")
        self.start_button.setEnabled(dataset is not None and not self.tasks.busy())

    def is_running(self) -> bool:
        """Whether a run is in progress."""
        return self.tasks.busy()

    def start(self) -> None:
        """Run ERDR on the current dataset and configuration."""
        dataset = self.state.dataset
        if dataset is None or self.tasks.busy():
            return
        config = self.state.config
        save, runs_dir = self.save.isChecked(), self.runs_dir
        self.start_button.setEnabled(False)
        self.progress.setRange(0, 0)  # busy
        self.outcome.setText("Running…")
        self.tasks.start(
            lambda: run_job(config, dataset, save, runs_dir), self._succeeded, self._failed
        )

    def _succeeded(self, value: object) -> None:
        result, folder = cast(tuple[ExperimentResult, str | None], value)
        self._stop()
        self.state.set_result(result, folder)
        self.finished.emit(True)

    def _failed(self, message: str) -> None:
        self._stop()
        self.outcome.setText("The run failed.")
        self.report("The run failed", message)
        self.finished.emit(False)

    def _stop(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self._context()

    def _show(self, result: ExperimentResult | None) -> None:
        if result is None:
            self.outcome.setText("")
            return
        names = result.object_names
        small = result.dataset.m <= 60
        d_set = object_set(result.result.training, names) if small else ""
        f_set = object_set(result.result.validation, names) if small else ""
        notes = "".join(
            f"<br>{chip(f'⚠ {note}', 'warning', bold=False)}"
            for note in (*result.notes, *result.warnings)
        )
        saved = f"<br>Saved: {self.state.saved_run}" if self.state.saved_run else ""
        training = chip(f"D (training): {result.result.training.size}", "D")
        validation = chip(f"F (validation): {result.result.validation.size}", "F")
        self.outcome.setText(
            f"{training} {d_set} · {validation} {f_set} · "
            f"{len(result.result.iterations)} iterations · "
            f"{sum(c.occurs for c in result.cases)} of {len(result.cases)} cases · "
            f"{result.seconds:.3f} s{notes}{saved}"
        )

    def cancel(self) -> None:
        """Nothing to interrupt mid-way: a run is short; :meth:`wait` lets it end."""

    def wait(self) -> bool:
        """Wait for a running task (tests, closing the window)."""
        return self.tasks.wait()
