"""Exporters: a run as CSV, JSON, Markdown, LaTeX, Excel, figures, an HTML report and datasets.

Formats are plug-ins of the :data:`EXPORTERS` registry (entry-point group ``erdr.exporters``).
Every exporter reads the same plain tables (:mod:`.tables`) and figures (:mod:`.figures`), so the
formats cannot disagree. :func:`export_result` writes the chosen formats into one folder:

``csv/<table>.csv`` · ``run.json`` · ``report.md`` · ``latex/<table>.tex`` · ``workbook.xlsx`` ·
``figures/<figure>.png|svg`` · ``report.html`` · ``datasets/training|validation.dat|csv``
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from matplotlib.figure import Figure

from erdr import __version__
from erdr.core.registry import Registry
from erdr.data.writers import write_extended
from erdr.errors import ConfigError
from erdr.export import excel, report, text
from erdr.export.figures import (
    RUN_FIGURES,
    readings_figure,
    run_figure,
    save_figure,
    sweep_figure,
)
from erdr.export.tables import MATRIX_LIMIT, Table, readings_table, run_tables, sweep_table
from erdr.services.analysis import ReadingRow, SweepRow
from erdr.services.experiment import ExperimentResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportOptions:
    """What an export contains besides the run itself."""

    readings: tuple[ReadingRow, ...] | None = None
    """A readings comparison to include (table and figure)."""
    sweep: tuple[SweepRow, ...] | None = None
    """A k sweep to include (table and figure)."""
    figure_formats: tuple[str, ...] = ("png", "svg")
    """File types of the figures."""
    dataset_formats: tuple[str, ...] | None = None
    """Formats of the training/validation samples (default: the configuration's)."""


Exporter = Callable[[ExperimentResult, Path, ExportOptions], list[Path]]
"""Writes one format of a run into a folder; returns the files written."""

EXPORTERS: Registry[Exporter] = Registry("exporters")
"""Export formats by name."""
ALL = "all"


def all_tables(run: ExperimentResult, options: ExportOptions) -> list[Table]:
    """The run's tables plus the analysis tables of ``options``."""
    tables = run_tables(run)
    classes = len(run.dataset.classes)
    if options.readings:
        tables.append(readings_table(options.readings, run.object_names, classes))
    if options.sweep:
        tables.append(sweep_table(options.sweep, classes))
    return tables


def all_figures(run: ExperimentResult, options: ExportOptions) -> list[tuple[str, str, Figure]]:
    """(key, name, figure) of the run's figures plus the analysis figures of ``options``."""
    figures = [(key, name, run_figure(key, run)) for key, (name, _) in RUN_FIGURES.items()]
    if options.readings:
        figures.append(("readings", "Readings", readings_figure(options.readings, run.result.m)))
    if options.sweep:
        figures.append(("sweep", "k sweep", sweep_figure(options.sweep, run.result.m)))
    return figures


def run_settings(run: ExperimentResult) -> list[tuple[str, str]]:
    """The settings of a run as (name, value) pairs for the report and the workbook."""
    config = run.config
    params = config.distance.metric.params
    metric = run.distances.metric + (f" {params}" if params else "")
    return [
        ("Dataset", f"{run.dataset.name}  (m = {run.dataset.m}, n = {run.dataset.n})"),
        ("Source", run.dataset.source or "—"),
        ("Normalizer", run.distances.scaling.normalizer),
        ("Metric · features", f"{metric} · {config.distance.features}"),
        ("Distance rounding", f"{config.distance.decimals} decimals"),
        ("k · k rule", f"{run.k} · {config.erdr.k_rule} (permitted: {run.permitted.text})"),
        ("ε", repr(config.erdr.epsilon)),
        ("Reading", run.result.readings.label),
        ("Configuration hash", run.config_hash),
        ("Dataset hash", run.dataset_hash),
        ("Run started (UTC)", run.started.isoformat(timespec="seconds")),
    ]


def _title(run: ExperimentResult) -> str:
    return f"ERDR — Enemy-Radius Density Reduction · {run.dataset.name}"


def export_csv(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """One CSV file per table (exact values, UTF-8 with BOM for Excel)."""
    return [
        text.write_text(folder / "csv" / f"{table.key}.csv", text.to_csv(table), bom=True)
        for table in all_tables(run, options)
    ]


def export_json(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """Every table and the settings in ``run.json``."""
    meta: dict[str, object] = {
        "erdr": __version__,
        "title": _title(run),
        "settings": dict(run_settings(run)),
        "notes": list(run.notes),
        "warnings": list(run.warnings),
    }
    return [text.write_text(folder / "run.json", text.to_json(all_tables(run, options), meta))]


def export_markdown(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """``report.md``: the settings and every table (large matrices left out)."""
    lines = [f"# {_title(run)}", ""]
    for note in run.notes:
        lines.append(f"> ⚠ Not the literal article reading — {note}")
    if run.notes:
        lines.append("")
    lines += [f"- **{name}:** {value}" for name, value in run_settings(run)]
    lines.append("")
    for table in all_tables(run, options):
        if table.matrix and run.result.m > MATRIX_LIMIT:
            continue
        lines.append(text.to_markdown(table))
    return [text.write_text(folder / "report.md", "\n".join(lines))]


def export_latex(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """One ``.tex`` table per table and ``tables.tex`` that inputs them all."""
    written: list[Path] = []
    inputs: list[str] = []
    for table in all_tables(run, options):
        if table.matrix and run.result.m > MATRIX_LIMIT:
            continue
        written.append(text.write_text(folder / "latex" / f"{table.key}.tex", text.to_latex(table)))
        inputs.append(f"\\input{{{table.key}}}")
    header = "% ERDR tables — needs \\usepackage{booktabs} and \\usepackage{amssymb}\n"
    written.append(
        text.write_text(folder / "latex" / "tables.tex", header + "\n".join(inputs) + "\n")
    )
    return written


def export_xlsx(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """``workbook.xlsx``: the tables stacked per workbook sheet, the figures on *Charts*."""
    figures = [(name, figure) for _, name, figure in all_figures(run, options)]
    path = excel.write_workbook(
        folder / "workbook.xlsx",
        all_tables(run, options),
        title=_title(run),
        settings=run_settings(run) + [("Note", note) for note in run.notes],
        figures=figures,
    )
    return [path]


def export_figures(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """Every figure as PNG and SVG (``options.figure_formats``)."""
    written: list[Path] = []
    for key, _, figure in all_figures(run, options):
        for fmt in options.figure_formats:
            written.append(save_figure(figure, folder / "figures" / f"{key}.{fmt}"))
    return written


def export_html(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """``report.html``: one self-contained page with the settings, figures and tables."""
    document = report.report_html(
        title=_title(run),
        subtitle=(
            f"Training sample D: {run.result.training.size} of {run.result.m} objects · "
            f"validation sample F: {run.result.validation.size} · "
            f"{len(run.result.iterations)} iterations"
        ),
        settings=run_settings(run),
        notes=run.notes,
        tables=all_tables(run, options),
        figures=[(name, figure) for _, name, figure in all_figures(run, options)],
        m=run.result.m,
        footer=f"configuration {run.config_hash[:12]} · dataset {run.dataset_hash[:12]}",
    )
    return [text.write_text(folder / "report.html", document)]


def export_datasets(run: ExperimentResult, folder: Path, options: ExportOptions) -> list[Path]:
    """The training and validation samples in the author's extended layout."""
    formats = options.dataset_formats or run.config.output.dataset_formats
    written: list[Path] = []
    for fmt in formats:
        written.append(
            write_extended(run.training_dataset, folder / "datasets" / f"training.{fmt}")
        )
        written.append(
            write_extended(run.validation_dataset, folder / "datasets" / f"validation.{fmt}")
        )
    return written


EXPORTERS.add("csv", export_csv, summary="one CSV file per table (exact values)")
EXPORTERS.add("json", export_json, summary="every table and the settings in run.json")
EXPORTERS.add("markdown", export_markdown, aliases=("md",), summary="report.md with every table")
EXPORTERS.add("latex", export_latex, aliases=("tex",), summary="LaTeX tables (booktabs)")
EXPORTERS.add(
    "xlsx", export_xlsx, aliases=("excel",), summary="workbook.xlsx laid out like the ERDR workbook"
)
EXPORTERS.add("figures", export_figures, summary="PNG and SVG figures")
EXPORTERS.add("html", export_html, aliases=("report",), summary="self-contained report.html")
EXPORTERS.add("datasets", export_datasets, summary="training and validation samples (.dat, .csv)")


def resolve_formats(names: Iterable[str]) -> list[str]:
    """Canonical format names; ``all`` expands to every format.

    Raises:
        ConfigError: An unknown format name.
    """
    resolved: list[str] = []
    for raw in names:
        for name in (part.strip() for part in raw.split(",")):
            if not name:
                continue
            if name.lower() == ALL:
                chosen = EXPORTERS.names()
            elif name in EXPORTERS:
                chosen = [EXPORTERS.info(name).name]
            else:
                available = ", ".join(EXPORTERS.names())
                raise ConfigError(f"unknown export format {name!r}; available: {available}, all")
            resolved += [n for n in chosen if n not in resolved]
    return resolved


def export_result(
    run: ExperimentResult,
    folder: Path,
    formats: Sequence[str] = (ALL,),
    options: ExportOptions | None = None,
) -> list[Path]:
    """Write ``run`` in the chosen formats into ``folder``; returns every file written."""
    chosen = options or ExportOptions()
    written: list[Path] = []
    for name in resolve_formats(formats):
        written += EXPORTERS.get(name)(run, folder, chosen)
    logger.info("run exported", extra={"folder": str(folder), "files": len(written)})
    return written


__all__ = [
    "ALL",
    "EXPORTERS",
    "ExportOptions",
    "Exporter",
    "all_figures",
    "all_tables",
    "export_result",
    "resolve_formats",
    "run_settings",
]
