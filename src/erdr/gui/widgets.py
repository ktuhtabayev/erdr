"""Reusable widgets in the template's style: page frame, titles, warning box, tables, figures.

Tables paint every column header in the colour of what the column holds and every marked cell in
the colour of what it means; :class:`Legend` explains the colours a table uses and :func:`chip`
shows a count or a name in its category's colours (ADR-019).
"""

from __future__ import annotations

import html
import logging
from collections.abc import Callable, Iterable, Sequence

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QShortcut,
)
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
from erdr.export.theme import SWATCHES, legend, meaning
from erdr.gui.models import TableModel
from erdr.log import KeyValueFormatter


def chip(text: str, mark: str, *, bold: bool = True) -> str:
    """Rich text: ``text`` in the tint and the ink of ``mark`` (a count, a name, a legend entry)."""
    found = SWATCHES[mark]
    weight = " font-weight:600;" if bold else ""
    return (
        f"<span style='background-color:{found.fill}; color:{found.ink};{weight}'>"
        f"&nbsp;{html.escape(text)}&nbsp;</span>"
    )


def swatch_icon(colour: str, size: int = 10) -> QIcon:
    """A small square of ``colour`` (the stage of a tab)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(colour))
    return QIcon(pixmap)


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


class Legend(QLabel):
    """What the colours of a table mean: one chip per mark it uses, by section (ADR-019)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty legend (hidden until it has marks)."""
        super().__init__(parent)
        self.setObjectName("legend")
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.marks: list[str] = []
        """The marks shown, in legend order."""
        self.setVisible(False)

    def show_marks(self, marks: Iterable[str | None], class_labels: Sequence[object] = ()) -> None:
        """Explain ``marks``; ``class_labels`` name the classes K1, K2 and so on."""
        sections = legend(marks)
        self.marks = [mark for _, members in sections for mark in members]
        self.setText(
            " &nbsp; ".join(
                f"{html.escape(title)}: "
                + " ".join(chip(meaning(mark, class_labels), mark) for mark in members)
                for title, members in sections
            )
        )
        self.setVisible(bool(sections))

    def show_table(self, table: Table | None, class_labels: Sequence[object] = ()) -> None:
        """Explain the colours of ``table`` (nothing for ``None``)."""
        self.show_marks(table.used_marks() if table is not None else (), class_labels)


class RoleHeader(QHeaderView):
    """A table header that paints a column in the colour of what it holds (the template's)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """A horizontal header; unmarked columns keep the style sheet's look."""
        super().__init__(Qt.Orientation.Horizontal, parent)

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int) -> None:
        """Fill a marked column's header with its tint and write its name in its ink."""
        model = self.model()
        found = model.header_swatch(logicalIndex) if isinstance(model, TableModel) else None
        if found is None or not rect.isValid():
            super().paintSection(painter, rect, logicalIndex)
            return
        painter.save()
        painter.fillRect(rect, QColor(found.fill))
        painter.setPen(self.palette().color(QPalette.ColorRole.Mid))
        painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(found.ink))
        text = str(model.headerData(logicalIndex, Qt.Orientation.Horizontal) or "")
        area = rect.adjusted(8, 0, -8, 0)
        text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, area.width())
        left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(area, int(left), text)
        painter.restore()


class TableView(QTableView):
    """A read-only table of an exporter's :class:`~erdr.export.tables.Table`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """An empty view: alternating rows, row selection, Ctrl+C copies (the template's)."""
        super().__init__(parent)
        self.setHorizontalHeader(RoleHeader(self))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setSortingEnabled(False)  # tables open in the workbook's order
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        QShortcut(QKeySequence.StandardKey.Copy, self, self.copy_selection)

    def show_table(
        self, table: Table, decimals: int = 6, class_labels: Sequence[object] = ()
    ) -> None:
        """Show ``table``; columns are sized to their content (up to a limit).

        ``class_labels`` name the classes K1, K2, … in the tooltips.
        """
        previous = self.model()
        model = TableModel(table, decimals, self, class_labels)  # owned by the view (Qt)
        self.setModel(model)
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
        """Replace the drawing by ``figure``, sized to the canvas when it is on screen.

        A figure set after the canvas is laid out keeps its own size until the next resize;
        it gets the canvas's size at once, as matplotlib's resize handler would give it.
        """
        figure.set_canvas(self.canvas)
        self.canvas.figure = figure
        width, height = self.canvas.width(), self.canvas.height()
        if self.canvas.isVisible() and width > 1 and height > 1:
            ratio = float(self.canvas.device_pixel_ratio)
            figure.set_size_inches(
                width * ratio / figure.dpi, height * ratio / figure.dpi, forward=False
            )
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
