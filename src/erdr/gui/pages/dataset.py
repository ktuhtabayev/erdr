"""Dataset page: choose a dataset of the project, a built-in one, or any file.

The summary names the feature types and the classes in their colours — quantitative (I) blue,
nominal (J) yellow, the classes K1, K2, … as in every figure — and the class bar shows the class
sizes; the table's headers and class cells take the same colours (ADR-019).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from erdr.data.builtin import DATASETS
from erdr.data.catalog import project_catalog, resolve_dataset
from erdr.data.loaders import load_dataset
from erdr.data.schema import Dataset
from erdr.errors import ERDRError
from erdr.export.tables import Table, sample_table
from erdr.export.theme import MUTED, class_colour, class_mark
from erdr.gui.state import AppState
from erdr.gui.widgets import Legend, Page, TableView, chip
from erdr.notation import class_name
from erdr.services.datasets import summarize

FILE_FILTER = (
    "Datasets (*.dat *.csv *.txt *.xlsx *.xlsm *.parquet);;"
    "Extended layout (*.dat *.csv);;Excel (*.xlsx *.xlsm);;All files (*)"
)


def dataset_preview(dataset: Dataset) -> Table:
    """The dataset as a table (objects, features, class; the type row last) — the exporters'."""
    return sample_table(dataset, dataset.name)


class ClassBalance(QWidget):
    """The classes as one bar: K1, K2, … in their figure colours, sized by their share."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty bar."""
        super().__init__(parent)
        self.sizes: tuple[int, ...] = ()
        self.setMinimumHeight(12)
        self.setMaximumHeight(12)

    def sizeHint(self) -> QSize:
        """A thin bar as wide as its container."""
        return QSize(200, 12)

    def set_sizes(self, sizes: tuple[int, ...]) -> None:
        """Show the class sizes (|K1|, |K2|, …)."""
        self.sizes = sizes
        self.setToolTip(" · ".join(f"{class_name(i)}: {n}" for i, n in enumerate(sizes)))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """One rounded segment per class with a 2 px gap between them."""
        total = sum(self.sizes)
        if total == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        gap = 2.0
        width = float(self.width()) - gap * (len(self.sizes) - 1)
        left = 0.0
        for index, size in enumerate(self.sizes):
            share = width * size / total
            painter.setBrush(QColor(class_colour(index)))
            painter.drawRoundedRect(QRectF(left, 0, share, float(self.height())), 3, 3)
            left += share + gap
        painter.end()


class DatasetPage(Page):
    """Pick E₀ — the sample ERDR divides into D and F."""

    title = "Dataset"
    explanation = (
        "Choose the sample E₀. The project's datasets folder holds the default dataset "
        "Heart-Disease (7, 13, 2) — the 7 objects of the ERDR workbook — and Heart-Disease "
        "(270, 13, 2); any file in the extended layout (m n c / objects + class / type flags), a "
        "CSV or Excel table, or the ERDR workbook itself can be opened."
    )

    def __init__(
        self, state: AppState, report: Callable[[str, str], None], parent: QWidget | None = None
    ) -> None:
        """The chooser, the summary and the data table."""
        super().__init__(parent)
        self.state = state
        self.report = report
        row = QHBoxLayout()
        self.chooser = QComboBox()
        self.chooser.setMinimumWidth(360)
        self.open_button = QPushButton("Open file…")
        row.addWidget(QLabel("Dataset:"))
        row.addWidget(self.chooser, 1)
        row.addWidget(self.open_button)
        self.content.addLayout(row)
        self.summary = QLabel("No dataset loaded.")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(self.summary.textInteractionFlags())
        self.content.addWidget(self.summary)
        self.balance = ClassBalance()
        self.content.addWidget(self.balance)
        self.table = TableView()
        self.content.addWidget(self.table, 1)
        self.legend = Legend()
        self.content.addWidget(self.legend)
        self._fill_chooser()
        self.chooser.activated.connect(self._chosen)
        self.open_button.clicked.connect(self._open_file)
        state.datasetChanged.connect(self._show)

    def _fill_chooser(self) -> None:
        self.chooser.clear()
        catalog = project_catalog()
        if catalog is not None:
            for entry in catalog:
                self.chooser.addItem(f"{entry.label}   [{entry.id}]", entry.id)
        for info in DATASETS:
            self.chooser.addItem(f"{info.summary}   [builtin]", info.name)

    def _chosen(self, index: int) -> None:
        key = self.chooser.itemData(index)
        if key:
            self.load(str(key))

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a dataset", "", FILE_FILTER)
        if path:
            self.load_file(Path(path))

    def load(self, source: str) -> bool:
        """Load a dataset by id, name or path; returns whether it worked."""
        try:
            dataset = resolve_dataset(source)
        except ERDRError as error:
            self.report("Cannot load the dataset", str(error))
            return False
        self.state.set_dataset(dataset)
        return True

    def load_file(self, path: Path) -> bool:
        """Load a dataset file of any supported format."""
        try:
            dataset = load_dataset(path)
        except ERDRError as error:
            self.report("Cannot load the dataset", str(error))
            return False
        self.state.set_dataset(dataset)
        return True

    def _show(self, dataset: Dataset | None) -> None:
        if dataset is None:
            self.summary.setText("No dataset loaded.")
            self.balance.set_sizes(())
            self.legend.show_table(None)
            return
        s = summarize(dataset)
        classes = " ".join(
            chip(f"{class_name(i)} · class {label}: {size}", class_mark(i))
            for i, (label, size) in enumerate(zip(s.classes, s.class_sizes, strict=True))
        )
        self.summary.setText(
            f"<b>{s.name}</b> {s.shape} · {s.class_text}<br>"
            f"{chip(f'quantitative (I): {len(s.quantitative)}', 'quantitative')} "
            f"{chip(f'nominal (J): {len(s.nominal)}', 'nominal')} &nbsp; {classes}<br>"
            f"permitted k: {s.permitted.text} · z(Sᵢ, k) exists for k ≤ {s.largest_k} "
            f"(own class: k ≤ {s.largest_k_own_class})<br>"
            f"<span style='color:{MUTED}'>{s.source or ''}</span>"
        )
        self.balance.set_sizes(s.class_sizes)
        table = dataset_preview(dataset)
        self.table.show_table(table, class_labels=s.classes)
        self.legend.show_table(table, s.classes)
