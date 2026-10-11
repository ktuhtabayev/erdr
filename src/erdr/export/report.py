"""The run report: one self-contained HTML file with the settings, the figures and the tables.

The figures are inline SVG and the styles are in the file, so the report opens anywhere without
other files; a figure that belongs to a sheet (the hypersphere figures) stands right before that
sheet's tables, the others at the top. Cells and column headers take the colours of their marks
(:mod:`erdr.export.theme`), with the meaning as a tooltip, and the colour legend explains the marks
the report uses. Matrix tables (m × m) of samples larger than
:data:`~erdr.export.tables.MATRIX_LIMIT` objects are left out — they stay in the CSV, JSON and
Excel exports.
"""

from __future__ import annotations

import html
from collections.abc import Sequence

from matplotlib.figure import Figure

from erdr import __version__
from erdr.export.figures import svg_text
from erdr.export.tables import MATRIX_LIMIT, Table
from erdr.export.text import display
from erdr.export.theme import CHECKS, SWATCHES, legend, meaning, swatch

_CSS = """
:root { --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
        --grid:#e1e0d9; --title:#0d366b; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 36px 0 8px; }
.sub { color: var(--ink2); margin: 0 0 20px; }
.notes { border-left: 3px solid var(--warning-edge); background: var(--warning-fill);
         color: var(--warning-ink); padding: 8px 12px; margin: 12px 0; }
.settings { display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; }
.settings dt { color: var(--parameter-ink); font-weight: 600; } .settings dd { margin: 0; }
figure { margin: 16px 0; background: var(--surface); border: 1px solid var(--grid);
         border-radius: 8px; padding: 8px; overflow-x: auto; }
figure svg { max-width: 100%; height: auto; display: block; }
.table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--grid);
              border-radius: 8px; }
table { border-collapse: collapse; font-size: 12.5px; font-variant-numeric: tabular-nums; }
th, td { padding: 4px 8px; border-bottom: 1px solid var(--grid); text-align: right;
         white-space: nowrap; }
th { background: #f0efec; color: var(--ink2); font-weight: 600; position: sticky; top: 0; }
td:first-child, th:first-child { text-align: left; font-weight: 600; }
td.text { text-align: left; white-space: normal; min-width: 12em; }
.note { color: var(--ink2); font-style: italic; margin: 6px 0 0; }
.legend { margin: 4px 0; }
.legend b { color: var(--ink2); font-weight: 600; margin-right: 4px; }
.legend span { display: inline-block; padding: 1px 8px; margin: 2px 4px 2px 0; border-radius: 4px;
               font-weight: 600; }
footer { margin-top: 48px; color: var(--muted); font-size: 12px; }
"""


def mark_css() -> str:
    """One rule per mark: the tint and the ink of :mod:`erdr.export.theme`."""
    warning = CHECKS["warning"]
    root = (
        f":root {{ --warning-fill:{warning.fill}; --warning-ink:{warning.ink}; "
        f"--warning-edge:{warning.accent}; --parameter-ink:{SWATCHES['parameter'].ink}; }}"
    )
    rules = [root]
    rules += [
        f".m-{mark} {{ background:{found.fill}; color:{found.ink}; }}"
        for mark, found in SWATCHES.items()
    ]
    return "\n".join(rules) + "\n"


def _attributes(mark: str | None, *classes: str) -> str:
    """``class`` (the mark and ``classes``) and ``title`` (the mark's meaning) of a cell."""
    names = [f"m-{mark}"] if mark is not None and swatch(mark) is not None else []
    names += [name for name in classes if name]
    attribute = f' class="{" ".join(names)}"' if names else ""
    if mark is not None and swatch(mark) is not None:
        attribute += f' title="{html.escape(meaning(mark))}"'
    return attribute


def _cell(value: object, mark: str | None) -> str:
    text = display(value)  # type: ignore[arg-type]
    wide = "text" if isinstance(value, str) and len(value) > 24 else ""
    return f"<td{_attributes(mark, wide)}>{html.escape(text)}</td>"


def legend_html(tables: Sequence[Table], class_labels: Sequence[object] = ()) -> str:
    """The colour legend of the marks the tables use, one line per section."""
    used: set[str] = set().union(*(table.used_marks() for table in tables))
    lines = []
    for section, marks in legend(used):
        chips = "".join(
            f'<span class="m-{mark}">{html.escape(meaning(mark, class_labels))}</span>'
            for mark in marks
        )
        lines.append(f'<p class="legend"><b>{html.escape(section)}</b>{chips}</p>')
    return "".join(lines)


def figure_html(name: str, figure: Figure) -> str:
    """One figure as inline SVG."""
    return f'<figure aria-label="{html.escape(name)}">{svg_text(figure)}</figure>'


def table_html(table: Table) -> str:
    """One table as an HTML section."""
    head = "".join(
        f"<th{_attributes(table.header_mark(c))}>{html.escape(name)}</th>"
        for c, name in enumerate(table.columns)
    )
    body = "".join(
        "<tr>" + "".join(_cell(v, table.mark(r, c)) for c, v in enumerate(row)) + "</tr>"
        for r, row in enumerate(table.rows)
    )
    note = f'<p class="note">{html.escape(table.note)}</p>' if table.note else ""
    return (
        f'<section id="{html.escape(table.key)}"><h2>{html.escape(table.title)}</h2>'
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>{note}</section>"
    )


def report_html(
    *,
    title: str,
    subtitle: str,
    settings: Sequence[tuple[str, str]],
    notes: Sequence[str],
    tables: Sequence[Table],
    figures: Sequence[tuple[str, Figure] | tuple[str, Figure, str]],
    m: int,
    footer: str = "",
    class_labels: Sequence[object] = (),
) -> str:
    """The complete HTML document."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title><style>{_CSS}{mark_css()}</style></head><body><main>",
        f'<h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p>',
    ]
    if notes:
        items = "".join(f"<li>{html.escape(n)}</li>" for n in notes)
        parts.append(
            '<div class="notes"><strong>Not the literal article reading:</strong>'
            f"<ul>{items}</ul></div>"
        )
    parts.append('<dl class="settings">')
    for name, value in settings:
        parts.append(f"<dt>{html.escape(name)}</dt><dd>{html.escape(value)}</dd>")
    parts.append("</dl>")
    parts.append(legend_html(tables, class_labels))
    sheets = {table.sheet for table in tables}
    placed: dict[str, list[tuple[str, Figure]]] = {}
    for item in figures:
        sheet = item[2] if len(item) == 3 else None
        if sheet is not None and sheet in sheets:
            placed.setdefault(sheet, []).append((item[0], item[1]))
        else:
            parts.append(figure_html(item[0], item[1]))
    skipped = []
    for table in tables:
        for name, figure in placed.pop(table.sheet, []):  # a sheet's figures before its tables
            parts.append(figure_html(name, figure))
        if table.matrix and m > MATRIX_LIMIT:
            skipped.append(table.title)
            continue
        parts.append(table_html(table))
    if skipped:
        parts.append(
            '<p class="note">Left out here for a sample of '
            f"{m} objects (see the CSV, JSON and Excel exports): "
            + html.escape("; ".join(skipped))
            + "</p>"
        )
    parts.append(
        f"<footer>erdr {__version__} · {html.escape(footer)}</footer></main></body></html>"
    )
    return "\n".join(parts) + "\n"
