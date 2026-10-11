"""Qt models over the exporters' plain tables, with the cell and header marks as colours.

What a cell or a column means is the table's *mark*; :mod:`erdr.export.theme` turns it into the
same colours the Excel workbook, the HTML report and the figures use (ADR-019).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from erdr.export.tables import Table
from erdr.export.text import display
from erdr.export.theme import Swatch, meaning, swatch

Index = QModelIndex | QPersistentModelIndex


class TableModel(QAbstractTableModel):
    """A read-only view of a :class:`~erdr.export.tables.Table`."""

    def __init__(
        self,
        table: Table,
        decimals: int = 6,
        parent: QObject | None = None,
        class_labels: Sequence[object] = (),
    ) -> None:
        """Show ``table`` with floats rounded to ``decimals`` (the tooltip shows every digit).

        Give the view as ``parent``: Qt then owns the model together with its view, so the
        model cannot be freed while the view still shows it. ``class_labels`` name the classes
        K1, K2, … in the tooltips.
        """
        super().__init__(parent)
        self.table = table
        self.decimals = decimals
        self.class_labels = tuple(class_labels)
        self._bold = QFont()
        self._bold.setBold(True)

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008 - Qt's signature
        """Number of rows."""
        return 0 if parent.isValid() else len(self.table.rows)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008 - Qt's signature
        """Number of columns."""
        return 0 if parent.isValid() else len(self.table.columns)

    def header_swatch(self, column: int) -> Swatch | None:
        """The colours of a column header (what kind of quantity the column holds)."""
        return swatch(self.table.header_mark(column))

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Text, alignment, colour and tooltip of a cell."""
        if not index.isValid():
            return None
        value = self.table.rows[index.row()][index.column()]
        mark = self.table.mark(index.row(), index.column())
        colours = swatch(mark)
        if role == Qt.ItemDataRole.DisplayRole:
            return display(value, self.decimals)
        if role == Qt.ItemDataRole.ToolTipRole:
            parts = [display(value)]
            if mark is not None and colours is not None:
                parts.append(meaning(mark, self.class_labels))
            return " · ".join(p for p in parts if p)
        if role == Qt.ItemDataRole.BackgroundRole and colours is not None:
            return QBrush(QColor(colours.fill))
        if role == Qt.ItemDataRole.ForegroundRole and colours is not None:
            return QBrush(QColor(colours.ink))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = isinstance(value, int | float) and not isinstance(value, bool)
            horizontal = Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
            return int(horizontal | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole and index.column() == 0:
            return self._bold
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Column titles with what their colour means; rows are numbered."""
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1) if role == Qt.ItemDataRole.DisplayRole else None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.table.columns[section]
        if role == Qt.ItemDataRole.ToolTipRole:
            mark = self.table.header_mark(section)
            lines = [self.table.columns[section]]
            if mark is not None and swatch(mark) is not None:
                lines.append(meaning(mark, self.class_labels))
            return "\n".join(lines)
        return None
