"""Results page: every table of the workbook for the current run, the figures and the spheres.

Each tab carries the colour of its stage, as the workbook's sheet tabs do; the legend under the
tabs explains the colours of the table on show (ADR-019). The *Hyperspheres* tab explores Steps
1–5 as spheres, object by object and iteration by iteration (ADR-020); a double click on a row of
an object's or an iteration's table opens it there.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget

from erdr.export.figures import figure_names, run_figure
from erdr.export.tables import Table, run_tables
from erdr.export.theme import STAGES, stage_of
from erdr.gui.pages.spheres import SpheresExplorer
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
    "enemy-spheres": "Enemy spheres",
    "k-spheres": "k-spheres",
    "covering": "Covering",
    "sphere-checks": "Sphere checks",
    "queue": "Step 2 · queue",
    "iterations": "Iterations",
    "iteration-spheres": "Spheres per iteration",
    "sphere-trace": "Sphere trace",
    "counters": "Counters g",
    "routes": "D and F",
    "composition": "Composition",
    "cases": "Cases",
}
"""Tab titles per table key."""
EXPLORER = "explorer"
"""The key of the *Hyperspheres* tab (:meth:`ResultsPage.show_tab`)."""
OBJECT_ROWS = {
    "characteristics": 0,
    "enemy-spheres": 0,
    "k-spheres": 0,
    "covering": 0,
    "queue": 1,
    "routes": 0,
}
"""Tables whose rows are objects: key → the column with the object's name."""
ITERATION_ROWS = {"iterations": 0, "iteration-spheres": 0, "sphere-trace": 0}
"""Tables whose rows belong to iterations: key → the column with t."""


class ResultsPage(Page):
    """The current run, table by table — the sheets of the ERDR workbook."""

    title = "Results"
    explanation = (
        "Every table of the ERDR workbook for the current run; a tab's square is the colour of its "
        "stage. Column headers are coloured by what they hold (feature type, class, r g z, d, "
        "sample) and cells by what they mean (class K1 / K2, training sample D, validation sample "
        "F, selected object, …) — the legend under the tabs explains the table on show; hover a "
        "cell for its exact value. Double-click an object or an iteration to see its spheres."
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
        self.explorer = SpheresExplorer(self)  # owned by Qt from the start (ADR-020)
        self.explorer.hide()
        state.resultChanged.connect(self._show)
        self._show(state.result)

    def _show(self, result: ExperimentResult | None) -> None:
        # clear() detaches the pages of the previous run without deleting them, as every release
        # before 0.4.0 did; the explorer is one widget, reused (ADR-020)
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
            self.explorer.show_result(None)
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
            if table.key in OBJECT_ROWS or table.key in ITERATION_ROWS:
                view.doubleClicked.connect(
                    lambda cell, key=table.key: self._open_spheres(key, cell)
                )
        figures = QWidget()
        layout = QVBoxLayout(figures)
        row = QHBoxLayout()
        self.figure_choice = QComboBox()
        for key, name in figure_names():
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
        self.explorer.show_result(result)
        index = self.tabs.addTab(self.explorer, "Hyperspheres")
        self.tabs.setTabIcon(index, swatch_icon(STAGES["steps"].colour))
        self.tabs.setTabToolTip(
            index, "Steps 1–5 as spheres, object by object and iteration by iteration"
        )
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

    def _open_spheres(self, key: str, cell: QModelIndex) -> None:
        """Show the spheres of the object or the iteration of a table row."""
        result = self.state.result
        table = self.tables.get(key)
        if result is None or table is None or not cell.isValid():
            return
        row = table.rows[cell.row()]
        if key in OBJECT_ROWS:
            name = row[OBJECT_ROWS[key]]
            if name in result.object_names:
                self.explorer.show_object(result.object_names.index(str(name)))
                self.show_tab(EXPLORER)
        else:
            value = row[ITERATION_ROWS[key]]
            if isinstance(value, int):
                self.explorer.show_iteration(value)
                self.show_tab(EXPLORER)

    def show_tab(self, key: str) -> None:
        """Bring the tab of table ``key`` (or ``figures``, or ``explorer``) to the front."""
        if key == "figures":
            self.tabs.setCurrentIndex(self.tabs.count() - 2)
        elif key == EXPLORER:
            self.tabs.setCurrentWidget(self.explorer)
        elif key in self.views:
            self.tabs.setCurrentWidget(self.views[key])
