"""Qt models over the exporters' plain tables, with the cell marks as colours."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from erdr.export.tables import Table
from erdr.export.text import display

MARK_COLOURS = {
    "D": "#cde2fb",
    "F": "#fbe0d3",
    "selected": "#fff0c2",
    "L": "#d1f0e4",
    "moved": "#b7d3f6",
    "decreased": "#e0dcf7",
    "own": "#eef5fd",
    "enemy": "#fbdada",
    "tie-r": "#fff0c2",
    "tie-index": "#dcebfb",
    "literal": "#fff0c2",
    "yes": "#d1f0e4",
    "no": "#f0efec",
}
"""Background per mark — the same tints as the Excel workbook and the HTML report."""
MARK_MEANINGS = {
    "D": "training sample D",
    "F": "validation sample F",
    "selected": "the selected object Sᵢ",
    "L": "member of L",
    "moved": "moved to D in this iteration",
    "decreased": "counter decreased by Step 5",
    "own": "same class / inside the enemy sphere",
    "enemy": "enemy (other class)",
    "tie-r": "order decided by r (equal d)",
    "tie-index": "order decided by the index (equal d and r)",
    "literal": "the literal article reading",
    "yes": "the case occurs",
    "no": "the case does not occur",
}
"""Tooltip per mark."""

Index = QModelIndex | QPersistentModelIndex


class TableModel(QAbstractTableModel):
    """A read-only view of a :class:`~erdr.export.tables.Table`."""

    def __init__(self, table: Table, decimals: int = 6, parent: QObject | None = None) -> None:
        """Show ``table`` with floats rounded to ``decimals`` (the tooltip shows every digit).

        Give the view as ``parent``: Qt then owns the model together with its view, so the
        model cannot be freed while the view still shows it.
        """
        super().__init__(parent)
        self.table = table
        self.decimals = decimals

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008 - Qt's signature
        """Number of rows."""
        return 0 if parent.isValid() else len(self.table.rows)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008 - Qt's signature
        """Number of columns."""
        return 0 if parent.isValid() else len(self.table.columns)

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Text, alignment, colour and tooltip of a cell."""
        if not index.isValid():
            return None
        value = self.table.rows[index.row()][index.column()]
        mark = self.table.mark(index.row(), index.column())
        if role == Qt.ItemDataRole.DisplayRole:
            return display(value, self.decimals)
        if role == Qt.ItemDataRole.ToolTipRole:
            parts = [display(value)]
            if mark in MARK_MEANINGS:
                parts.append(MARK_MEANINGS[mark])
            return " · ".join(p for p in parts if p)
        if role == Qt.ItemDataRole.BackgroundRole and mark in MARK_COLOURS:
            return QBrush(QColor(MARK_COLOURS[mark]))
        if role == Qt.ItemDataRole.ForegroundRole and mark in MARK_COLOURS:
            return QBrush(QColor("#0b0b0b"))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = isinstance(value, int | float) and not isinstance(value, bool)
            horizontal = Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft
            return int(horizontal | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole and index.column() == 0:
            font = QFont()
            font.setBold(True)
            return font
        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """Column titles; rows are numbered."""
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.table.columns[section]
        return str(section + 1)
