"""The ``erdr`` command.

Commands: ``config`` (show, init, check), ``data`` (list, check, info), ``plugins`` (the
normalizers, metrics, formats and datasets that can be chosen), ``run`` (ERDR on a dataset: Step
1, the trace, D and F, the cases; optionally saved and exported), ``readings`` (every reading of
§1.1), ``sweep`` (|D| for many k), ``validate`` (the package against the ERDR workbook),
``runs`` and ``export`` (saved run folders) and ``gui`` (the desktop application).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from erdr import __version__
from erdr.config import (
    ConfigFormat,
    ExperimentConfig,
    PluginSpec,
    PresetName,
    ReadingsConfig,
    config_hash,
    dumps,
    load_config,
    matching_preset,
    preset,
    reading_notes,
    save_config,
)
from erdr.core.metrics import METRICS, traits_of
from erdr.core.normalizers import NORMALIZERS
from erdr.core.readings import CLOSEST, LITERAL, Readings, ZScope
from erdr.data import DATASETS, LOADERS, Dataset, load_from_config
from erdr.data.catalog import project_catalog, resolve_dataset
from erdr.errors import ConfigError, ERDRError
from erdr.export import EXPORTERS, ExportOptions, export_result, resolve_formats
from erdr.export.tables import (
    Table,
    cases_table,
    characteristics_table,
    iterations_table,
    readings_table,
    routes_table,
    sweep_table,
)
from erdr.export.text import display
from erdr.gui import GUI_EXTRA_HINT
from erdr.log import configure_logging
from erdr.notation import object_order, object_set
from erdr.services.analysis import compare_readings, sweep_k
from erdr.services.datasets import summarize
from erdr.services.experiment import ExperimentResult, run_experiment
from erdr.services.runs import RunError, latest_run, list_runs, load_run, save_run
from erdr.services.validation import DEFAULT_TOLERANCE, find_workbook, validate_workbook

EXIT_FAILED = 1
EXIT_USAGE = 2
TABLE_ROWS = 40
"""Tables longer than this are cut in the console (``--all`` shows everything)."""

app = typer.Typer(
    name="erdr",
    help="Enemy-Radius Density Reduction (ERDR): training / validation split.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(
    help="Create, show and check experiment configurations.", no_args_is_help=True
)
data_app = typer.Typer(
    help="Inspect datasets: sizes, feature types, classes, permitted k.", no_args_is_help=True
)
app.add_typer(config_app, name="config")
app.add_typer(data_app, name="data")

ConfigOption = Annotated[
    Path | None, typer.Option("--config", "-c", help="Configuration file (.yaml, .toml, .json).")
]
DatasetArgument = Annotated[
    str | None,
    typer.Argument(help="Dataset file, id or name (default: the configuration's, else 'default')."),
]


def _fail(error: ERDRError) -> typer.Exit:
    typer.echo(f"error: {error}", err=True)
    return typer.Exit(EXIT_USAGE)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"erdr {__version__}")
        raise typer.Exit()


@app.callback()
def main_options(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
    verbose: Annotated[
        int, typer.Option("--verbose", "-v", count=True, help="More log output (-v, -vv).")
    ] = 0,
) -> None:
    """Enemy-Radius Density Reduction (ERDR): training / validation split."""
    levels = {0: "WARNING", 1: "INFO"}
    configure_logging(levels.get(verbose, "DEBUG"))


# ---------------------------------------------------------------- console tables


def echo_table(table: Table, *, limit: int | None = TABLE_ROWS, decimals: int = 4) -> None:
    """Print a table with aligned columns (floats rounded for the console)."""
    rows = [[display(v, decimals) for v in row] for row in table.rows]
    shown = rows if limit is None or len(rows) <= limit else rows[:limit]
    columns = list(table.columns)
    widths = [len(c) for c in columns]
    for row in shown:
        for j, cell in enumerate(row):
            widths[j] = min(max(widths[j], len(cell)), 48)

    def line(cells: Sequence[str]) -> str:
        parts = []
        for j, cell in enumerate(cells):
            text = cell if len(cell) <= widths[j] else cell[: widths[j] - 1] + "…"
            parts.append(text.ljust(widths[j]) if j == 0 else text.rjust(widths[j]))
        return "  ".join(parts).rstrip()

    typer.echo(table.title)
    typer.echo(line(columns))
    typer.echo("  ".join("─" * w for w in widths))
    for row in shown:
        typer.echo(line(row))
    if len(shown) < len(rows):
        typer.echo(f"… {len(rows) - len(shown)} more rows (--all shows every row)")
    typer.echo("")


# ---------------------------------------------------------------- erdr config


@config_app.command("show")
def config_show(
    name: Annotated[
        PresetName, typer.Option("--preset", "-p", help="Preset to print.")
    ] = PresetName.LITERAL,
    fmt: Annotated[
        ConfigFormat, typer.Option("--format", "-f", help="Output format.")
    ] = ConfigFormat.YAML,
) -> None:
    """Print a preset configuration."""
    typer.echo(dumps(preset(name), fmt), nl=False)


@config_app.command("init")
def config_init(
    path: Annotated[Path, typer.Argument(help="File to create (.yaml, .yml, .toml or .json).")],
    name: Annotated[
        PresetName, typer.Option("--preset", "-p", help="Preset to start from.")
    ] = PresetName.LITERAL,
    force: Annotated[bool, typer.Option("--force", help="Overwrite an existing file.")] = False,
) -> None:
    """Write a new configuration file from a preset."""
    try:
        save_config(preset(name), path, overwrite=force)
    except ERDRError as error:
        raise _fail(error) from error
    typer.echo(f"wrote {path}")


@config_app.command("check")
def config_check(
    path: Annotated[Path, typer.Argument(help="Configuration file to check.")],
) -> None:
    """Validate a configuration: keys, values and plug-in parameters."""
    try:
        config = load_config(path)
        NORMALIZERS.make_params(
            config.preprocessing.normalizer.name, config.preprocessing.normalizer.params
        )
        METRICS.make_params(config.distance.metric.name, config.distance.metric.params)
    except ERDRError as error:
        raise _fail(error) from error
    chosen = matching_preset(config)
    typer.echo(f"{path}: valid")
    typer.echo(f"  hash    {config_hash(config)}")
    typer.echo(f"  preset  {chosen.value if chosen else 'custom'}")
    typer.echo(f"  reading {config.erdr.readings.to_readings().label}")
    for note in reading_notes(config):
        typer.echo(f"  ⚠ {note.switch}: {note.statement}")


def _config(path: Path | None) -> tuple[ExperimentConfig, Path | None]:
    if path is None:
        return ExperimentConfig(), None
    return load_config(path), path.resolve().parent


# ---------------------------------------------------------------- erdr data


@data_app.command("list")
def data_list() -> None:
    """List the datasets of the project's folder, the built-in datasets and the file formats."""
    catalog = project_catalog()
    if catalog is not None:
        typer.echo(f"datasets folder: {catalog.root}")
        for entry in catalog:
            shape = "({}, {}, {})".format(*entry.shape) if entry.shape else "?"
            typer.echo(f"  {entry.id:24s} {entry.name:32s} {shape:14s} {', '.join(entry.formats)}")
    else:
        typer.echo("no datasets folder (set ERDR_DATASETS or work inside the project)")
    typer.echo("built-in datasets:")
    for info in DATASETS:
        typer.echo(f"  {info.name:24s} {info.summary}")
    typer.echo("file formats: " + ", ".join(LOADERS.names()))


@data_app.command("check")
def data_check() -> None:
    """Load every file of the datasets folder; compare headers, names and formats."""
    catalog = project_catalog()
    if catalog is None:
        typer.echo("error: no datasets folder", err=True)
        raise typer.Exit(EXIT_USAGE)
    failed = False
    for check in catalog.check():
        mark = "✓" if check.passed else "✗"
        digest = check.content_hash[:12] if check.content_hash else "—"
        typer.echo(f"{mark} {check.entry.id:24s} {check.shape}  {digest}")
        for ext, digest in check.sha256.items():
            typer.echo(f"    {ext}  sha256 {digest}")
        for problem in check.problems:
            typer.echo(f"    problem: {problem}")
        failed = failed or not check.passed
    if failed:
        raise typer.Exit(EXIT_FAILED)


def _dataset(source: str | None, config: ExperimentConfig, base: Path | None) -> Dataset:
    """The dataset named on the command line, else the configuration's (relative to its file)."""
    if source is not None:
        return resolve_dataset(source)
    return load_from_config(config.dataset, base)


@data_app.command("info")
def data_info(source: DatasetArgument = None) -> None:
    """Sizes, feature types, classes and the permitted k of a dataset."""
    try:
        dataset = resolve_dataset(source)
    except ERDRError as error:
        raise _fail(error) from error
    s = summarize(dataset)
    typer.echo(f"{s.name}  {s.shape}")
    typer.echo(f"  source        {s.source or '—'}")
    typer.echo(f"  classes       {s.class_text}")
    typer.echo(f"  quantitative  {len(s.quantitative)}: {', '.join(s.quantitative) or '—'}")
    typer.echo(f"  nominal       {len(s.nominal)}: {', '.join(s.nominal) or '—'}")
    typer.echo(
        f"  permitted k   {s.permitted.text}  (odd k from 3 to 2·min|Kᵢ| − 3 = {s.permitted.k_max})"
    )
    typer.echo(
        f"  z(Sᵢ, k) exists for k ≤ {s.largest_k} (any class), "
        f"k ≤ {s.largest_k_own_class} (own class)"
    )
    typer.echo(f"  content hash  {s.content_hash}")


# ---------------------------------------------------------------- erdr plugins


@app.command("plugins")
def plugins() -> None:
    """List what can be chosen: normalizers, metrics, dataset formats, export formats, datasets."""
    for title, registry in (
        ("normalizers", NORMALIZERS),
        ("metrics", METRICS),
        ("dataset formats", LOADERS),
        ("export formats", EXPORTERS),
        ("built-in datasets", DATASETS),
    ):
        typer.echo(f"{title}:")
        for info in registry:
            extra = ""
            if registry is METRICS:
                domain = traits_of(METRICS.get(info.name)).domain
                extra = f"  [{domain}]" if domain != "any" else ""
            aliases = f"  (also: {', '.join(info.aliases)})" if info.aliases else ""
            typer.echo(f"  {info.name:20s} {info.summary}{extra}{aliases}")


# ---------------------------------------------------------------- erdr run


def _with_overrides(
    config: ExperimentConfig,
    *,
    preset_name: PresetName | None,
    k: int | None,
    epsilon: float | None,
    reading: str | None,
    z_scope: ZScope | None,
    metric: str | None,
    normalizer: str | None,
    k_rule: str | None,
) -> ExperimentConfig:
    erdr = config.erdr
    readings = erdr.readings.to_readings()
    if preset_name is not None:
        readings = LITERAL if preset_name is PresetName.LITERAL else CLOSEST
    if reading is not None:
        readings = Readings.from_code(reading, readings.z_scope)
    if z_scope is not None:
        readings = Readings(
            readings.self_in_l, readings.blocked_cover, readings.step5_return, z_scope
        )
    update: dict[str, object] = {"readings": ReadingsConfig.from_readings(readings)}
    if k is not None:
        update["k"] = k
    if epsilon is not None:
        update["epsilon"] = epsilon
    if k_rule is not None:
        update["k_rule"] = k_rule
    changes: dict[str, object] = {"erdr": erdr.model_copy(update=update)}
    if metric is not None:
        changes["distance"] = config.distance.model_copy(update={"metric": PluginSpec(name=metric)})
    if normalizer is not None:
        changes["preprocessing"] = config.preprocessing.model_copy(
            update={"normalizer": PluginSpec(name=normalizer)}
        )
    data = config.model_copy(update=changes).model_dump(mode="json")
    try:
        return ExperimentConfig.model_validate(data)
    except ValueError as error:
        raise ConfigError(str(error)) from error


PresetOption = Annotated[
    PresetName | None, typer.Option("--preset", "-p", help="Readings of a preset.")
]
KOption = Annotated[int | None, typer.Option("--k", "-k", help="k of z(Sᵢ, k).")]
ReadingOption = Annotated[
    str | None, typer.Option("--reading", "-r", help="Switches A, B, C as a code, e.g. 121.")
]
ZOption = Annotated[
    ZScope | None, typer.Option("--z-scope", help="z(Sᵢ, k) over all classes or the own class.")
]
MetricOption = Annotated[
    str | None, typer.Option("--metric", "-m", help="Metric (see 'erdr plugins').")
]
NormalizerOption = Annotated[
    str | None, typer.Option("--normalizer", "-n", help="Normalizer (see 'erdr plugins').")
]


def _print_run(run: ExperimentResult, *, show_all: bool, trace: bool) -> None:
    limit = None if show_all else TABLE_ROWS
    result = run.result
    names = run.object_names
    typer.echo(
        f"{run.dataset.name}  (m = {run.dataset.m}, n = {run.dataset.n})  ·  k = {run.k}  ·  "
        f"{result.readings.label}"
    )
    typer.echo(
        f"normalizer {run.distances.scaling.normalizer} · metric {run.distances.metric} · "
        f"ε = {result.epsilon}"
    )
    for note in run.notes:
        typer.echo(f"⚠ not the literal article reading — {note}")
    for warning in run.warnings:
        typer.echo(f"⚠ {warning}")
    typer.echo("")
    if trace:
        echo_table(characteristics_table(run), limit=limit)
        echo_table(iterations_table(run), limit=limit)
    small = run.dataset.m <= 60  # object lists of larger samples do not fit a line
    queue = object_order(result.characteristics.priority, names) if small else "…"
    typer.echo(f"Step 2 queue order: {queue}")
    typer.echo(f"iterations: {len(result.iterations)}")
    d_counts = ", ".join(str(c) for c in run.class_counts(result.training))
    f_counts = ", ".join(str(c) for c in run.class_counts(result.validation))
    d_set = object_set(result.training, names) if small else ""
    f_set = object_set(result.validation, names) if small else ""
    typer.echo(f"D (training):   {result.training.size:4d}  by class {d_counts}   {d_set}")
    typer.echo(f"F (validation): {result.validation.size:4d}  by class {f_counts}   {f_set}")
    typer.echo(f"cases: {sum(c.occurs for c in run.cases)} of {len(run.cases)} occur")
    if trace:
        typer.echo("")
        echo_table(routes_table(run), limit=limit)
        echo_table(cases_table(run), limit=None)


@app.command("run")
def run(
    source: DatasetArgument = None,
    config_path: ConfigOption = None,
    preset_name: PresetOption = None,
    k: KOption = None,
    epsilon: Annotated[
        float | None, typer.Option("--epsilon", help="ε > 0 of the blocking.")
    ] = None,
    reading: ReadingOption = None,
    z_scope: ZOption = None,
    metric: MetricOption = None,
    normalizer: NormalizerOption = None,
    k_rule: Annotated[str | None, typer.Option("--k-rule", help="enforce, warn or off.")] = None,
    trace: Annotated[
        bool,
        typer.Option(
            "--trace/--brief", help="Show Step 1, every iteration, the routes and the cases."
        ),
    ] = True,
    show_all: Annotated[bool, typer.Option("--all", help="Show every row of long tables.")] = False,
    save: Annotated[bool, typer.Option("--save/--no-save", help="Write a run folder.")] = False,
    runs_dir: Annotated[
        Path | None, typer.Option("--runs-dir", help="Folder of the run folders.")
    ] = None,
    export: Annotated[
        list[str] | None,
        typer.Option("--export", "-e", help="Export formats (comma-separated or 'all')."),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", "-o", help="Export folder (default: the run folder or ./exports)."),
    ] = None,
) -> None:
    """Run ERDR on a dataset and show Step 1, the iterations, D, F and the cases."""
    try:
        config, base = _config(config_path)
        config = _with_overrides(
            config,
            preset_name=preset_name,
            k=k,
            epsilon=epsilon,
            reading=reading,
            z_scope=z_scope,
            metric=metric,
            normalizer=normalizer,
            k_rule=k_rule,
        )
        experiment = run_experiment(config, _dataset(source, config, base))
        _print_run(experiment, show_all=show_all, trace=trace)
        folder = save_run(experiment, runs_dir) if save else None
        if folder is not None:
            typer.echo(f"run saved: {folder}")
        if export:
            target = out or (folder / "export" if folder else Path("exports"))
            files = export_result(experiment, target, resolve_formats(export))
            typer.echo(f"exported {len(files)} files to {target}")
    except (ERDRError, ValueError) as error:
        raise _fail(error if isinstance(error, ERDRError) else ConfigError(str(error))) from error


# ---------------------------------------------------------------- erdr readings / sweep


@app.command("readings")
def readings(
    source: DatasetArgument = None,
    config_path: ConfigOption = None,
    k: KOption = None,
    both_z: Annotated[
        bool, typer.Option("--both-z", help="Also every reading with the own-class z.")
    ] = False,
) -> None:
    """Run every combination of the readings A, B, C (sheet Readings (Switches))."""
    try:
        config, base = _config(config_path)
        if k is not None:
            config = config.model_copy(update={"erdr": config.erdr.model_copy(update={"k": k})})
        dataset = _dataset(source, config, base)
        scopes = (ZScope.ALL, ZScope.OWN_CLASS) if both_z else (ZScope.ALL,)
        rows = compare_readings(dataset, config, z_scopes=scopes)
    except ERDRError as error:
        raise _fail(error) from error
    typer.echo(f"{dataset.name}  ·  k = {config.erdr.k}")
    echo_table(readings_table(rows, dataset.object_ids, len(dataset.classes)), limit=None)
    distinct = {row.training for row in rows if row.error is None}
    typer.echo(f"{len(distinct)} different training samples from {len(rows)} readings")


@app.command("sweep")
def sweep(
    source: DatasetArgument = None,
    config_path: ConfigOption = None,
    ks: Annotated[
        str | None,
        typer.Option(
            "--k", "-k", help="k values, e.g. 3,5,7 or 3-41 (default: every permitted k)."
        ),
    ] = None,
    reading: Annotated[
        list[str] | None,
        typer.Option(
            "--reading",
            "-r",
            help="Reading codes (default: literal and closest); add ':own' for the own-class z.",
        ),
    ] = None,
) -> None:
    """|D| for many k and readings (sheet Article Table 1 Check)."""
    try:
        config, base = _config(config_path)
        dataset = _dataset(source, config, base)
        chosen = [_parse_reading(code) for code in reading] if reading else [LITERAL, CLOSEST]
        rows = sweep_k(dataset, config, ks=_parse_ks(ks) if ks else None, readings=chosen)
    except (ERDRError, ValueError) as error:
        raise _fail(error if isinstance(error, ERDRError) else ConfigError(str(error))) from error
    typer.echo(f"{dataset.name}  (m = {dataset.m})")
    echo_table(sweep_table(rows, len(dataset.classes)), limit=None)


def _parse_reading(text: str) -> Readings:
    code, _, scope = text.partition(":")
    return Readings.from_code(
        code, ZScope.OWN_CLASS if scope.strip() in ("own", "own-class") else ZScope.ALL
    )


def _parse_ks(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            low, high = (int(v) for v in part.split("-", 1))
            values += list(range(low, high + 1, 2 if low % 2 == high % 2 else 1))
        elif part:
            values.append(int(part))
    return values


# ---------------------------------------------------------------- erdr validate


@app.command("validate")
def validate(
    against: Annotated[
        Path | None,
        typer.Option(
            "--against", "-a", help="The ERDR workbook (default: resources/Experiments/…)."
        ),
    ] = None,
    tolerance: Annotated[
        float, typer.Option(help="Largest accepted absolute difference of numbers.")
    ] = DEFAULT_TOLERANCE,
    details: Annotated[
        bool, typer.Option("--details", help="List every check, not only failed ones.")
    ] = False,
    fast: Annotated[
        bool, typer.Option("--fast", help="Skip the 270-object runs of Article Table 1 Check.")
    ] = False,
) -> None:
    """Compare the package with every computed sheet of the ERDR workbook."""
    path = against or find_workbook()
    if path is None:
        typer.echo("error: no ERDR workbook found — give it with --against", err=True)
        raise typer.Exit(EXIT_USAGE)
    try:
        report = validate_workbook(path, tolerance=tolerance, skip=("table1",) if fast else ())
    except ERDRError as error:
        raise _fail(error) from error
    typer.echo(f"{path.name}  ·  tolerance {tolerance:g}")
    for sheet, total, passed in report.sections():
        mark = "✓" if passed == total else f"✗ {total - passed} failed"
        typer.echo(f"  {sheet:26s} {total:5d} checks  {mark}")
    for check in report.checks if details else report.failures:
        mark = "✓" if check.passed else "✗"
        typer.echo(
            f"    {mark} [{check.section}] {check.name}: "
            f"workbook {check.expected!r}, package {check.actual!r}"
        )
    typer.echo(f"  {len(report.checks)} checks")
    if not report.passed:
        typer.echo("validation FAILED", err=True)
        raise typer.Exit(EXIT_FAILED)
    typer.echo("validation passed")


# ---------------------------------------------------------------- erdr runs / export


RunsDirOption = Annotated[Path, typer.Option("--runs-dir", help="Folder of the run folders.")]


@app.command("runs")
def runs(runs_dir: RunsDirOption = Path("runs")) -> None:
    """List the saved run folders, newest first."""
    found = list_runs(runs_dir)
    if not found:
        typer.echo(f"no runs in {runs_dir}")
        return
    for info in found:
        typer.echo(
            f"{info.run_id}  {info.dataset:28s} k = {info.k:<3d} {info.reading:28s} "
            f"|D| = {info.training_size}, |F| = {info.validation_size}"
        )


@app.command("export")
def export_run(
    folder: Annotated[
        Path | None, typer.Argument(help="Run folder (default: the latest run).")
    ] = None,
    formats: Annotated[
        list[str] | None, typer.Option("--format", "-f", help="Formats (comma-separated or 'all').")
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Export folder (default: <run>/export).")
    ] = None,
    runs_dir: RunsDirOption = Path("runs"),
    with_readings: Annotated[
        bool, typer.Option("--readings", help="Include every reading of §1.1.")
    ] = False,
    with_sweep: Annotated[
        bool, typer.Option("--sweep", help="Include |D| for every permitted k.")
    ] = False,
) -> None:
    """Repeat a saved run and export it (tables, workbook, figures, report, datasets)."""
    chosen = folder or latest_run(runs_dir)
    if chosen is None:
        typer.echo(f"error: no run folder given and none in {runs_dir}", err=True)
        raise typer.Exit(EXIT_USAGE)
    try:
        experiment = load_run(chosen)
        options = ExportOptions(
            readings=compare_readings(experiment.dataset, experiment.config)
            if with_readings
            else None,
            sweep=sweep_k(experiment.dataset, experiment.config) if with_sweep else None,
        )
        target = out or chosen / "export"
        files = export_result(experiment, target, resolve_formats(formats or ["all"]), options)
    except (ERDRError, RunError) as error:
        raise _fail(error) from error
    typer.echo(f"exported {len(files)} files to {target}")


# ---------------------------------------------------------------- erdr gui


@app.command("gui")
def gui(
    source: DatasetArgument = None,
    config_path: ConfigOption = None,
) -> None:
    """Start the desktop application (needs PySide6: the optional extra "gui")."""
    try:
        from erdr.gui.app import launch
    except ImportError as error:
        typer.echo(f"error: {GUI_EXTRA_HINT} ({error.name})", err=True)
        raise typer.Exit(EXIT_FAILED) from error
    raise typer.Exit(launch(dataset=source, config=config_path))


def _utf8_console() -> None:
    """Formulas use Unicode (ρ, ε, ∅, ⚠); Windows code pages cannot encode them."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    """Entry point of the ``erdr`` console script."""
    _utf8_console()
    app()
