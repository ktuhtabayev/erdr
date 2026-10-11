"""Colour categories (ADR-019): one meaning, one colour in tables, Excel, HTML, figures, CLI."""

import re
from pathlib import Path

import openpyxl
import pytest
from matplotlib.colors import to_hex
from typer.testing import CliRunner

from erdr.cli.app import app, paint
from erdr.config import preset
from erdr.core.readings import CLOSEST, LITERAL, BlockedCover, Readings
from erdr.export import ExportOptions, export_result
from erdr.export.figures import reading_colour, readings_figure, run_figure, sweep_figure
from erdr.export.report import legend_html, table_html
from erdr.export.tables import readings_table, run_tables, sample_table, sweep_table
from erdr.export.theme import (
    CLASSES,
    D_ACCENT,
    F_ACCENT,
    LEGEND_GROUPS,
    MUTED,
    READING_COLOURS,
    SERIES,
    SWATCHES,
    class_colour,
    class_mark,
    hex_rgb,
    legend,
    meaning,
    stage_of,
    swatch,
)
from erdr.services.analysis import compare_readings, sweep_k
from erdr.services.experiment import ExperimentResult, run_experiment
from tests.conftest import ROOT

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(scope="module")
def tables(default_run: ExperimentResult) -> dict[str, object]:
    return {t.key: t for t in run_tables(default_run)}


# ---------------------------------------------------------------- the theme


def test_every_mark_has_colours_and_a_place_in_the_legend():
    grouped = [mark for _, marks in LEGEND_GROUPS for mark in marks]
    assert sorted(grouped) == sorted(SWATCHES)  # each mark once, in one section
    for found in SWATCHES.values():
        for colour in (found.fill, found.ink, found.accent):
            assert re.fullmatch(r"#[0-9a-f]{6}", colour)
        assert found.meaning


def test_the_workbook_legend_and_the_class_colours():
    # the ERDR workbook's own colours (its Overview, "Colour legend")
    assert SWATCHES["quantitative"].fill == "#ddebf7"
    assert SWATCHES["nominal"].fill == "#fff2cc"
    assert SWATCHES["class"].fill == "#f4cccc"
    assert SWATCHES["parameter"].fill == "#e4dfec"
    # classes take the figures' categorical slots in order; D and F keep clear of K1, K2
    assert [CLASSES[f"K{i + 1}"].accent for i in range(8)] == list(SERIES)
    assert {D_ACCENT, F_ACCENT}.isdisjoint(SERIES[:2])
    assert SWATCHES["D"].fill not in (CLASSES["K1"].fill, CLASSES["K2"].fill)
    assert class_mark(0) == "K1"
    assert class_mark(8) == "class"  # past the palette: the class category, never a cycle
    assert class_colour(1) == SERIES[1]
    assert class_colour(8) == MUTED
    assert swatch(None) is None
    assert swatch("unknown") is None
    assert meaning("K2", (1, 2)) == "class K2 (label 2)"
    assert meaning("D") == "training sample D"
    assert hex_rgb("#2a78d6") == (42, 120, 214)


def test_legend_keeps_the_theme_order():
    assert legend(["enemy", "K2", None, "quantitative", "K1", "nope"]) == [
        ("Columns", ["quantitative"]),
        ("Classes", ["K1", "K2"]),
        ("Steps of the algorithm", ["enemy"]),
    ]
    assert legend([]) == []


def test_stages_follow_the_workbook_tabs():
    stage = stage_of("ERDR Characteristics")
    assert stage is not None
    assert stage.colour == "#c55a11"
    assert stage_of("Dataset") is not None
    assert stage_of("nothing") is None


# ---------------------------------------------------------------- the tables


def test_features_and_classes_are_marked(default_run: ExperimentResult, tables):
    data = tables["dataset"]
    ds = default_run.dataset
    expected = tuple("quantitative" if q else "nominal" for q in ds.quantitative)
    assert data.header_marks == (None, *expected, "class")
    classes = [data.mark(i, len(data.columns) - 1) for i in range(ds.m)]
    assert classes == [f"K{int(i) + 1}" for i in ds.class_index]
    type_row = data.rows.index(next(r for r in data.rows if r[0] == "Type"))
    assert data.marks[type_row] == ("type", *expected, "type")
    normalized = tables["normalized"]
    assert normalized.marks[-1][0] == "statistic"
    assert normalized.header_mark(1) == expected[0]
    assert sample_table(ds).header_marks == data.header_marks


def test_samples_classes_and_steps_are_marked(default_run: ExperimentResult, tables):
    routes = tables["routes"]
    for r, row in enumerate(routes.rows):
        assert routes.mark(r, 2) == ("D" if row[2].startswith("D") else "F")
        assert routes.mark(r, 1) in ("K1", "K2")
    assert routes.header_mark(1) == "class"
    characteristics = tables["characteristics"]
    marks = dict(zip(characteristics.columns, characteristics.header_marks, strict=True))
    assert marks["r(Sᵢ)"] == "characteristic"
    assert marks["d(Sᵢ)"] == "priority"
    assert marks["Class"] == "class"
    composition = tables["composition"]
    assert composition.header_marks[1:3] == ("K1", "K2")
    distances = tables["distances"]
    assert distances.header_marks[1:] == tuple(distances.mark(i, 0) for i in range(7))
    iterations = tables["iterations"]
    columns = dict(zip(iterations.columns, iterations.header_marks, strict=True))
    assert (columns["|D| after"], columns["|F| after"]) == ("D", "F")
    summary = tables["summary"]
    assert ("parameter", "literal") in summary.marks
    assert (None, "D") in summary.marks
    assert (None, "F") in summary.marks
    for table in tables.values():
        assert table.used_marks() <= set(SWATCHES), table.key


def test_a_reading_that_is_not_literal_is_flagged(default_dataset, heart270):
    rows = compare_readings(default_dataset)
    table = readings_table(rows, default_dataset.object_ids, 2)
    literal = next(r for r, row in enumerate(rows) if row.readings.is_literal)
    assert table.marks[literal][:4] == ("literal",) * 4
    a2 = next(r for r, row in enumerate(rows) if row.readings.code == "211")
    assert table.marks[a2][:4] == ("warning", "literal", "literal", "literal")
    assert table.header_marks[:4] == ("parameter",) * 4
    swept = sweep_k(default_dataset, ks=[1, 3])
    sweep = sweep_table(swept, 2)
    assert [m[-1] for m in sweep.marks] == ["yes" if row.permitted else "no" for row in swept]
    assert {"yes", "no"} <= {m[-1] for m in sweep.marks}
    assert [m[1] for m in sweep.marks] == [
        "literal" if row.readings.is_literal else "warning" for row in swept
    ]
    summary = run_tables(run_experiment(preset("closest"), heart270))[0]
    assert ("parameter", "warning") in summary.marks


# ---------------------------------------------------------------- Excel and HTML


def test_excel_and_html_use_the_theme(tmp_path: Path, default_run: ExperimentResult):
    options = ExportOptions(readings=compare_readings(default_run.dataset))
    export_result(default_run, tmp_path, ["xlsx", "html"], options)
    book = openpyxl.load_workbook(tmp_path / "workbook.xlsx")
    assert book["Dataset"].sheet_properties.tabColor.rgb.endswith("2F5597")
    assert book["ERDR Characteristics"].sheet_properties.tabColor.rgb.endswith("C55A11")
    header = book["Dataset"]["B2"]  # x₁: quantitative
    assert header.value == "x₁"
    assert header.fill.fgColor.rgb.endswith("DDEBF7")
    assert book["Dataset"]["C2"].fill.fgColor.rgb.endswith("FFF2CC")  # x₂: nominal
    routes = book["Training & Validation"]
    sample = routes["C3"]
    expected = SWATCHES["D" if sample.value.startswith("D") else "F"]
    assert sample.fill.fgColor.rgb.endswith(expected.fill[1:].upper())
    assert sample.font.color.rgb.endswith(expected.ink[1:].upper())
    legend_cells = [c.value for c in book["Overview"]["A"] if c.value]
    assert "class K1 (label 1)" in legend_cells
    assert "quantitative feature (set I)" in legend_cells
    assert "does not occur / not permitted" not in legend_cells  # unused marks are left out
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert ".m-K1 { background:#d6e6fa; color:#123f7a; }" in html
    assert '<th class="m-quantitative" title="quantitative feature (set I)">x₁</th>' in html
    assert '<span class="m-F">validation sample F</span>' in html


def test_html_helpers(tables):
    section = table_html(tables["routes"])
    assert 'class="m-class"' in section
    assert 'title="training sample D"' in section
    assert legend_html([]) == ""
    assert "<b>Classes</b>" in legend_html([tables["routes"]], (1, 2))


# ---------------------------------------------------------------- figures


def _line_colours(figure) -> list[str]:
    return [to_hex(line.get_color()) for line in figure.axes[0].get_lines()]


def test_figures_colour_by_class_sample_and_reading(default_run: ExperimentResult):
    sizes = _line_colours(run_figure("sizes", default_run))
    assert {D_ACCENT, F_ACCENT, MUTED} <= set(sizes)
    radii = run_figure("radii", default_run).axes[0]
    first = radii.collections[1].get_facecolors()  # r(Sᵢ): filled, in the class colour
    classes = default_run.result.characteristics.classes
    assert to_hex(first[0]) == class_colour(int(classes[0]))
    other = Readings(blocked_cover=BlockedCover.DROPPED)
    assert reading_colour(LITERAL) == READING_COLOURS[0]
    assert reading_colour(CLOSEST, [CLOSEST]) == READING_COLOURS[1]
    assert reading_colour(other, [LITERAL, other]) == READING_COLOURS[2]
    assert reading_colour(other) == MUTED
    # a reading keeps its colour whichever readings are drawn with it
    rows = sweep_k(default_run.dataset, ks=[1], readings=[CLOSEST, LITERAL])
    assert set(_line_colours(sweep_figure(rows, 7))) == set(READING_COLOURS[:2])
    bars = readings_figure(compare_readings(default_run.dataset), 7).axes[0].patches
    hues = [to_hex(bar.get_facecolor()) for bar in bars]
    assert hues.count(READING_COLOURS[0]) == 1
    assert hues.count(MUTED) == len(hues) - 1


# ---------------------------------------------------------------- the console


def test_console_colours(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.delenv("NO_COLOR", raising=False)
    runner = CliRunner()
    coloured = runner.invoke(app, ["run", "default", "--trace"], color=True)
    assert coloured.exit_code == 0
    red, green, blue = hex_rgb(D_ACCENT)
    assert f"\x1b[38;2;{red};{green};{blue}m" in coloured.output  # D in its colour
    plain = runner.invoke(app, ["run", "default", "--trace"])  # not a terminal
    assert not ANSI.search(plain.output)
    assert ANSI.sub("", coloured.output) == plain.output
    monkeypatch.setenv("NO_COLOR", "1")
    assert paint("D", "D") == "D"
    no_colour = runner.invoke(app, ["run", "default"], color=True)
    assert not ANSI.search(no_colour.output)
