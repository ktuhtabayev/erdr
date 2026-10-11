"""Results page: every table of the workbook for the current run, and the figures."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from erdr.export.figures import RUN_FIGURES, run_figure
from erdr.export.tables import run_tables
from erdr.gui.models import MARK_COLOURS, MARK_MEANINGS
from erdr.gui.state import AppState
from erdr.gui.widgets import FigureView, Page, TableView
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
        "Every table of the ERDR workbook for the current run. Colours: blue = training sample "
        "D, orange = validation sample F, yellow = selected object or tie decided by r, violet = "
        "counter decreased by Step 5; hover a cell for its exact value."
    )

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        """The tabs (filled when a run arrives)."""
        super().__init__(parent)
        self.state = state
        self.empty = QLabel("Run ERDR to see its results.")
        self.content.addWidget(self.empty)
        style = "color:#0b0b0b; padding:0 6px"  # dark ink on the light tints, in any theme
        legend = " ".join(
            f"<span style='background:{MARK_COLOURS[k]}; {style}'>{MARK_MEANINGS[k]}</span>"
            for k in ("D", "F", "selected", "decreased", "moved", "own", "enemy")
        )
        self.legend = QLabel(legend)
        self.legend.setWordWrap(True)
        self.content.addWidget(self.legend)
        self.tabs = QTabWidget()
        self.content.addWidget(self.tabs, 1)
        self.views: dict[str, TableView] = {}
        self.figure_choice = QComboBox()
        self.figure_view = FigureView()
        state.resultChanged.connect(self._show)
        self._show(state.result)

    def _show(self, result: ExperimentResult | None) -> None:
        self.tabs.clear()
        self.views.clear()
        while self.tabs.count():  # the tabs of the previous run are deleted, not only hidden
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            if page is not None:
                page.deleteLater()
        self.empty.setVisible(result is None)
        self.legend.setVisible(result is not None)
        self.tabs.setVisible(result is not None)
        if result is None:
            return
        for table in run_tables(result):
            view = TableView()
            view.show_table(table)
            self.views[table.key] = view
            self.tabs.addTab(view, TAB_NAMES.get(table.key, table.key))
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
        self.tabs.addTab(figures, "Figures")
        self._draw()

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
