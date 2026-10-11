"""Desktop application (PySide6).

Workflow: Dataset → Configure → Run → Results → Readings & k → Export. The GUI is one more
interface above the services — it computes nothing itself. A run is
:func:`~erdr.services.experiment.run_experiment` in a worker thread; what the pages show are the
tables (:mod:`erdr.export.tables`) and figures (:mod:`erdr.export.figures`) the exporters write, so
the screen, the exported files and the workbook cannot disagree.

PySide6 is the optional extra ``[gui]``; nothing here is imported by the library or the CLI unless
the application is started (``erdr gui`` or ``erdr-gui``).
"""

from __future__ import annotations

GUI_EXTRA_HINT = 'the desktop application needs PySide6: pip install "erdr[gui]"'
"""Shown when the application is started without PySide6."""

__all__ = ["GUI_EXTRA_HINT"]
