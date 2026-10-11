"""Text formats of the tables: CSV, JSON, Markdown and LaTeX (ADR-012).

CSV and JSON keep every value exactly (floats in their shortest round-trip form); Markdown and
LaTeX show floats with up to :data:`DISPLAY_DECIMALS` decimals, trailing zeros removed, as the
workbook displays them. Every file is UTF-8 with LF line ends; CSV files start with a byte-order
mark so that Excel shows S₁, ρ and ∅ correctly.
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Sequence
from pathlib import Path

from erdr.export.tables import Cell, Table

DISPLAY_DECIMALS = 10
"""Decimals shown in Markdown, LaTeX and HTML (the workbook's 10-decimal rounding)."""

_LATEX_SYMBOLS = {
    "ρ": r"$\rho$",
    "ε": r"$\varepsilon$",
    "∅": r"$\emptyset$",
    "→": r"$\to$",
    "←": r"$\leftarrow$",
    "−": "-",
    "·": r"$\cdot$",
    "≠": r"$\neq$",
    "≥": r"$\geq$",
    "≤": r"$\leq$",
    "∈": r"$\in$",
    "∩": r"$\cap$",
    "Σ": r"$\Sigma$",
    "′": "'",
    "✓": r"$\checkmark$",
    "✗": r"$\times$",
    "—": "---",
    "…": r"\ldots{}",
    "\\": r"$\setminus$",
    "|": r"$|$",
}
_SUBSCRIPTS = dict(zip("₀₁₂₃₄₅₆₇₈₉ᵢⱼₜ", "0123456789ijt", strict=True))
_LATEX_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def display(value: Cell, decimals: int = DISPLAY_DECIMALS) -> str:
    """A cell as shown in a report: floats rounded, integral floats without decimals."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return "—"
        if value.is_integer() and abs(value) < 1e15:
            return str(int(value))
        text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
        return "0" if text in ("-0", "") else text
    return str(value)


def exact(value: Cell) -> str:
    """A cell as written to CSV: every float exactly (its shortest round-trip form)."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def to_csv(table: Table) -> str:
    """The table as CSV text (header row, then the rows; LF line ends)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(table.columns)
    for row in table.rows:
        writer.writerow([exact(v) for v in row])
    return buffer.getvalue()


def table_to_data(table: Table) -> dict[str, object]:
    """The table as plain JSON data."""
    return {
        "key": table.key,
        "title": table.title,
        "sheet": table.sheet,
        "columns": list(table.columns),
        "rows": [list(row) for row in table.rows],
        "note": table.note,
    }


def to_json(tables: Sequence[Table], meta: dict[str, object] | None = None) -> str:
    """Several tables (and optional metadata) as one JSON document."""
    data = {"meta": meta or {}, "tables": [table_to_data(table) for table in tables]}
    return json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False, default=str) + "\n"


def _md_cell(value: Cell) -> str:
    return display(value).replace("|", "\\|").replace("\n", " ")


def to_markdown(table: Table, *, heading_level: int = 2) -> str:
    """The table as a GitHub-flavoured Markdown section (heading, table, note)."""
    lines = [f"{'#' * heading_level} {table.title}", ""]
    lines.append("| " + " | ".join(_md_cell(c) for c in table.columns) + " |")
    lines.append("|" + "|".join("---" for _ in table.columns) + "|")
    for row in table.rows:
        lines.append("| " + " | ".join(_md_cell(v) for v in row) + " |")
    if table.note:
        lines += ["", f"*{table.note}*"]
    return "\n".join(lines) + "\n"


def latex_escape(text: str) -> str:
    """Plain text with the article's symbols as LaTeX (S₁ → S$_{1}$, ρ → rho in math mode)."""
    tokens: list[tuple[bool, str]] = []  # (math mode, content)
    pending: list[str] = []

    def flush() -> None:
        if pending:
            tokens.append((True, "_{" + "".join(pending) + "}"))
            pending.clear()

    for char in text:
        if char in _SUBSCRIPTS:
            pending.append(_SUBSCRIPTS[char])
            continue
        flush()
        symbol = _LATEX_SYMBOLS.get(char)
        if symbol is not None and symbol.startswith("$"):
            tokens.append((True, symbol.strip("$")))
        elif symbol is not None:
            tokens.append((False, symbol))
        elif char in _LATEX_SPECIAL:
            tokens.append((False, _LATEX_SPECIAL[char]))
        elif ord(char) > 127:
            tokens.append((False, "?"))  # anything else outside ASCII would break LaTeX
        else:
            tokens.append((False, char))
    flush()
    out: list[str] = []
    for is_math, content in tokens:  # adjacent math tokens share one $…$
        if is_math and out and out[-1].endswith("$") and out[-1].startswith("$"):
            out[-1] = out[-1][:-1] + content + "$"
        else:
            out.append(f"${content}$" if is_math else content)
    return "".join(out)


def to_latex(table: Table) -> str:
    """The table as a LaTeX ``table`` with a ``tabular`` (booktabs rules, ASCII only)."""
    spec = "l" + "r" * (len(table.columns) - 1)
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{" + latex_escape(table.title) + "}",
        r"\label{tab:erdr-" + table.key + "}",
        r"\begin{tabular}{" + spec + "}",
        r"\toprule",
        " & ".join(latex_escape(c) for c in table.columns) + r" \\",
        r"\midrule",
    ]
    for row in table.rows:
        lines.append(" & ".join(latex_escape(display(v)) for v in row) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    if table.note:
        lines.append(r"\par\smallskip\footnotesize " + latex_escape(table.note))
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str, *, bom: bool = False) -> Path:
    """Write ``text`` as UTF-8 with LF line ends (optionally with a byte-order mark)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\ufeff" if bom else "").encode("utf-8") + text.encode("utf-8"))
    return path
