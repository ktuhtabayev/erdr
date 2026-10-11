"""The colour categories on screen (ADR-019): headers, cells, legends, chips, flagged switches."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from erdr.export.tables import run_tables
from erdr.export.theme import STAGES, SWATCHES
from erdr.gui.models import TableModel
from erdr.gui.widgets import Legend, chip
from erdr.gui.window import MainWindow
from tests.gui.conftest import Run

pytestmark = pytest.mark.gui


def _header_pixel(view, column: int) -> str:
    """The colour inside a header section, a few pixels from its left edge."""
    header = view.horizontalHeader()
    image = header.grab().toImage()
    x = header.sectionViewportPosition(column) + 3
    return image.pixelColor(x, 3).name()


def test_dataset_page_names_features_and_classes(loaded: MainWindow, qapp):
    page = loaded.dataset_page
    dataset = loaded.state.dataset
    assert dataset is not None
    model = page.table.model()
    assert isinstance(model, TableModel)
    first = 1 if bool(dataset.quantitative[0]) else 2  # a quantitative and a nominal column
    kinds = {model.table.header_mark(c) for c in range(1, dataset.n + 1)}
    assert kinds == {"quantitative", "nominal"}
    assert model.header_swatch(first) is not None
    assert model.header_swatch(0) is None
    class_column = dataset.n + 1
    cell = model.index(0, class_column)
    mark = model.table.mark(0, class_column)
    assert mark in ("K1", "K2")
    assert model.data(cell, Qt.ItemDataRole.BackgroundRole).color() == QColor(SWATCHES[mark].fill)
    assert model.data(cell, Qt.ItemDataRole.ForegroundRole).color() == QColor(SWATCHES[mark].ink)
    assert "class K" in model.data(cell, Qt.ItemDataRole.ToolTipRole)
    tooltip = model.headerData(class_column, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)
    assert tooltip == "Class\nclass label"
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) == "№"
    assert {"quantitative", "nominal", "class", "type", "K1", "K2"} <= set(page.legend.marks)
    assert page.balance.sizes == dataset.class_sizes
    summary = page.summary.text()
    assert SWATCHES["quantitative"].fill in summary
    assert SWATCHES["nominal"].fill in summary
    assert SWATCHES["K2"].fill in summary
    loaded.show()
    page.table.resizeColumnsToContents()
    qapp.processEvents()
    mark = model.table.header_mark(1)
    assert _header_pixel(page.table, 1) == SWATCHES[mark].fill  # the header is painted
    assert _header_pixel(page.table, 0) != SWATCHES[mark].fill
    page.balance.grab()  # paints the class bar
    page._show(None)
    assert not page.legend.marks
    assert page.balance.sizes == ()


def test_results_legend_follows_the_tab(loaded: MainWindow, run: Run):
    run(loaded)
    page = loaded.results_page
    page.show_tab("routes")
    assert {"D", "F", "K1", "K2", "class"} <= set(page.legend.marks)
    assert not page.legend.isHidden()
    page.show_tab("cases")
    assert page.legend.marks == ["yes"]
    page.show_tab("figures")
    assert page.legend.marks == []
    assert page.legend.isHidden()
    for index in range(page.tabs.count()):
        assert not page.tabs.tabIcon(index).isNull()  # every tab shows its stage colour
    assert "Stage: " + STAGES["steps"].name in page.tabs.tabToolTip(
        page.tabs.indexOf(page.views["characteristics"])
    )
    result = loaded.state.result
    assert result is not None
    table = next(t for t in run_tables(result) if t.key == "iterations")
    model = TableModel(table)
    assert model.data(model.index(0, 1), Qt.ItemDataRole.BackgroundRole) is not None
    assert SWATCHES["D"].fill in loaded.result_label.text()
    assert SWATCHES["F"].fill in loaded.run_page.outcome.text()
    assert SWATCHES["parameter"].fill in loaded.run_page.context.text()


def test_a_switch_that_is_not_literal_is_flagged(loaded: MainWindow):
    page = loaded.configure_page
    box = page.readings["blocked_cover"]
    assert box.property("flagged") is False
    assert page.preset_badge.objectName() == "badge"
    box.setCurrentIndex(1)
    assert box.property("flagged") is True
    assert "Not the literal" in box.toolTip()
    assert page.preset_badge.objectName() == "warningBadge"
    assert page.readings["self_in_l"].property("flagged") is False
    assert SWATCHES["warning"].fill in loaded.run_page.context.text()
    box.setCurrentIndex(0)
    assert box.property("flagged") is False
    assert page.preset_badge.objectName() == "badge"


def test_legend_and_chip(qtbot):
    legend = Legend()
    qtbot.addWidget(legend)
    legend.show_marks(["F", "quantitative", None, "K1"], (1, 2))
    assert legend.marks == ["quantitative", "K1", "F"]
    assert "class K1 (label 1)" in legend.text()
    assert "Columns: " in legend.text()
    legend.show_marks([])
    assert legend.isHidden()
    text = chip("D < 5", "D")
    assert SWATCHES["D"].fill in text
    assert "D &lt; 5" in text
