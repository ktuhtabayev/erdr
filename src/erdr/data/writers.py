"""Writing datasets in the author's extended layout — the training and validation samples of ERDR.

The files follow the conventions of the author's dataset files byte for byte (ADR-007):

``.csv``
    comma-separated, CRLF line ends; the first row ``m,n,c`` padded with empty cells to n + 1
    columns; integral values without a decimal point (``70``), others in the shortest form
    (``2.4``); the type row ends with an empty cell under the class column.
``.dat``
    space-separated, LF line ends; the first row ``m n c``; every feature value as a decimal
    (``70.0``, ``2.4``), the class label as it is; the type row with n flags.

Nominal categories read as text are written as their codes (the layout has no names).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from erdr.data.schema import Dataset
from erdr.errors import DatasetError

EXTENDED_SUFFIXES = (".csv", ".dat")
"""The file types of the extended layout."""


def _csv_number(value: float) -> str:
    """``70.0`` → ``70``, ``2.4`` → ``2.4`` (the author's .csv files)."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _dat_number(value: float) -> str:
    """``70`` → ``70.0``, ``2.4`` → ``2.4`` (the author's .dat files)."""
    return repr(float(value))


def _label(value: object, forbidden: str, where: str) -> str:
    text = str(value.item() if isinstance(value, np.generic) else value)
    if any(char in text for char in forbidden) or not text:
        raise DatasetError(f"{where}: the class label {text!r} cannot be written in this format")
    return text


def extended_text(dataset: Dataset, suffix: str) -> str:
    """The content of an extended-layout file (``.csv`` or ``.dat``) for ``dataset``.

    Raises:
        DatasetError: Unknown suffix, a non-finite value, or a label the format cannot hold.
    """
    kind = suffix.lower()
    if kind not in EXTENDED_SUFFIXES:
        raise DatasetError(f"the extended layout is written as .csv or .dat, not {suffix!r}")
    if not np.all(np.isfinite(dataset.X)):
        raise DatasetError(f"{dataset.name}: only finite values can be written")
    m, n, c = dataset.m, dataset.n, len(dataset.classes)
    flags = [str(flag) for flag in dataset.type_flags]
    if kind == ".csv":
        header = [str(m), str(n), str(c)] + [""] * max(n + 1 - 3, 0)
        lines = [",".join(header)]
        for row, label in zip(dataset.X, dataset.y, strict=True):
            cells = [_csv_number(v) for v in row] + [_label(label, ",\r\n", dataset.name)]
            lines.append(",".join(cells))
        lines.append(",".join([*flags, ""]))
        return "\r\n".join(lines) + "\r\n"
    lines = [f"{m} {n} {c}"]
    for row, label in zip(dataset.X, dataset.y, strict=True):
        cells = [_dat_number(v) for v in row] + [_label(label, " \t\r\n", dataset.name)]
        lines.append(" ".join(cells))
    lines.append(" ".join(flags))
    return "\n".join(lines) + "\n"


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
