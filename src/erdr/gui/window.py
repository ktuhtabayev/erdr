"""The main window: a sidebar of pages, the pages, menus and a status bar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from erdr import __version__
from erdr.errors import ERDRError
from erdr.gui.pages.analysis import AnalysisPage
from erdr.gui.pages.configure import ConfigurePage
from erdr.gui.pages.dataset import DatasetPage
from erdr.gui.pages.export import ExportPage
from erdr.gui.pages.results import ResultsPage
from erdr.gui.pages.run import RunPage
from erdr.gui.state import AppState
from erdr.gui.widgets import Page
from erdr.services.experiment import ExperimentResult
from erdr.services.runs import load_run

APP_TITLE = "ERDR — Enemy-Radius Density Reduction"
DOCUMENTATION = "https://ktuhtabayev.github.io/erdr/"


class MainWindow(QMainWindow):
    """Dataset → Configure → Run → Results → Readings & k → Export."""

    def __init__(self, state: AppState | None = None) -> None:
        """Build the window and its pages around ``state`` (a new one by default)."""
        super().__init__()
        self.state = state or AppState(self)
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 820)

        def report(title: str, text: str) -> None:  # late binding: show_message may be replaced
            self.show_message(title, text)

        self.dataset_page = DatasetPage(self.state, report)
        self.configure_page = ConfigurePage(self.state, report)
        self.run_page = RunPage(self.state, report)
        self.results_page = ResultsPage(self.state)
        self.analysis_page = AnalysisPage(self.state, report)
        self.export_page = ExportPage(self.state, report)
        self.pages: list[Page] = [
            self.dataset_page,
            self.configure_page,
            self.run_page,
            self.results_page,
            self.analysis_page,
            self.export_page,
        ]
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(170)
        self.stack = QStackedWidget()
        for page in self.pages:
            self.sidebar.addItem(page.title)
            self.stack.addWidget(page)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sidebar.setCurrentRow(0)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self._menus()
        self.state.datasetChanged.connect(lambda _: self._status())
        self.state.resultChanged.connect(self._result_arrived)
        self._status()

    # ------------------------------------------------------------------ navigation

    def go_to(self, page: Page) -> None:
        """Show ``page``."""
        self.sidebar.setCurrentRow(self.pages.index(page))

    def _result_arrived(self, result: ExperimentResult | None) -> None:
        self._status()
        if result is not None:
            self.go_to(self.results_page)

    def _status(self) -> None:
        dataset = self.state.dataset
        result = self.state.result
        parts = [dataset.name if dataset else "no dataset"]
        if result is not None:
            parts.append(
                f"D = {result.result.training.size}, F = {result.result.validation.size} "
                f"({result.result.readings.label})"
            )
        self.statusBar().showMessage("   ·   ".join(parts))

    # ------------------------------------------------------------------ menus

    def _menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for text, shortcut, slot in (
            ("Open &dataset…", QKeySequence.StandardKey.Open, self._open_dataset),
            ("Open &configuration…", None, self._open_config),
            ("Open a saved &run folder…", None, self._open_run),
        ):
            action = QAction(text, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("E&xit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        run_menu = self.menuBar().addMenu("&Run")
        run_action = QAction("&Run ERDR", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._run)
        run_menu.addAction(run_action)
        help_menu = self.menuBar().addMenu("&Help")
        docs = QAction("&Documentation", self)
        docs.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(DOCUMENTATION)))
        about = QAction("&About", self)
        about.triggered.connect(self._about)
        help_menu.addAction(docs)
        help_menu.addAction(about)

    def _open_dataset(self) -> None:
        self.go_to(self.dataset_page)
        self.dataset_page._open_file()

    def _open_config(self) -> None:
        self.go_to(self.configure_page)
        self.configure_page._load()

    def _open_run(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open a run folder", "runs")
        if folder:
            self.open_run(Path(folder))

    def open_run(self, folder: Path) -> bool:
        """Repeat a saved run and show it."""
        try:
            result = load_run(folder)
        except ERDRError as error:
            self.show_message("Cannot open the run", str(error))
            return False
        self.state.set_dataset(result.dataset)
        self.configure_page.show_config(result.config)
        self.state.set_result(result, str(folder))
        return True

    def open_config(self, path: Path) -> bool:
        """Load a configuration file (and its dataset, if it names one)."""
        if not self.configure_page.open(path):
            return False
        if self.state.config.dataset.path is not None:
            from erdr.data.loaders import load_from_config

            try:
                self.state.set_dataset(
                    load_from_config(self.state.config.dataset, path.resolve().parent)
                )
            except ERDRError as error:
                self.show_message("Cannot load the dataset of the configuration", str(error))
        return True

    def _run(self) -> None:
        self.go_to(self.run_page)
        self.run_page.start()

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About ERDR",
            f"<b>{APP_TITLE}</b><br>version {__version__}<br><br>"
            "The ERDR algorithm of §1.1 of N. A. Ignatev's article divides a labelled sample E₀ "
            "into a training sample D and a validation sample F = E₀ \\ D by enemy radii and "
            "local density.<br><br>MIT License · Kudratillo Tuhtabayev",
        )

    def show_message(self, title: str, text: str) -> None:
        """Report a problem to the user (replaced by the tests and the self-test)."""
        box = QMessageBox(QMessageBox.Icon.Warning, title, text[:4000], parent=self)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.exec()

    def wait(self) -> None:
        """Wait for every background task."""
        for page in (self.run_page, self.analysis_page, self.export_page):
            page.wait()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Let running tasks end before the window goes."""
        self.wait()
        self.run_page.log_bridge.detach()
        super().closeEvent(event)
