"""Dataset page: choose a dataset of the project, a built-in one, or any file."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
from erdr.export.tables import Cell, Table
from erdr.gui.state import AppState
from erdr.gui.widgets import Page, TableView
from erdr.services.datasets import summarize

FILE_FILTER = (
    "Datasets (*.dat *.csv *.txt *.xlsx *.xlsm *.parquet);;"
    "Extended layout (*.dat *.csv);;Excel (*.xlsx *.xlsm);;All files (*)"
)


def dataset_preview(dataset: Dataset) -> Table:
    """The dataset as a table (objects, features, class; the type row last)."""
    rows: list[tuple[Cell, ...]] = [
        (dataset.object_ids[i], *(float(v) for v in dataset.X[i]), str(dataset.y[i].item()))
        for i in range(dataset.m)
    ]
    rows.append(("Type", *dataset.type_flags, "1 = I"))
    return Table("dataset", dataset.name, ("№", *dataset.feature_names, "Class"), tuple(rows))


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
        self.table = TableView()
        self.content.addWidget(self.table, 1)
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
            return
        s = summarize(dataset)
        self.summary.setText(
            f"<b>{s.name}</b> {s.shape} · {s.class_text}<br>"
            f"quantitative (I): {len(s.quantitative)} · nominal (J): {len(s.nominal)} · "
            f"permitted k: {s.permitted.text} · z(Sᵢ, k) exists for k ≤ {s.largest_k} "
            f"(own class: k ≤ {s.largest_k_own_class})<br>"
            f"<span style='color:#898781'>{s.source or ''}</span>"
        )
        self.table.show_table(dataset_preview(dataset))
