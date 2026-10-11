r"""Take the screenshots of ``docs/gui.md`` (every page of the desktop application).

Run from the repository root::

    .\.venv\Scripts\python.exe scripts\gui_screenshots.py

The window is laid out by the platform but never shown on screen; each page is grabbed after the
default dataset has been run, the readings compared and a k sweep made.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "gui"


def main() -> int:
    """Grab every page into ``docs/images/gui``."""
    os.chdir(ROOT)
    # the native platform draws with the system fonts (Qt's offscreen platform has none)
    os.environ["QT_QPA_PLATFORM"] = "windows"
    from PySide6.QtCore import QCoreApplication, Qt

    from erdr.gui.app import create_application, create_window

    create_application()
    window = create_window()
    window.show_message = lambda title, text: print(f"{title}: {text}", file=sys.stderr)  # type: ignore[method-assign]
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1360, 860)
    window.show()

    def settle(seconds: float = 0.5) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)

    def wait_for(page: object) -> None:
        while page.tasks.busy():  # type: ignore[attr-defined]
            settle(0.1)
        settle()

    OUT.mkdir(parents=True, exist_ok=True)
    window.run_page.start()
    wait_for(window.run_page)
    window.analysis_page.both_z.setChecked(False)
    window.analysis_page.compare()
    wait_for(window.analysis_page)
    window.analysis_page.ks.setText("1-5")
    window.analysis_page.sweep()
    wait_for(window.analysis_page)
    window.analysis_page._show_readings_figure()
    shots = [
        ("dataset", window.dataset_page, None),
        ("configure", window.configure_page, None),
        ("run", window.run_page, None),
        ("results-iterations", window.results_page, "iterations"),
        ("results-characteristics", window.results_page, "characteristics"),
        ("results-figure", window.results_page, "figures"),
        ("readings", window.analysis_page, None),
        ("export", window.export_page, None),
    ]
    for name, page, tab in shots:
        window.go_to(page)
        if tab is not None:
            window.results_page.show_tab(tab)
        settle()
        window.grab().save(str(OUT / f"{name}.png"))
        print(OUT / f"{name}.png")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
