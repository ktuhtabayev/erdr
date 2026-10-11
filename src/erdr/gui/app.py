"""Starting the desktop application: ``erdr gui``, the ``erdr-gui`` script and the executable."""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
import traceback
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtWidgets import QApplication

from erdr import __version__
from erdr.gui.settings import Settings
from erdr.gui.theme import ThemeName, is_dark
from erdr.gui.window import APP_TITLE, MainWindow

SELF_TEST_SECONDS = 120.0
"""How long the self-test waits for a run."""


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """The Qt application (the running one, if there is one)."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    app = QApplication(list(argv) if argv is not None else sys.argv[:1])
    app.setOrganizationName("erdr")
    app.setApplicationName("erdr")
    app.setApplicationDisplayName(APP_TITLE)
    app.setStyle("Fusion")  # the same look everywhere
    return app


def create_window(
    *,
    dataset: str | None = None,
    config: Path | None = None,
    theme: str | None = None,
    settings: Settings | None = None,
) -> MainWindow:
    """The main window with what the command line named (the default dataset otherwise).

    Args:
        dataset: A dataset file, id or name to open.
        config: A configuration file to open.
        theme: ``light``, ``dark`` or ``system`` for this session (and remembered).
        settings: Where the window keeps its settings (default: the user's).
    """
    window = MainWindow(settings=settings)
    if theme is not None:
        window.set_theme(theme)
    if config is not None:
        window.open_config(config)
    if dataset is not None:
        window.dataset_page.load(dataset)
    elif window.state.dataset is None:
        window.dataset_page.load("default")
    return window


def launch(
    *, dataset: str | None = None, config: Path | None = None, theme: str | None = None
) -> int:
    """Run the application until its window is closed; returns the exit code."""
    app = create_application()
    window = create_window(dataset=dataset, config=config, theme=theme)
    window.show()
    return int(app.exec())


def _wait(condition: list[bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while not condition and time.monotonic() < deadline:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    return bool(condition)


def self_test(report: Path | None = None) -> int:
    """Check an installation without showing a window; 0 if every check passed.

    Loads the default dataset, runs ERDR in the worker thread (it must give the workbook's
    D = {S₁, S₂, S₅, S₆, S₇} on the default dataset), shows a table, a figure and the hypersphere
    explorer, compares the readings and exports every format into a temporary folder. The result
    goes to ``report`` (a windowed program has no console) and the exit code.
    """
    lines = [f"erdr {__version__} self-test"]
    passed = True

    def check(what: str, ok: bool) -> None:
        nonlocal passed
        passed = passed and ok
        lines.append(f"{'ok  ' if ok else 'FAIL'}  {what}")

    scratch_settings = tempfile.TemporaryDirectory()
    try:
        app = create_application()
        problems: list[str] = []
        store = QSettings(
            str(Path(scratch_settings.name) / "settings.ini"), QSettings.Format.IniFormat
        )
        window = create_window(settings=Settings(store))  # the user's settings stay untouched
        window.show_message = lambda title, text: problems.append(f"{title}: {text}")  # type: ignore[method-assign]
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        window.show()
        dataset = window.state.dataset
        check(f"default dataset: {dataset.name if dataset else 'none'}", dataset is not None)
        check("light theme (the default)", not is_dark(app.palette()))
        window.set_theme(ThemeName.DARK)
        check("dark theme", is_dark(app.palette()))
        window.set_theme(ThemeName.LIGHT)
        ended: list[bool] = []
        window.run_page.finished.connect(lambda ok: ended.append(ok))
        window.run_page.start()
        check("run finished", _wait(ended, SELF_TEST_SECONDS) and ended[0])
        result = window.state.result
        if result is not None:
            names = result.object_names
            training = [names[i] for i in result.result.training]
            check(f"training sample {training}", len(training) > 0)
            if result.dataset.m == 7 and result.dataset.n == 13:
                check(
                    "the workbook's D = {S₁, S₂, S₅, S₆, S₇}",
                    training == ["S₁", "S₂", "S₅", "S₆", "S₇"],
                )
            view = window.results_page.views.get("characteristics")
            check(
                "table shown",
                view is not None and view.model() is not None and view.model().rowCount() > 0,
            )
            window.results_page.show_tab("figures")
            check("figure drawn", len(window.results_page.figure_view.figure.axes) > 0)
            explorer = window.results_page.explorer
            window.results_page.show_tab("explorer")
            explorer.show_iteration(1)
            explorer.step(1)
            check(
                "hypersphere explorer",
                len(explorer.figure_view.figure.axes) > 0
                and explorer.table_view.model() is not None,
            )
            compared: list[bool] = []
            window.state.analysisChanged.connect(lambda: compared.append(True))
            window.analysis_page.compare()
            check(
                "readings compared",
                _wait(compared, SELF_TEST_SECONDS) and bool(window.state.readings),
            )
            with tempfile.TemporaryDirectory() as scratch:
                exported: list[bool] = []
                window.export_page.finished.connect(lambda ok: exported.append(ok))
                window.export_page.folder.setText(scratch)
                for box in window.export_page.formats.values():
                    box.setChecked(True)
                window.export_page.export()
                done = _wait(exported, SELF_TEST_SECONDS) and exported[0]
                count = window.export_page.files.count()
                check(f"every format exported ({count} files)", done and count > 0)
                window.export_page.wait()
        for problem in problems:
            lines.append(f"      reported: {problem.splitlines()[0] if problem else ''}")
        check("no problem reported", not problems)
        window.close()
    except Exception:  # the report must say what broke
        passed = False
        lines.append("FAIL  " + traceback.format_exc())
    finally:
        scratch_settings.cleanup()
    lines.append("PASSED" if passed else "FAILED")
    text = "\n".join(lines) + "\n"
    if report is not None:
        report.write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        sys.stdout.write(text)
    return 0 if passed else 1


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point of ``erdr-gui`` and of the Windows executable."""
    parser = argparse.ArgumentParser(prog="erdr-gui", description=APP_TITLE)
    parser.add_argument("dataset", nargs="?", help="dataset file, id or name to open")
    parser.add_argument("--config", "-c", type=Path, help="configuration file to open")
    parser.add_argument(
        "--theme",
        choices=[name.value for name in ThemeName],
        help="light (default), dark, or system — the Windows light or dark mode",
    )
    parser.add_argument(
        "--self-test",
        nargs="?",
        const="-",
        metavar="REPORT",
        help="check the installation and exit",
    )
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    if arguments.self_test is not None:
        target = None if arguments.self_test == "-" else Path(arguments.self_test)
        raise SystemExit(self_test(target))
    raise SystemExit(
        launch(dataset=arguments.dataset, config=arguments.config, theme=arguments.theme)
    )


if __name__ == "__main__":
    main()
