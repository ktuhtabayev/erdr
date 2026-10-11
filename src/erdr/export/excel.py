"""The run as an Excel workbook laid out like the ERDR workbook (ADR-012).

Tables that mirror the same sheet of the ERDR workbook are stacked on one sheet, in workbook
order (*Overview*, *Dataset*, *Normalized Dataset*, *Zhuravlev Distances*, …); the figures go to
*Charts*. Values are written exactly (no rounding); the marks of the cells become fills.
"""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
from pathlib import Path

from matplotlib.figure import Figure
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from erdr import __version__
from erdr.export.tables import Table

TITLE_FILL = PatternFill("solid", fgColor="0D366B")
HEADER_FILL = PatternFill("solid", fgColor="E1E0D9")
MARK_FILLS = {
    "D": "CDE2FB",
    "F": "FBE0D3",
    "selected": "FFF0C2",
    "L": "D1F0E4",
    "moved": "B7D3F6",
    "decreased": "E0DCF7",
    "own": "EEF5FD",
    "enemy": "FBDADA",
    "tie-r": "FFF0C2",
    "tie-index": "DCEBFB",
    "literal": "FFF0C2",
    "yes": "D1F0E4",
    "no": "F0EFEC",
}
"""Cell fill per mark (light tints; the legend is on the *Overview* sheet)."""
MARK_LEGEND = {
    "D": "training sample D",
    "F": "validation sample F",
    "selected": "selected object Sᵢ / tie decided by r",
    "L": "member of L",
    "moved": "moved to D",
    "decreased": "counter decreased by Step 5",
    "own": "own class inside the enemy sphere / same class",
    "enemy": "enemy (other class)",
    "tie-index": "tie decided by the index",
    "literal": "the literal article reading",
    "yes": "case occurs",
    "no": "case does not occur",
}
_WIDTH_LIMIT = 60


def _sheet_name(name: str, taken: set[str]) -> str:
    base = "".join("_" if ch in "[]:*?/\\" else ch for ch in name)[:31] or "Sheet"
    candidate, counter = base, 2
    while candidate in taken:
        suffix = f" ({counter})"
        candidate = base[: 31 - len(suffix)] + suffix
        counter += 1
    taken.add(candidate)
    return candidate


def _write_table(ws: Worksheet, table: Table, top: int) -> int:
    """Write ``table`` from row ``top``; returns the first free row after it."""
    width = len(table.columns)
    title = ws.cell(row=top, column=1, value=table.title)
    title.font = Font(bold=True, color="FFFFFF")
    for column in range(1, width + 1):
        ws.cell(row=top, column=column).fill = TITLE_FILL
    for column, name in enumerate(table.columns, start=1):
        cell = ws.cell(row=top + 1, column=column, value=name)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for r, row in enumerate(table.rows):
        for c, value in enumerate(row):
            cell = ws.cell(row=top + 2 + r, column=c + 1, value=value)
            mark = table.mark(r, c)
            if mark in MARK_FILLS:
                cell.fill = PatternFill("solid", fgColor=MARK_FILLS[mark])
        ws.cell(row=top + 2 + r, column=1).font = Font(bold=True)
    end = top + 2 + len(table.rows)
    if table.note:
        ws.cell(row=end, column=1, value=table.note).font = Font(italic=True, color="52514E")
        end += 1
    return end + 1


def _fit_columns(ws: Worksheet) -> None:
    widths: dict[int, int] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None or cell.row == 1:
                continue
            text = str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), min(len(text), _WIDTH_LIMIT))
    for column, width in widths.items():
        ws.column_dimensions[get_column_letter(column)].width = max(8, width + 2)


def write_workbook(
    path: Path,
    tables: Sequence[Table],
    *,
    title: str,
    settings: Sequence[tuple[str, str]] = (),
    figures: Sequence[tuple[str, Figure]] = (),
) -> Path:
    """Write the tables (stacked per workbook sheet), the settings and the figures.

    Args:
        path: The ``.xlsx`` file.
        tables: The tables; those with the same :attr:`Table.sheet` share a sheet.
        title: The title on the *Overview* sheet.
        settings: (name, value) pairs shown on the *Overview* sheet.
        figures: (name, figure) pairs placed on the *Charts* sheet.
    """
    workbook = Workbook()
    overview = workbook.active
    assert overview is not None  # a new workbook always has its first sheet
    overview.title = "Overview"
    overview.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
    overview.cell(row=2, column=1, value=f"Written by erdr {__version__}").font = Font(
        italic=True, color="52514E"
    )
    row = 4
    for name, value in settings:
        overview.cell(row=row, column=1, value=name).font = Font(bold=True)
        overview.cell(row=row, column=2, value=value)
        row += 1
    row += 1
    taken = {"Overview"}
    sheets: dict[str, list[Table]] = {}
    for table in tables:
        sheets.setdefault(table.sheet or table.key, []).append(table)
    for table in sheets.pop("Overview", []):
        row = _write_table(overview, table, row)
    overview.cell(row=row, column=1, value="Colour legend").font = Font(bold=True)
    for mark, meaning in MARK_LEGEND.items():
        row += 1
        cell = overview.cell(row=row, column=1, value=meaning)
        cell.fill = PatternFill("solid", fgColor=MARK_FILLS[mark])
    _fit_columns(overview)

    for name, group in sheets.items():
        ws = workbook.create_sheet(_sheet_name(name, taken))
        top = 1
        for table in group:
            top = _write_table(ws, table, top)
        if len(group) == 1:
            ws.freeze_panes = ws.cell(row=3, column=2)
        _fit_columns(ws)

    if figures:
        charts = workbook.create_sheet(_sheet_name("Charts", taken))
        top = 1
        for name, figure in figures:
            charts.cell(row=top, column=1, value=name).font = Font(bold=True)
            buffer = BytesIO()
            figure.savefig(buffer, format="png", dpi=110)
            buffer.seek(0)
            image = Image(buffer)
            charts.add_image(image, f"A{top + 1}")
            top += int(image.height / 20) + 3
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path
