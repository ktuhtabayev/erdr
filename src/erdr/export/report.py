"""The run report: one self-contained HTML file with the settings, the figures and the tables.

The figures are inline SVG and the styles are in the file, so the report opens anywhere without
other files. Matrix tables (m × m) of samples larger than
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

_CSS = """
:root { --surface:#fcfcfb; --page:#f9f9f7; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
        --grid:#e1e0d9; --title:#0d366b; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
       font: 14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 17px; margin: 36px 0 8px; }
.sub { color: var(--ink2); margin: 0 0 20px; }
.notes { border-left: 3px solid #eda100; background: #fff8e6; padding: 8px 12px; margin: 12px 0; }
.settings { display: grid; grid-template-columns: max-content 1fr; gap: 2px 16px; }
.settings dt { color: var(--ink2); } .settings dd { margin: 0; }
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
.legend span { display: inline-block; padding: 1px 8px; margin: 2px 4px 2px 0; border-radius: 4px; }
.m-D { background: #cde2fb; } .m-F { background: #fbe0d3; }
.m-selected { background: #fff0c2; } .m-L { background: #d1f0e4; }
.m-moved { background: #b7d3f6; } .m-decreased { background: #e0dcf7; }
.m-own { background: #eef5fd; } .m-enemy { background: #fbdada; } .m-tie-r { background: #fff0c2; }
.m-tie-index { background: #dcebfb; } .m-literal { background: #fff0c2; }
.m-yes { background: #d1f0e4; } .m-no { background: #f0efec; }
footer { margin-top: 48px; color: var(--muted); font-size: 12px; }
"""
_LEGEND = (
    ("D", "training sample D"),
    ("F", "validation sample F"),
    ("selected", "selected Sᵢ"),
    ("decreased", "counter decreased"),
    ("moved", "moved to D"),
    ("own", "same class / inside the enemy sphere"),
    ("enemy", "enemy"),
    ("tie-index", "tie decided by the index"),
)


def _cell(value: object, mark: str | None) -> str:
    text = display(value)  # type: ignore[arg-type]
    classes = []
    if mark:
        classes.append(f"m-{mark}")
    if isinstance(value, str) and len(value) > 24:
        classes.append("text")
    attribute = f' class="{" ".join(classes)}"' if classes else ""
    return f"<td{attribute}>{html.escape(text)}</td>"


def table_html(table: Table) -> str:
    """One table as an HTML section."""
    head = "".join(f"<th>{html.escape(c)}</th>" for c in table.columns)
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
    figures: Sequence[tuple[str, Figure]],
    m: int,
    footer: str = "",
) -> str:
    """The complete HTML document."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body><main>",
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
    legend = "".join(f'<span class="m-{k}">{html.escape(v)}</span>' for k, v in _LEGEND)
    parts.append(f'<p class="legend">{legend}</p>')
    for name, figure in figures:
        parts.append(f'<figure aria-label="{html.escape(name)}">{svg_text(figure)}</figure>')
    skipped = []
    for table in tables:
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
