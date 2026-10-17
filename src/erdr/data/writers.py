"""Writing datasets in the author's extended layout — the training and validation samples of ERDR.

The files follow the conventions of the author's dataset files byte for byte (ADR-007):

``.csv``
    comma-separated, CRLF line ends; the first row ``m,n,c`` padded with empty cells to n + 1
    columns; integral values without a decimal point (``70``), others in the shortest form
    (``2.4``, ``0.00003`` — never an exponent); the type row ends with an empty cell under the
    class column.
``.dat``
    space-separated, LF line ends; the first row ``m n c``; every feature value as a decimal
    (``70.0``, ``2.4``, ``0.00003``), the class label as it is; the type row with n flags.

Nominal categories read as text are written as their codes (the layout has no names).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np

from erdr.data.schema import Dataset
from erdr.errors import DatasetError

EXTENDED_SUFFIXES = (".csv", ".dat")
"""The file types of the extended layout."""
LINE_ENDS = {".csv": "\r\n", ".dat": "\n"}
"""The line end of each file type."""


def _decimal(value: float) -> str:
    """The shortest digits that read back as ``value``, never in exponent form (``0.00003``)."""
    return np.format_float_positional(float(value), unique=True, trim="0")


def _csv_number(value: float) -> str:
    """``70.0`` → ``70``, ``2.4`` → ``2.4``, ``3e-05`` → ``0.00003`` (the author's .csv files)."""
    return str(int(value)) if float(value).is_integer() else _decimal(value)


def _dat_number(value: float) -> str:
    """``70`` → ``70.0``, ``2.4`` → ``2.4``, ``3e-05`` → ``0.00003`` (the author's .dat files)."""
    return _decimal(value)


def _label(value: object, forbidden: str, where: str) -> str:
    text = str(value.item() if isinstance(value, np.generic) else value)
    if any(char in text for char in forbidden) or not text:
        raise DatasetError(f"{where}: the class label {text!r} cannot be written in this format")
    return text


def extended_lines(dataset: Dataset, suffix: str) -> Iterator[str]:
    """The lines of an extended-layout file (``.csv`` or ``.dat``) for ``dataset``, no line ends.

    Raises:
        DatasetError: Unknown suffix or a non-finite value; a label the format cannot hold
            when its line is reached.
    """
    kind = suffix.lower()
    if kind not in EXTENDED_SUFFIXES:
        raise DatasetError(f"the extended layout is written as .csv or .dat, not {suffix!r}")
    if not np.all(np.isfinite(dataset.X)):
        raise DatasetError(f"{dataset.name}: only finite values can be written")
    return _lines(dataset, kind)


def _lines(dataset: Dataset, kind: str) -> Iterator[str]:
    m, n, c = dataset.m, dataset.n, len(dataset.classes)
    flags = [str(flag) for flag in dataset.type_flags]
    if kind == ".csv":
        yield ",".join([str(m), str(n), str(c)] + [""] * max(n + 1 - 3, 0))
        for row, label in zip(dataset.X, dataset.y, strict=True):
            cells = [_csv_number(v) for v in row] + [_label(label, ",\r\n", dataset.name)]
            yield ",".join(cells)
        yield ",".join([*flags, ""])
        return
    yield f"{m} {n} {c}"
    for row, label in zip(dataset.X, dataset.y, strict=True):
        cells = [_dat_number(v) for v in row] + [_label(label, " \t\r\n", dataset.name)]
        yield " ".join(cells)
    yield " ".join(flags)


def extended_text(dataset: Dataset, suffix: str) -> str:
    """The content of an extended-layout file (``.csv`` or ``.dat``) for ``dataset``.

    Raises:
        DatasetError: Unknown suffix, a non-finite value, or a label the format cannot hold.
    """
    lines = extended_lines(dataset, suffix)
    end = LINE_ENDS[suffix.lower()]
    return "".join(line + end for line in lines)


def convention_problem(path: Path, dataset: Dataset) -> str:
    """How the file ``path`` of ``dataset`` departs from the author's conventions, or ``""``.

    The file is compared line by line with what :func:`write_extended` writes for its data, so a
    file of any size is checked without holding its text in memory (ADR-021).
    """
    kind = path.suffix.lower()
    try:
        end = LINE_ENDS[kind].encode()
        with path.open("rb") as handle:
            for number, line in enumerate(extended_lines(dataset, kind), start=1):
                expected = line.encode("utf-8") + end
                actual = handle.readline()
                if actual != expected:
                    return f"{path.name}, line {number}: {_difference(actual, expected, kind)}"
            if handle.read(1):
                return f"{path.name}: text after the type row"
    except (OSError, KeyError, DatasetError) as error:
        return f"{path.name}: cannot be compared with the conventions ({error})"
    return ""


def _difference(actual: bytes, expected: bytes, kind: str) -> str:
    """What makes the line ``actual`` differ from the line the conventions write."""
    end = "CRLF" if kind == ".csv" else "LF"
    if not actual:
        return "the file ends before the type row"
    if not actual.endswith(b"\n"):
        return f"the line must end with {end}"
    got = actual.rstrip(b"\r\n").decode("utf-8", "replace")
    want = expected.rstrip(b"\r\n").decode("utf-8")
    if got == want:
        return f"{kind} lines end with {end}"
    separator = "," if kind == ".csv" else " "
    got_cells, want_cells = got.split(separator), want.split(separator)
    for index, (a, b) in enumerate(zip(got_cells, want_cells, strict=False)):
        if a != b:
            return f"cell {index + 1} is {a!r}; the {kind} conventions write {b!r}"
    return f"{len(got_cells)} cells; the {kind} conventions write {len(want_cells)}"


def write_extended(dataset: Dataset, path: Path, *, overwrite: bool = True) -> Path:
    """Write ``dataset`` to ``path`` (``.csv`` or ``.dat``) in the extended layout.

    Raises:
        DatasetError: The file exists and ``overwrite`` is false, or the dataset cannot be written.
    """
    if path.exists() and not overwrite:
        raise DatasetError(f"{path} already exists")
    text = extended_text(dataset, path.suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def shape_name(name: str, dataset: Dataset) -> str:
    """``Heart-Disease (7, 13, 2)`` for a dataset of that shape — the author's file naming.

    A trailing ``(m, n, c)`` already in ``name`` is replaced.
    """
    base = name.rsplit(" (", 1)[0] if name.endswith(")") and " (" in name else name
    return f"{base} ({dataset.m}, {dataset.n}, {len(dataset.classes)})"
