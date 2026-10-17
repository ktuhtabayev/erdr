"""Dataset page: choose a dataset of the project, a built-in one, or any file.

The chooser lists the datasets by type folder — Quantitative, Nominal, Heterogeneous (ADR-021).
The summary names the dataset type, the metric the configuration runs on it (``auto``: the
metric of the type, ADR-022), the feature types and the classes in their colours — quantitative
(I) blue, nominal (J) yellow, the classes K1, K2, … as in every figure — and the class bar shows
the class sizes; the table's headers and class cells take the same colours (ADR-019).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from erdr.config.models import ExperimentConfig
from erdr.data.builtin import DATASETS
from erdr.data.catalog import project_catalog, resolve_dataset
from erdr.data.loaders import load_dataset
from erdr.data.schema import Dataset, DatasetType
from erdr.errors import ERDRError
from erdr.export.tables import Table, sample_table
from erdr.export.theme import MUTED, class_colour, class_mark
from erdr.gui.state import AppState
from erdr.gui.widgets import Legend, Page, TableView, chip
from erdr.notation import class_name
from erdr.services.datasets import (
    DatasetSummary,
    choose_metric,
    megabytes,
    memory_warning,
    summarize,
)

FILE_FILTER = (
    "Datasets (*.dat *.csv *.txt *.xlsx *.xlsm *.parquet);;"
    "Extended layout (*.dat *.csv);;Excel (*.xlsx *.xlsm);;All files (*)"
)
LARGE_FILE = 50 * 2**20
"""Dataset files above this size show their size in the chooser."""
TYPE_MARKS = {
    DatasetType.QUANTITATIVE: "quantitative",
    DatasetType.NOMINAL: "nominal",
    DatasetType.HETEROGENEOUS: "type",
}
"""The colour of each dataset type: its feature type's, both feature types' for heterogeneous."""


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
        "Heart-Disease (7, 13, 2) — the 7 objects of the ERDR workbook — and the datasets of the "
        "type folders Quantitative, Nominal and Heterogeneous; the metric follows the dataset "
        "type (auto). Any file in the extended layout (m n c / objects + class / type flags), a "
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
        self._summary: DatasetSummary | None = None
        self._fill_chooser()
        self.chooser.activated.connect(self._chosen)
        self.open_button.clicked.connect(self._open_file)
        state.datasetChanged.connect(self._show)
        state.configChanged.connect(lambda _: self._describe())

    def _fill_chooser(self) -> None:
        """The folder's datasets under their type folders, then the built-in ones by type."""
        self.chooser.clear()
        catalog = project_catalog()
        if catalog is not None:
            for title, entries in catalog.groups():
                if title != "default":
                    self._heading(f"{title}/" if DatasetType.from_folder(title) else title)
                for entry in entries:
                    size = f" · {megabytes(entry.size)}" if entry.size > LARGE_FILE else ""
                    self.chooser.addItem(f"{entry.label}{size}   [{entry.id}]", entry.id)
        for kind in DatasetType:
            found = [info for info in DATASETS if info.obj.dataset_type is kind]
            if found:
                self._heading(f"Built-in · {kind.folder}")
            for info in found:
                self.chooser.addItem(f"{info.summary}   [builtin]", info.name)

    def _heading(self, text: str) -> None:
        """A bold line of the chooser that cannot be chosen."""
        self.chooser.addItem(text)
        model = self.chooser.model()
        if isinstance(model, QStandardItemModel):
            item = model.item(self.chooser.count() - 1)
            item.setEnabled(False)
            font = item.font()
            font.setBold(True)
            item.setFont(font)

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
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)  # TCGA_LUAD takes a while
        try:
            dataset = resolve_dataset(source)
        except ERDRError as error:
            self.report("Cannot load the dataset", str(error))
            return False
        finally:
            QApplication.restoreOverrideCursor()
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
            self._summary = None
            self.summary.setText("No dataset loaded.")
            self.balance.set_sizes(())
            self.legend.show_table(None)
            return
        s = self._summary = summarize(dataset, self.state.config)
        self._describe()
        self.balance.set_sizes(s.class_sizes)
        table = dataset_preview(dataset)
        self.table.show_table(table, class_labels=s.classes)
        self.legend.show_table(table, s.classes)

    def _metric_line(self, config: ExperimentConfig) -> str:
        """The metric ``config`` runs on the dataset — or why it cannot — and the suited ones."""
        dataset, s = self.state.dataset, self._summary
        if dataset is None or s is None:
            return ""
        try:
            choice = choose_metric(config, dataset)
        except ERDRError as error:
            return chip(f"⚠ {error}", "warning", bold=False)
        line = chip(f"metric: {choice.label}", "parameter")
        if choice.note:
            line += " " + chip(f"⚠ {choice.note}", "warning", bold=False)
        return f"{line} &nbsp; suited to {s.dataset_type.value} datasets: {', '.join(s.metrics)}"

    def _describe(self) -> None:
        """The summary text for the loaded dataset under the current configuration."""
        s = self._summary
        if s is None:
            return
        classes = " ".join(
            chip(f"{class_name(i)} · class {label}: {size}", class_mark(i))
            for i, (label, size) in enumerate(zip(s.classes, s.class_sizes, strict=True))
        )
        kind = chip(f"{s.dataset_type.value} dataset", TYPE_MARKS[s.dataset_type])
        memory = memory_warning(s.m, s.n)
        self.summary.setText(
            f"<b>{s.name}</b> {s.shape} · {s.class_text}<br>"
            f"{kind} {chip(f'quantitative (I): {len(s.quantitative)}', 'quantitative')} "
            f"{chip(f'nominal (J): {len(s.nominal)}', 'nominal')} &nbsp; {classes}<br>"
            f"{self._metric_line(self.state.config)}<br>"
            f"permitted k: {s.permitted.text} · z(Sᵢ, k) exists for k ≤ {s.largest_k} "
            f"(own class: k ≤ {s.largest_k_own_class})<br>"
            + (chip(f"⚠ {memory}", "warning", bold=False) + "<br>" if memory else "")
            + f"<span style='color:{MUTED}'>{s.source or ''}</span>"
        )
