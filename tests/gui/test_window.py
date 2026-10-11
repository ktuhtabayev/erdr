"""The desktop application: every page, driven like a user would (offscreen)."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from erdr.core.metrics import METRICS
from erdr.core.readings import BlockedCover, ZScope
from erdr.export.tables import run_tables
from erdr.gui.app import create_window, self_test
from erdr.gui.forms import ParamsForm
from erdr.gui.models import TableModel
from erdr.gui.pages.analysis import parse_ks
from erdr.gui.settings import Settings
from erdr.gui.theme import FONT_SCALES, LIGHT, ThemeName, is_dark, stylesheet
from erdr.gui.window import MainWindow
from erdr.services.runs import save_run
from tests.conftest import CONFIGS
from tests.gui.conftest import RUN_TIMEOUT, Run

pytestmark = pytest.mark.gui


def test_dataset_page(window: MainWindow, messages: list[str]):
    assert window.state.dataset is None
    assert window.dataset_page.chooser.count() >= 5  # 2 folder datasets + 3 built-in
    assert window.dataset_page.load("heart-disease-270")
    assert window.state.dataset is not None
    assert window.state.dataset.m == 270
    assert "permitted k: 3, 5, …, 237" in window.dataset_page.summary.text()
    model = window.dataset_page.table.model()
    assert model.rowCount() == 271  # objects + the type row
    assert not window.dataset_page.load("nothing")
    assert messages
    assert "Cannot load" in messages[-1]
    assert window.dataset_page.load_file(Path("datasets/default.csv"))
    assert not window.dataset_page.load_file(Path("missing.csv"))


def test_configure_page_edits_the_state(loaded: MainWindow):
    page = loaded.configure_page
    page.k.setValue(5)
    assert loaded.state.config.erdr.k == 5
    assert "outside the rule" in page.permitted.text()
    page.readings["blocked_cover"].setCurrentIndex(1)
    assert loaded.state.config.erdr.readings.blocked_cover is BlockedCover.DROPPED
    assert "Not the literal" in page.warning.text()
    assert page.preset_badge.text() == "custom"
    page.literal_button.click()
    assert loaded.state.config.erdr.readings.to_readings().is_literal
    assert page.preset_badge.text() == "literal"
    assert page.warning.isHidden()
    page.closest_button.click()
    assert page.preset_badge.text() == "closest"
    assert "own class" in page.warning.text()
    page.literal_button.click()
    page.metric_box.setCurrentIndex(page.metric_box.findData("minkowski"))
    assert loaded.state.config.distance.metric.name == "minkowski"
    page.reset_button.click()
    assert loaded.state.config.erdr.k == 3
    assert loaded.state.config.distance.metric.name == "zhuravlev"


def test_configure_page_files(loaded: MainWindow, tmp_path: Path, messages: list[str]):
    assert loaded.open_config(CONFIGS / "heart-disease-270-closest.yaml")
    assert loaded.state.config.erdr.readings.z_scope is ZScope.OWN_CLASS
    assert loaded.state.dataset is not None
    assert loaded.state.dataset.m == 270
    assert loaded.configure_page.preset_badge.text() == "closest"
    bad = tmp_path / "bad.yaml"
    bad.write_text("erdr: {k: 0}\n", encoding="utf-8")
    assert not loaded.configure_page.open(bad)
    assert "Cannot load the configuration" in messages[-1]


def test_run_and_results(loaded: MainWindow, run: Run):
    run(loaded)
    result = loaded.state.result
    assert result is not None
    assert [result.object_names[i] for i in result.result.training] == [
        "S₁",
        "S₂",
        "S₅",
        "S₆",
        "S₇",
    ]
    assert "D (training): 5" in loaded.run_page.outcome.text()
    assert loaded.stack.currentWidget() is loaded.results_page
    assert set(loaded.results_page.views) == {t.key for t in run_tables(result)}
    loaded.results_page.show_tab("iterations")
    view = loaded.results_page.views["iterations"]
    assert view.model().rowCount() == 6
    loaded.results_page.show_tab("figures")
    for index in range(loaded.results_page.figure_choice.count()):
        loaded.results_page.figure_choice.setCurrentIndex(index)
        assert loaded.results_page.figure_view.figure.axes
    assert loaded.result_label.text() == "D = 5, F = 2"
    assert any("ERDR finished" in line for line in loaded.run_page.log.toPlainText().splitlines())


def test_run_failure_is_reported(loaded: MainWindow, qtbot: QtBot, messages: list[str]):
    loaded.configure_page.k.setValue(5)  # outside the k rule (enforce)
    with qtbot.waitSignal(loaded.run_page.finished, timeout=RUN_TIMEOUT) as blocker:
        loaded.run_page.start()
    assert blocker.args == [False]
    assert "outside the k rule" in messages[-1]


def test_saved_run(loaded: MainWindow, run: Run, tmp_path: Path, settings: Settings):
    loaded.run_page.save.setChecked(True)
    run(loaded)
    assert loaded.state.saved_run is not None
    folder = Path(loaded.state.saved_run)
    assert (folder / "manifest.yaml").is_file()
    other = create_window(dataset="guide-example", settings=settings)
    other.show_message = lambda title, text: None  # type: ignore[method-assign]
    assert other.open_run(folder)
    assert other.state.result is not None
    assert other.state.dataset is not None
    assert other.state.dataset.m == 7
    assert not other.open_run(tmp_path)
    other.close()


def test_analysis_page(loaded: MainWindow, qtbot: QtBot, messages: list[str]):
    page = loaded.analysis_page
    with qtbot.waitSignal(loaded.state.analysisChanged, timeout=RUN_TIMEOUT):
        page.compare()
    page.wait()
    assert loaded.state.readings is not None
    assert len(loaded.state.readings) == 8
    assert page.readings_view.model().rowCount() == 8
    page.ks.setText("1-3")
    with qtbot.waitSignal(loaded.state.analysisChanged, timeout=RUN_TIMEOUT):
        page.sweep()
    page.wait()
    assert loaded.state.sweep is not None
    assert {row.k for row in loaded.state.sweep} == {1, 3}  # a range steps over odd k
    assert page.figure_view.figure.axes
    page.ks.setText("a,b")
    page.sweep()
    assert "Invalid k values" in messages[-1]
    page.ks.setText("")
    page.use_literal.setChecked(False)
    page.use_closest.setChecked(False)
    page.sweep()
    assert "No reading chosen" in messages[-1]
    assert parse_ks("3, 5-9") == [3, 5, 7, 9]
    assert parse_ks("") is None


def test_export_page(loaded: MainWindow, run: Run, qtbot: QtBot, tmp_path: Path):
    page = loaded.export_page
    assert not page.export_button.isEnabled()
    run(loaded)
    assert page.export_button.isEnabled()
    for name, box in page.formats.items():
        box.setChecked(name in {"csv", "datasets"})
    with qtbot.waitSignal(page.finished, timeout=RUN_TIMEOUT) as blocker:
        page.export()
    page.wait()
    assert blocker.args == [True]
    assert page.files.count() > 0
    assert (tmp_path / "exports" / "datasets" / "training.dat").is_file()
    assert page.chosen_formats() == ["csv", "datasets"]


def test_table_model_roles(loaded: MainWindow, run: Run):
    run(loaded)
    assert loaded.state.result is not None
    table = next(t for t in run_tables(loaded.state.result) if t.key == "routes")
    model = TableModel(table)
    index = model.index(0, 2)
    assert model.data(index) == "D · training"
    assert model.data(index, Qt.ItemDataRole.BackgroundRole) is not None
    assert "training sample D" in model.data(index, Qt.ItemDataRole.ToolTipRole)
    assert model.data(model.index(0, 0), Qt.ItemDataRole.FontRole).bold()
    assert model.headerData(0, Qt.Orientation.Horizontal) == "№"
    assert model.headerData(0, Qt.Orientation.Vertical) == "1"
    assert model.columnCount() == len(table.columns)


def test_params_form(qtbot: QtBot):
    form = ParamsForm()
    qtbot.addWidget(form)
    form.set_plugin(METRICS, "minkowski", {"p": 4.0})
    assert form.values() == {"p": 4.0}
    form.set_plugin(METRICS, "weighted-zhuravlev", {})
    assert form.values() == {}
    editors = form._editors
    editors["nominal_weight"].setValue(0.5)  # type: ignore[attr-defined]
    editors["feature_weights"].setText("1, 2")  # type: ignore[attr-defined]
    assert form.values() == {"nominal_weight": 0.5, "feature_weights": [1.0, 2.0]}
    form.set_plugin(METRICS, "zhuravlev", {})
    assert form.values() == {}


def test_create_window_defaults(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, settings: Settings):
    from tests.conftest import ROOT

    monkeypatch.chdir(ROOT)
    created = create_window(settings=settings)
    qtbot.addWidget(created)
    assert created.state.dataset is not None
    assert created.state.dataset.name == "default (7, 13, 2)"
    with_config = create_window(
        config=CONFIGS / "heart-disease-270.yaml", theme="dark", settings=settings
    )
    qtbot.addWidget(with_config)
    assert with_config.state.dataset is not None
    assert with_config.state.dataset.m == 270


def test_self_test(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from tests.conftest import ROOT

    monkeypatch.chdir(ROOT)
    report = tmp_path / "self-test.txt"
    assert self_test(report) == 0
    text = report.read_text(encoding="utf-8")
    assert text.rstrip().endswith("PASSED")
    assert "the workbook's D" in text


def test_save_run_used_by_the_gui_is_the_service(loaded: MainWindow, run: Run, tmp_path: Path):
    run(loaded)
    assert loaded.state.result is not None
    folder = save_run(loaded.state.result, tmp_path / "manual")
    assert loaded.open_run(folder)


def test_light_theme_by_default_and_switching(window: MainWindow, qapp, settings: Settings):
    assert window.theme is ThemeName.LIGHT
    assert not is_dark(qapp.palette())
    assert window.theme_actions[ThemeName.LIGHT].isChecked()
    window.toggle_theme()
    assert window.theme is ThemeName.DARK
    assert is_dark(qapp.palette())
    assert settings.theme is ThemeName.DARK  # remembered
    window.set_theme("system")
    assert window.theme_actions[ThemeName.SYSTEM].isChecked()
    window.set_theme("nonsense")  # anything unknown is the default
    assert window.theme is ThemeName.LIGHT
    assert not is_dark(qapp.palette())


def test_the_template_style(window: MainWindow, qapp):
    sheet = qapp.styleSheet()
    assert "QListWidget#sidebar" in sheet
    assert "font-size: 10.0pt" in sheet  # the template's base size
    assert window.sidebar.objectName() == "sidebar"
    assert window.sidebar.item(0).text() == "1   Dataset"
    assert window.sidebar.width() >= 184
    assert window.run_page.start_button.objectName() == "primary"
    assert window.run_page.log.objectName() == "console"
    margins = window.dataset_page.layout().contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (18, 14, 18, 12)
    assert stylesheet(LIGHT, 1.5).count("15.0pt") >= 1


def test_zoom(window: MainWindow, qapp, settings: Settings):
    window.zoom(1)
    assert window.font_scale == FONT_SCALES[2]
    assert qapp.font().pointSizeF() == pytest.approx(11.5)
    assert settings.font_scale == FONT_SCALES[2]
    for _ in range(10):
        window.zoom(1)
    assert window.font_scale == FONT_SCALES[-1]
    window.zoom(0)
    assert window.font_scale == 1.0
    window.zoom(-1)
    assert window.font_scale == FONT_SCALES[0]


def test_settings_survive_a_new_window(qtbot: QtBot, settings: Settings, monkeypatch):
    from tests.conftest import ROOT

    monkeypatch.chdir(ROOT)
    first = MainWindow(settings=settings)
    qtbot.addWidget(first)
    first.set_theme("dark")
    first.zoom(1)
    first.close()
    second = MainWindow(settings=settings)
    qtbot.addWidget(second)
    assert second.theme is ThemeName.DARK
    assert second.font_scale == FONT_SCALES[2]
    assert settings.geometry() is not None
    second.set_theme("light")
    settings.store.setValue("appearance/font_scale", "huge")
    assert settings.font_scale == 1.0


def test_status_badges(loaded: MainWindow):
    assert loaded.reading_label.text().startswith("literal · A=1 B=1 C=1")
    assert loaded.notes_button.isHidden()
    loaded.configure_page.readings["blocked_cover"].setCurrentIndex(1)
    assert "custom" in loaded.reading_label.text()
    assert not loaded.notes_button.isHidden()
    assert "B" in loaded.notes_button.text()
    assert not loaded.configure_page.warning.isHidden()
    loaded.notes_button.click()
    assert loaded.stack.currentWidget() is loaded.configure_page


def test_copying_table_cells(loaded: MainWindow, run: Run, qapp):
    run(loaded)
    view = loaded.results_page.views["routes"]
    view.selectRow(0)
    text = view.copy_selection()
    assert text.startswith("S₁\t")
    assert qapp.clipboard().text() == text
    view.clearSelection()
    assert view.copy_selection() == ""


def test_a_second_run_replaces_the_tabs(loaded: MainWindow, run: Run, qapp):
    from PySide6.QtCore import QCoreApplication, QEvent

    run(loaded)
    first = loaded.results_page.views["routes"]
    count = loaded.results_page.tabs.count()
    run(loaded)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert loaded.results_page.tabs.count() == count  # replaced, not added
    assert loaded.results_page.views["routes"] is not first
    loaded.toggle_theme()  # restyling after several runs (the case that crashed)
    loaded.zoom(1)
    loaded.toggle_theme()
    loaded.zoom(0)
