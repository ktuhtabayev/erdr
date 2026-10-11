"""The main window in the template's layout: sidebar, pages, menus, status bar, appearance."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QWidget,
)

from erdr import __version__
from erdr.config.presets import matching_preset, reading_notes
from erdr.errors import ERDRError
from erdr.gui.pages.analysis import AnalysisPage
from erdr.gui.pages.configure import ConfigurePage
from erdr.gui.pages.dataset import DatasetPage
from erdr.gui.pages.export import ExportPage
from erdr.gui.pages.results import ResultsPage
from erdr.gui.pages.run import RunPage
from erdr.gui.settings import Settings
from erdr.gui.state import AppState
from erdr.gui.theme import FONT_SCALES, ThemeName, apply_theme, theme_name
from erdr.gui.widgets import Page
from erdr.services.experiment import ExperimentResult
from erdr.services.runs import load_run

APP_TITLE = "ERDR — Enemy-Radius Density Reduction"
DOCUMENTATION = "https://ktuhtabayev.github.io/erdr/"
SIDEBAR_WIDTH = 184
"""Width of the page list (the template's); it grows with the longest name and the zoom."""
THEMES = (
    (ThemeName.LIGHT, "Light theme"),
    (ThemeName.DARK, "Dark theme"),
    (ThemeName.SYSTEM, "Follow Windows"),
)


class MainWindow(QMainWindow):
    """Dataset → Configure → Run → Results → Readings & k → Export."""

    def __init__(self, state: AppState | None = None, settings: Settings | None = None) -> None:
        """Build the window around ``state`` and restore the appearance of the last session."""
        super().__init__()
        self.settings = settings if settings is not None else Settings()
        self.state = state or AppState(self)
        self.theme = self.settings.theme
        self.font_scale = self.settings.font_scale
        self.setWindowTitle(APP_TITLE)
        self.resize(1360, 860)

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
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stack = QStackedWidget()
        for number, page in enumerate(self.pages, start=1):
            item = QListWidgetItem(f"{number}   {page.title}")
            item.setToolTip(f"{page.title}  (Ctrl+{number})")
            self.sidebar.addItem(item)
            self.stack.addWidget(page)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # ---- status bar: dataset and result on the left, the reading on the right
        self.dataset_label = QLabel()
        self.result_label = QLabel()
        self.reading_label = QLabel()
        self.reading_label.setObjectName("badge")
        self.notes_button = QPushButton()
        self.notes_button.setObjectName("warningBadge")
        self.notes_button.setFlat(True)
        self.notes_button.clicked.connect(lambda: self.go_to(self.configure_page))
        bar = self.statusBar()
        bar.addWidget(self.dataset_label)
        bar.addWidget(self.result_label)
        bar.addPermanentWidget(self.reading_label)
        bar.addPermanentWidget(self.notes_button)

        self._menus()
        self.state.datasetChanged.connect(lambda _: self._status())
        self.state.configChanged.connect(lambda _: self._status())
        self.state.resultChanged.connect(self._result_arrived)
        geometry = self.settings.geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        self.apply_appearance()
        self._status()
        self.sidebar.setCurrentRow(0)

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
        self.dataset_label.setText(dataset.name if dataset else "no dataset")
        self.result_label.setText(
            f"D = {result.result.training.size}, F = {result.result.validation.size}"
            if result is not None
            else ""
        )
        config = self.state.config
        preset = matching_preset(config)
        reading = config.erdr.readings.to_readings()
        self.reading_label.setText(f"{preset.value if preset else 'custom'} · {reading.label}")
        notes = reading_notes(config)
        self.notes_button.setText(f"⚠ not literal: {', '.join(n.switch for n in notes)}")
        self.notes_button.setToolTip("; ".join(n.statement for n in notes))
        self.notes_button.setVisible(bool(notes))

    # ------------------------------------------------------------------ menus

    def _action(
        self,
        menu: QMenu,
        text: str,
        slot: Callable[[], object],
        shortcut: str | QKeySequence.StandardKey | None = None,
    ) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        self._action(file_menu, "Open dataset…", self._open_dataset, "Ctrl+O")
        self._action(file_menu, "Open configuration…", self._open_config, "Ctrl+Shift+O")
        self._action(file_menu, "Save configuration as…", self.configure_page._save, "Ctrl+S")
        self._action(file_menu, "Open run folder…", self._open_run, "Ctrl+Shift+R")
        file_menu.addSeparator()
        self._action(file_menu, "Export…", lambda: self.go_to(self.export_page), "Ctrl+E")
        file_menu.addSeparator()
        self._action(file_menu, "Quit", self.close, "Ctrl+Q")

        run_menu = bar.addMenu("&Run")
        self._action(run_menu, "Run ERDR", self._run, "F5")

        view_menu = bar.addMenu("&View")
        for number, page in enumerate(self.pages, start=1):
            self._action(view_menu, page.title, partial(self.go_to, page), f"Ctrl+{number}")
        view_menu.addSeparator()
        themes = QActionGroup(self)
        self.theme_actions: dict[ThemeName, QAction] = {}
        for name, text in THEMES:
            action = QAction(text, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, n=name: self.set_theme(n))
            themes.addAction(action)
            view_menu.addAction(action)
            self.theme_actions[name] = action
        self._action(view_menu, "Switch theme", self.toggle_theme, "Ctrl+T")
        view_menu.addSeparator()
        zoom_in = self._action(view_menu, "Zoom in", lambda: self.zoom(1), "Ctrl++")
        zoom_in.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self._action(view_menu, "Zoom out", lambda: self.zoom(-1), "Ctrl+-")
        self._action(view_menu, "Actual size", lambda: self.zoom(0), "Ctrl+0")

        help_menu = bar.addMenu("&Help")
        self._action(
            help_menu, "Documentation", lambda: QDesktopServices.openUrl(QUrl(DOCUMENTATION)), "F1"
        )
        self._action(help_menu, "About", self._about)

    # ------------------------------------------------------------------ appearance

    def apply_appearance(self) -> None:
        """Apply the theme and the zoom to the whole application and remember them."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, self.theme, self.font_scale)
        # longer names and a larger zoom need a wider page list
        self.sidebar.ensurePolished()
        needed = self.sidebar.sizeHintForColumn(0) + 2 * self.sidebar.frameWidth() + 8
        self.sidebar.setFixedWidth(max(SIDEBAR_WIDTH, needed))
        for name, action in self.theme_actions.items():
            action.setChecked(name == self.theme)
        self.settings.theme = self.theme
        self.settings.font_scale = self.font_scale

    def set_theme(self, name: ThemeName | str) -> None:
        """Switch to the light, the dark or the Windows theme."""
        self.theme = theme_name(name)
        self.apply_appearance()

    def toggle_theme(self) -> None:
        """Switch between the light and the dark theme."""
        self.set_theme(ThemeName.LIGHT if self.theme is ThemeName.DARK else ThemeName.DARK)

    def zoom(self, direction: int) -> None:
        """Make the interface larger (+1), smaller (−1) or its actual size (0)."""
        if direction == 0:
            scale = 1.0
        else:
            steps = list(FONT_SCALES)
            current = min(range(len(steps)), key=lambda i: abs(steps[i] - self.font_scale))
            scale = steps[min(max(current + direction, 0), len(steps) - 1)]
        self.font_scale = scale
        self.apply_appearance()

    # ------------------------------------------------------------------ files

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
        """Let running tasks end, remember the window, then close."""
        self.wait()
        self.settings.save_geometry(self.saveGeometry())
        self.settings.sync()
        self.run_page.log_bridge.detach()
        super().closeEvent(event)
