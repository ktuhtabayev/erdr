"""Reusable widgets in the template's style: page frame, titles, warning box, tables, figures."""

from __future__ import annotations

import logging
from collections.abc import Callable

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from erdr.export.tables import Table
from erdr.gui.models import TableModel
from erdr.log import KeyValueFormatter


def page_title(text: str) -> QLabel:
    """The title of a page."""
    label = QLabel(text)
    label.setObjectName("pageTitle")
    return label


def hint(text: str, name: str = "pageHint") -> QLabel:
    """Small secondary text that wraps."""
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


def section_title(text: str) -> QLabel:
    """A heading inside a page."""
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def badge(text: str = "", *, warning: bool = False) -> QLabel:
    """A small rounded label; ``warning`` gives the ⚠ colours."""
    label = QLabel(text)
    label.setObjectName("warningBadge" if warning else "badge")
    label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return label


class WarningBox(QFrame):
    """A ⚠ box: what the user must not miss (a reading that is not the literal article text)."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Create the box; it hides itself while it has no text."""
        super().__init__(parent)
        self.setObjectName("warningBox")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.label)
        self.set_text(text)

    def set_text(self, text: str) -> None:
        """Show ``text``; an empty text hides the box."""
        self.label.setText(text)
        self.setVisible(bool(text))

    def text(self) -> str:
        """The text shown."""
        return self.label.text()


class TableView(QTableView):
    """A read-only table of an exporter's :class:`~erdr.export.tables.Table`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty view: alternating rows, row selection, Ctrl+C copies (the template's)."""
        super().__init__(parent)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setSortingEnabled(False)  # tables open in the workbook's order
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        QShortcut(QKeySequence.StandardKey.Copy, self, self.copy_selection)

    def show_table(self, table: Table, decimals: int = 6) -> None:
        """Show ``table``; columns are sized to their content (up to a limit)."""
        previous = self.model()
        self.setModel(TableModel(table, decimals, self))  # owned by the view (Qt), not by Python
        if previous is not None:
            previous.deleteLater()
        self.resizeColumnsToContents()
        for column in range(len(table.columns)):
            if self.columnWidth(column) > 340:
                self.setColumnWidth(column, 340)
        self.setToolTip(table.note)

    def copy_selection(self) -> str:
        """Copy the selected cells as tab-separated text (for Excel); returns the text."""
        model = self.model()
        indexes = sorted(self.selectedIndexes(), key=lambda i: (i.row(), i.column()))
        if model is None or not indexes:
            return ""
        rows: dict[int, dict[int, str]] = {}
        for index in indexes:
            rows.setdefault(index.row(), {})[index.column()] = str(model.data(index) or "")
        columns = sorted({c for row in rows.values() for c in row})
        text = "\n".join("\t".join(rows[r].get(c, "") for c in columns) for r in sorted(rows))
        QGuiApplication.clipboard().setText(text)
        return text


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
    """A page of the workflow: a title, a hint and its content (the template's layout)."""

    title = "Page"
    """Shown in the sidebar and as the heading."""
    explanation = ""
    """The hint under the heading."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the title row and the hint; subclasses add to :attr:`content`."""
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 12)
        outer.setSpacing(8)
        self.header = QHBoxLayout()
        self.header.addWidget(page_title(self.title))
        self.header.addStretch(1)
        outer.addLayout(self.header)
        if self.explanation:
            outer.addWidget(hint(self.explanation))
        self.content = QVBoxLayout()
        self.content.setSpacing(8)
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
