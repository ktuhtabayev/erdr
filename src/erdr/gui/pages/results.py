"""Results page: every table of the workbook for the current run, and the figures.

Each tab carries the colour of its stage, as the workbook's sheet tabs do; the legend under the
tabs explains the colours of the table on show (ADR-019).
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from erdr.export.figures import RUN_FIGURES, run_figure
from erdr.export.tables import Table, run_tables
from erdr.export.theme import STAGES, stage_of
from erdr.gui.state import AppState
from erdr.gui.widgets import FigureView, Legend, Page, TableView, swatch_icon
from erdr.services.experiment import ExperimentResult

TAB_NAMES = {
    "summary": "Key results",
    "dataset": "Dataset",
    "normalized": "Normalized",
    "distances": "ρ",
    "distances-quantitative": "ρ_I",
    "distances-nominal": "ρ_J",
    "neighbours": "Neighbours",
    "characteristics": "Step 1 · r, g, z, d",
    "spheres": "Spheres",
    "queue": "Step 2 · queue",
    "iterations": "Iterations",
    "counters": "Counters g",
    "routes": "D and F",
    "composition": "Composition",
    "cases": "Cases",
}
"""Tab titles per table key."""


class ResultsPage(Page):
    """The current run, table by table — the sheets of the ERDR workbook."""

    title = "Results"
    explanation = (
        "Every table of the ERDR workbook for the current run; a tab's square is the colour of its "
        "stage. Column headers are coloured by what they hold (feature type, class, r g z, d, "
        "sample) and cells by what they mean (class K1 / K2, training sample D, validation sample "
        "F, selected object, …) — the legend under the tabs explains the table on show; hover a "
        "cell for its exact value."
    )

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """The tabs (filled when a run arrives)."""
        super().__init__(parent)
        self.state = state
        self.empty = QLabel("Run ERDR to see its results.")
        self.content.addWidget(self.empty)
        self.tabs = QTabWidget()
        self.content.addWidget(self.tabs, 1)
        self.legend = Legend()
        self.content.addWidget(self.legend)
        self.views: dict[str, TableView] = {}
        self.tables: dict[str, Table] = {}
        self.tabs.currentChanged.connect(lambda _: self._explain())
        self.figure_choice = QComboBox()
        self.figure_view = FigureView()
        state.resultChanged.connect(self._show)
        self._show(state.result)

    def _show(self, result: ExperimentResult | None) -> None:
        self.tabs.clear()
        self.views.clear()
        self.tables.clear()
        while self.tabs.count():  # the tabs of the previous run are deleted, not only hidden
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if page is not None:
                page.deleteLater()
        self.empty.setVisible(result is None)
        self.tabs.setVisible(result is not None)
        if result is None:
            self.legend.show_table(None)
            return
        labels = result.dataset.classes
        for table in run_tables(result):
            view = TableView()
            view.show_table(table, class_labels=labels)
            self.views[table.key] = view
            self.tables[table.key] = table
            index = self.tabs.addTab(view, TAB_NAMES.get(table.key, table.key))
            stage = stage_of(table.sheet)
            if stage is not None:
                self.tabs.setTabIcon(index, swatch_icon(stage.colour))
                self.tabs.setTabToolTip(index, f"{table.title}\nStage: {stage.name}")
        figures = QWidget()
        layout = QVBoxLayout(figures)
        row = QHBoxLayout()
        self.figure_choice = QComboBox()
        for key, (name, _) in RUN_FIGURES.items():
            self.figure_choice.addItem(name, key)
        row.addWidget(QLabel("Figure:"))
        row.addWidget(self.figure_choice)
        row.addStretch(1)
        layout.addLayout(row)
        self.figure_view = FigureView()
        layout.addWidget(self.figure_view, 1)
        self.figure_choice.currentIndexChanged.connect(lambda _: self._draw())
        index = self.tabs.addTab(figures, "Figures")
        self.tabs.setTabIcon(index, swatch_icon(STAGES["result"].colour))
        self._draw()
        self._explain()

    def _explain(self) -> None:
        """Show the legend of the table on the current tab (figures carry their own)."""
        result = self.state.result
        page = self.tabs.currentWidget()
        key = next((k for k, view in self.views.items() if view is page), None)
        labels = result.dataset.classes if result is not None else ()
        self.legend.show_table(self.tables.get(key) if key else None, labels)

    def _draw(self) -> None:
        result = self.state.result
        key = self.figure_choice.currentData()
        if result is None or key is None:
            return
        self.figure_view.show_figure(run_figure(str(key), result))

    def show_tab(self, key: str) -> None:
        """Bring the tab of table ``key`` (or ``figures``) to the front."""
        if key == "figures":
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
        elif key in self.views:
            self.tabs.setCurrentWidget(self.views[key])
