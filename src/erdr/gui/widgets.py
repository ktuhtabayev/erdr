"""Reusable widgets: a table view, a figure canvas, a page frame and a log bridge."""

from __future__ import annotations

import logging
from collections.abc import Callable

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from erdr.export.tables import Table
from erdr.gui.models import TableModel
from erdr.log import KeyValueFormatter


class TableView(QTableView):
    """A read-only table of an exporter's :class:`~erdr.export.tables.Table`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty view."""
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setAlternatingRowColors(False)
        self.setWordWrap(False)
        self.setSortingEnabled(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.verticalHeader().setDefaultSectionSize(22)

    def show_table(self, table: Table, decimals: int = 6) -> None:
        """Show ``table``; columns are sized to their content (up to a limit)."""
        self.setModel(TableModel(table, decimals))
        self.resizeColumnsToContents()
        for column in range(len(table.columns)):
            if self.columnWidth(column) > 320:
                self.setColumnWidth(column, 320)
        self.setToolTip(table.note)


class FigureView(QWidget):
    """A matplotlib figure with its navigation toolbar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty figure."""
        super().__init__(parent)
        self.canvas = FigureCanvasQTAgg(Figure())  # type: ignore[no-untyped-call]
        self.toolbar = NavigationToolbar2QT(self.canvas, self)  # type: ignore[no-untyped-call]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

    def show_figure(self, figure: Figure) -> None:
        """Replace the drawing by ``figure``."""
        figure.set_canvas(self.canvas)
        self.canvas.figure = figure
        self.canvas.draw_idle()  # type: ignore[no-untyped-call]

    @property
    def figure(self) -> Figure:
        """The figure on screen."""
        return self.canvas.figure


class Page(QWidget):
    """A page of the main window: a title, an explanation and the content."""

    title = "Page"
    """Shown in the sidebar and as the heading."""
    explanation = ""
    """One paragraph under the heading."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """The heading and an empty content layout (:attr:`content`)."""
        super().__init__(parent)
        outer = QVBoxLayout(self)
        heading = QLabel(self.title)
        font = heading.font()
        font.setPointSize(font.pointSize() + 5)
        font.setBold(True)
        heading.setFont(font)
        outer.addWidget(heading)
        if self.explanation:
            text = QLabel(self.explanation)
            text.setWordWrap(True)
            outer.addWidget(text)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #e1e0d9;")
        outer.addWidget(line)
        self.content = QVBoxLayout()
        outer.addLayout(self.content, 1)


class LogBridge(QObject):
    """Forwards the package's log records to a widget (thread-safe, through a signal)."""

    record = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Not attached yet; :meth:`attach` installs the handler."""
        super().__init__(parent)
        self._handler: logging.Handler | None = None

    def attach(self, sink: Callable[[str], None], level: int = logging.INFO) -> None:
        """Send every record of the ``erdr`` logger at ``level`` or above to ``sink``."""
        self.record.connect(sink)
        bridge = self

        class _Handler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                bridge.record.emit(self.format(record))

        handler = _Handler(level)
        handler.setFormatter(
            KeyValueFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
        )
        logger = logging.getLogger("erdr")
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > level:
            logger.setLevel(level)
        self._handler = handler

    def detach(self) -> None:
        """Remove the handler."""
        if self._handler is not None:
            logging.getLogger("erdr").removeHandler(self._handler)
            self._handler = None
