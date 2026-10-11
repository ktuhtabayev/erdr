"""Readings & k page: every reading of §1.1, and the training-sample size for many k.

Switch values of the literal article text are green, the ones that differ orange; the figures
keep one colour per reading — the literal reading green, the closest blue (ADR-019).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from erdr.core.readings import CLOSEST, LITERAL, Readings, ZScope
from erdr.export.figures import readings_figure, sweep_figure
from erdr.export.tables import readings_table, sweep_table
from erdr.gui.state import AppState
from erdr.gui.widgets import FigureView, Legend, Page, TableView, section_title
from erdr.gui.workers import TaskRunner
from erdr.services.analysis import Progress, compare_readings, sweep_k


def parse_ks(text: str) -> list[int] | None:
    """``3, 5, 7`` or ``3-41`` (odd steps) → the k values; empty text → ``None`` (permitted k).

    Raises:
        ValueError: The text is not a list of integers or ranges.
    """
    values: list[int] = []
    for part in (p.strip() for p in text.split(",")):
        if not part:
            continue
        if "-" in part:
            low, high = (int(v) for v in part.split("-", 1))
            values += list(range(low, high + 1, 2 if low % 2 == high % 2 else 1))
        else:
            values.append(int(part))
    return values or None


class AnalysisPage(Page):
    """Compare the readings A, B, C and sweep k — sheets *Readings* and *Article Table 1 Check*."""

    title = "Readings & k"
    explanation = (
        "The article leaves open whether Sᵢ is in its own L (A), whether processed objects keep "
        "covering (B) and where Step 5 returns to Step 2 (C). Compare every combination on the "
        "current dataset, and see how the training-sample size |D| changes with k — on all 270 "
        "objects this reproduces the comparison with the article's Table 1."
    )

    def __init__(
        self, state: AppState, report: Callable[[str, str], None], parent: QWidget | None = None
    ) -> None:
        """Two groups: readings and the k sweep."""
        super().__init__(parent)
        self.state = state
        self.report = report
        self.tasks = TaskRunner(self)

        controls = QHBoxLayout()
        readings_box = QGroupBox("Readings A, B, C")
        rl = QHBoxLayout(readings_box)
        self.both_z = QCheckBox("also with the own-class z")
        self.readings_button = QPushButton("Compare readings")
        self.readings_button.setObjectName("primary")
        rl.addWidget(self.both_z)
        rl.addWidget(self.readings_button)
        controls.addWidget(readings_box)

        sweep_box = QGroupBox("Training-sample size by k")
        sl = QHBoxLayout(sweep_box)
        self.ks = QLineEdit()
        self.ks.setPlaceholderText("k values, e.g. 3,5,7 or 3-41 (empty: every permitted k)")
        self.use_literal = QCheckBox("literal")
        self.use_literal.setChecked(True)
        self.use_closest = QCheckBox("closest (B = 2, own-class z)")
        self.use_closest.setChecked(True)
        self.use_current = QCheckBox("current configuration")
        self.sweep_button = QPushButton("Run the sweep")
        self.sweep_button.setObjectName("primary")
        for widget in (
            QLabel("k:"),
            self.ks,
            self.use_literal,
            self.use_closest,
            self.use_current,
            self.sweep_button,
        ):
            sl.addWidget(widget)
        controls.addWidget(sweep_box, 1)
        self.content.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        self.content.addWidget(self.progress)

        splitter = QSplitter()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.readings_view = TableView()
        self.sweep_view = TableView()
        self.readings_legend = Legend()
        self.sweep_legend = Legend()
        ll.addWidget(section_title("Readings"))
        ll.addWidget(self.readings_view, 1)
        ll.addWidget(self.readings_legend)
        ll.addWidget(section_title("k sweep"))
        ll.addWidget(self.sweep_view, 1)
        ll.addWidget(self.sweep_legend)
        splitter.addWidget(left)
        self.figure_view = FigureView()
        splitter.addWidget(self.figure_view)
        splitter.setSizes([600, 500])
        self.content.addWidget(splitter, 1)

        self.readings_button.clicked.connect(self.compare)
        self.sweep_button.clicked.connect(self.sweep)
        state.analysisChanged.connect(self._show)
        state.datasetChanged.connect(lambda _: self._enable())
        self._enable()

    def _enable(self) -> None:
        ready = self.state.dataset is not None and not self.tasks.busy()
        self.readings_button.setEnabled(ready)
        self.sweep_button.setEnabled(ready)

    def _busy(self) -> None:
        self.progress.setRange(0, 0)
        self.readings_button.setEnabled(False)
        self.sweep_button.setEnabled(False)

    def _progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def _done(self) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self._enable()

    def compare(self) -> None:
        """Compare every reading in the background."""
        dataset, config = self.state.dataset, self.state.config
        if dataset is None:
            return
        scopes = (ZScope.ALL, ZScope.OWN_CLASS) if self.both_z.isChecked() else (ZScope.ALL,)
        self._busy()

        def job(progress: Progress) -> object:
            return compare_readings(dataset, config, z_scopes=scopes, progress=progress)

        self.tasks.start(job, self._compared, self._failed, self._progress, with_progress=True)

    def _compared(self, rows: object) -> None:
        self._done()
        self.state.set_readings(rows)  # type: ignore[arg-type]
        self._show_readings_figure()

    def sweep(self) -> None:
        """Run the k sweep in the background."""
        dataset, config = self.state.dataset, self.state.config
        if dataset is None:
            return
        try:
            ks = parse_ks(self.ks.text())
        except ValueError:
            self.report("Invalid k values", "Give k as 3,5,7 or as a range 3-41.")
            return
        chosen: list[Readings] = []
        if self.use_literal.isChecked():
            chosen.append(LITERAL)
        if self.use_closest.isChecked():
            chosen.append(CLOSEST)
        current = config.erdr.readings.to_readings()
        if self.use_current.isChecked() and current not in chosen:
            chosen.append(current)
        if not chosen:
            self.report("No reading chosen", "Tick at least one reading for the sweep.")
            return
        self._busy()

        def job(progress: Progress) -> object:
            return sweep_k(dataset, config, ks=ks, readings=chosen, progress=progress)

        self.tasks.start(job, self._swept, self._failed, self._progress, with_progress=True)

    def _swept(self, rows: object) -> None:
        self._done()
        self.state.set_sweep(rows)  # type: ignore[arg-type]
        self._show_sweep_figure()

    def _failed(self, message: str) -> None:
        self._done()
        self.report("The analysis failed", message)

    def _show(self) -> None:
        dataset = self.state.dataset
        if dataset is None:
            return
        labels = dataset.classes
        if self.state.readings:
            table = readings_table(self.state.readings, dataset.object_ids, len(labels))
            self.readings_view.show_table(table, class_labels=labels)
            self.readings_legend.show_table(table, labels)
        else:
            self.readings_view.setModel(None)
            self.readings_legend.show_table(None)
        if self.state.sweep:
            table = sweep_table(self.state.sweep, len(labels))
            self.sweep_view.show_table(table, class_labels=labels)
            self.sweep_legend.show_table(table, labels)
        else:
            self.sweep_view.setModel(None)
            self.sweep_legend.show_table(None)

    def _show_readings_figure(self) -> None:
        if self.state.readings and self.state.dataset is not None:
            self.figure_view.show_figure(readings_figure(self.state.readings, self.state.dataset.m))

    def _show_sweep_figure(self) -> None:
        if self.state.sweep and self.state.dataset is not None:
            self.figure_view.show_figure(sweep_figure(self.state.sweep, self.state.dataset.m))

    def wait(self) -> bool:
        """Wait for a running analysis."""
        return self.tasks.wait()
