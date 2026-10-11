"""Export page: the current run as tables, workbook, figures, report and datasets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QWidget,
)

from erdr.export import EXPORTERS, ExportOptions, export_result
from erdr.gui.state import AppState
from erdr.gui.widgets import Page
from erdr.gui.workers import TaskRunner
from erdr.services.experiment import ExperimentResult


def export_job(
    result: ExperimentResult, folder: Path, formats: list[str], options: ExportOptions
) -> list[Path]:
    """Export in the worker thread."""
    return export_result(result, folder, formats, options)


class ExportPage(Page):
    """Write the current run to a folder in the chosen formats."""

    title = "Export"
    explanation = (
        "CSV and JSON keep every value exactly; the Excel workbook is laid out like the ERDR "
        "workbook; the HTML report is one self-contained page; the datasets are the training "
        "and validation samples in the author's extended layout (.dat and .csv)."
    )
    finished = Signal(bool)
    """The export ended (``True`` if it succeeded)."""

    def __init__(
        self, state: AppState, report: Callable[[str, str], None], parent: QWidget | None = None
    ) -> None:
        """Format choices, the folder, the button and the list of written files."""
        super().__init__(parent)
        self.state = state
        self.report = report
        self.tasks = TaskRunner(self)
        box = QGroupBox("Formats")
        grid = QGridLayout(box)
        self.formats: dict[str, QCheckBox] = {}
        for index, info in enumerate(EXPORTERS):
            check = QCheckBox(f"{info.name} — {info.summary}")
            check.setChecked(True)
            self.formats[info.name] = check
            grid.addWidget(check, index // 2, index % 2)
        self.content.addWidget(box)
        self.with_readings = QCheckBox("include the readings comparison (Readings & k page)")
        self.with_sweep = QCheckBox("include the k sweep (Readings & k page)")
        self.content.addWidget(self.with_readings)
        self.content.addWidget(self.with_sweep)
        row = QHBoxLayout()
        self.folder = QLineEdit(str(Path("exports").resolve()))
        browse = QPushButton("Browse…")
        row.addWidget(QLabel("Folder:"))
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        self.content.addLayout(row)
        buttons = QHBoxLayout()
        self.export_button = QPushButton("Export")
        self.export_button.setMinimumHeight(32)
        self.open_button = QPushButton("Open the folder")
        buttons.addWidget(self.export_button)
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        self.content.addLayout(buttons)
        self.status = QLabel()
        self.content.addWidget(self.status)
        self.files = QListWidget()
        self.content.addWidget(self.files, 1)
        browse.clicked.connect(self._browse)
        self.export_button.clicked.connect(self.export)
        self.open_button.clicked.connect(self._open)
        state.resultChanged.connect(lambda _: self._enable())
        state.analysisChanged.connect(self._enable)
        self._enable()

    def _enable(self) -> None:
        self.export_button.setEnabled(self.state.result is not None and not self.tasks.busy())
        self.with_readings.setEnabled(bool(self.state.readings))
        self.with_sweep.setEnabled(bool(self.state.sweep))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Export folder", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def chosen_formats(self) -> list[str]:
        """The ticked formats."""
        return [name for name, check in self.formats.items() if check.isChecked()]

    def export(self) -> None:
        """Export the current run in the background."""
        result = self.state.result
        formats = self.chosen_formats()
        if result is None or not formats:
            return
        options = ExportOptions(
            readings=self.state.readings if self.with_readings.isChecked() else None,
            sweep=self.state.sweep if self.with_sweep.isChecked() else None,
        )
        folder = Path(self.folder.text())
        self.export_button.setEnabled(False)
        self.status.setText("Exporting…")
        self.tasks.start(
            lambda: export_job(result, folder, formats, options), self._exported, self._failed
        )

    def _exported(self, files: object) -> None:
        written = list(files)  # type: ignore[call-overload]
        self.files.clear()
        self.files.addItems([str(path) for path in written])
        self.status.setText(f"{len(written)} files written to {self.folder.text()}")
        self._enable()
        self.finished.emit(True)

    def _failed(self, message: str) -> None:
        self.status.setText("The export failed.")
        self.report("The export failed", message)
        self._enable()
        self.finished.emit(False)

    def _open(self) -> None:
        folder = Path(self.folder.text())
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def wait(self) -> bool:
        """Wait for a running export."""
        return self.tasks.wait()
