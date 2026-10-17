"""The project's dataset folder: discovery, identity checks and name resolution (ADR-007).

Layout (the author's, ADR-007 and ADR-021)::

    datasets/
      default.dat, default.csv          the default dataset: Heart-Disease (7, 13, 2)
      Quantitative/<Family>/<Name (m, n, c)>.dat|.csv
                                        datasets whose features are all quantitative,
      Nominal/<Family>/…                all nominal,
      Heterogeneous/<Family>/…          or both, e.g.
                                        Heterogeneous/Heart-Disease/Heart-Disease (270, 13, 2).dat
      <Family>/<Name (m, n, c)>.dat|.csv
                                        a family folder outside the type folders is read too
      synthetic/                        reserved for pre-existing synthetic datasets — not read

Every file is in the extended layout (:func:`~erdr.data.loaders.load_extended_layout`): a first
row ``m n c``; m rows of n feature values and the class label; a last row of n type flags,
1 = quantitative (set I), 0 = nominal (set J). ``.dat`` is whitespace-separated, ``.csv``
comma-separated; the files are kept byte for byte.

The ``.dat`` and ``.csv`` files of one stem are the same dataset in two formats: the ``.dat`` is
read, and :meth:`DatasetCatalog.check` verifies that both hold identical data, that the header's
(m, n, c) matches the file name, that the feature types match the type folder and that every
file is written in the author's conventions byte for byte. A new dataset is added by dropping
its files into a family folder of its type — nothing has to be registered.

Datasets are named by id (``heart-disease-270``), by display name (``Heart-Disease (270, 13, 2)``),
by ``default`` or by a file path. Without a ``datasets`` folder the package's built-in copies are
used, so an installed GUI or the Windows executable still has its datasets.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from erdr.data.loaders import LoadOptions, load_extended_layout
from erdr.data.schema import Dataset, DatasetType
from erdr.data.writers import convention_problem
from erdr.errors import DatasetError
from erdr.notation import feature_name

logger = logging.getLogger(__name__)

DATASETS_DIR = "datasets"
"""Name of the project's dataset folder."""
DEFAULT_STEM = "default"
"""Stem of the default dataset's files at the root of the folder."""
RESERVED_DIRS = ("synthetic",)
"""Sub-folders that are not read (pre-existing synthetic datasets)."""
EXTENSIONS = (".dat", ".csv")
"""File formats of the catalogue, in order of preference."""
DEFAULT_ID = "default"
ENVIRONMENT_VARIABLE = "ERDR_DATASETS"
"""Overrides the dataset folder."""

_SHAPE = re.compile(r"^(?P<name>.*?)\s*\((?P<m>\d+),\s*(?P<n>\d+),\s*(?P<c>\d+)\)$")


def _slug(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower()))


def file_sha256(path: Path) -> str:
    """SHA-256 of a file's bytes (the files are stored byte for byte)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class CatalogEntry:
    """One dataset of the folder: the same data in one or more formats."""

    id: str
    """``default`` or ``<name>-<m>`` (``-<n>`` added when two datasets would share an id)."""
    name: str
    """Display name: the file stem, e.g. ``Heart-Disease (270, 13, 2)`` (``default``)."""
    files: tuple[Path, ...]
    """The files, ``.dat`` first."""
    family: str
    """``default`` or the family folder (``Heart-Disease``)."""
    shape: tuple[int, int, int] | None
    """(m, n, c) from the file name (the default dataset: from its first row)."""
    dataset_type: DatasetType | None = None
    """The type folder the dataset is in (``Heterogeneous/…``), ``None`` outside them."""

    @property
    def path(self) -> Path:
        """The file that is read (the ``.dat`` if there is one)."""
        return self.files[0]

    @property
    def formats(self) -> tuple[str, ...]:
        """The extensions present, e.g. ``(".dat", ".csv")``."""
        return tuple(f.suffix.lower() for f in self.files)

    @property
    def size(self) -> int:
        """Bytes of the file that is read."""
        return self.path.stat().st_size

    @property
    def label(self) -> str:
        """``default — Heart-Disease (7, 13, 2)`` style text for lists."""
        if self.family == DEFAULT_ID and self.shape is not None:
            return f"default ({self.shape[0]}, {self.shape[1]}, {self.shape[2]})"
        return self.name

    def load(self) -> Dataset:
        """Read the dataset from its preferred file (the default is named by its shape)."""
        return load_extended(self.path, self.label)


@dataclass(frozen=True)
class EntryCheck:
    """The result of :meth:`DatasetCatalog.check` for one entry."""

    entry: CatalogEntry
    shape: tuple[int, int, int] | None
    """(m, n, c) as loaded."""
    content_hash: str | None
    """Hash of the data (values, types, labels) of the preferred file."""
    dataset_type: DatasetType | None = None
    """The type of the data as loaded (from the feature types)."""
    sha256: dict[str, str] = field(default_factory=dict)
    """SHA-256 of every file, by extension."""
    problems: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """No problem found."""
        return not self.problems


def read_shape(path: Path) -> tuple[int, int, int] | None:
    """(m, n, c) from the first row of an extended-layout file, or ``None`` if it has none."""
    try:
        with path.open(encoding="utf-8-sig") as handle:
            first = handle.readline()
    except (OSError, UnicodeDecodeError):
        return None
    cells = [cell for cell in re.split(r"[,;\s]+", first.strip()) if cell]
    if len(cells) != 3 or not all(cell.isdigit() for cell in cells):
        return None
    m, n, c = (int(cell) for cell in cells)
    return m, n, c


def load_extended(path: Path, name: str | None = None) -> Dataset:
    """Read a file of the extended layout (``.dat`` or ``.csv``)."""
    if not path.is_file():
        raise DatasetError(f"dataset file not found: {path}")
    return load_extended_layout(path, LoadOptions(name=name or path.stem))


@dataclass(frozen=True)
class DatasetCatalog:
    """The datasets of one ``datasets`` folder."""

    root: Path
    entries: tuple[CatalogEntry, ...]

    @property
    def default(self) -> CatalogEntry | None:
        """The default dataset, if the folder has one."""
        return next((e for e in self.entries if e.family == DEFAULT_ID), None)

    def __iter__(self) -> Iterator[CatalogEntry]:
        """Iterate over the entries: the default, then by type folder and name, then the rest."""
        return iter(self.entries)

    def __len__(self) -> int:
        """Number of datasets."""
        return len(self.entries)

    def groups(self) -> tuple[tuple[str, tuple[CatalogEntry, ...]], ...]:
        """The entries by folder, empty groups left out.

        ``default``, then the type folders ``Quantitative``, ``Nominal``, ``Heterogeneous``,
        then ``Other`` for family folders outside them.
        """
        titles = ["default", *(kind.folder for kind in DatasetType), "Other"]
        grouped: dict[str, list[CatalogEntry]] = {title: [] for title in titles}
        for entry in self.entries:
            if entry.family == DEFAULT_ID:
                grouped["default"].append(entry)
            elif entry.dataset_type is not None:
                grouped[entry.dataset_type.folder].append(entry)
            else:
                grouped["Other"].append(entry)
        return tuple((title, tuple(found)) for title, found in grouped.items() if found)

    def find(self, key: str) -> CatalogEntry | None:
        """The entry with this id or display name (case-insensitive), or ``None``."""
        wanted = key.strip().lower()
        for entry in self.entries:
            if wanted in (entry.id, entry.name.lower(), _slug(entry.name)):
                return entry
        return None

    def check(self) -> list[EntryCheck]:
        """Load every file of every entry; compare the header with the name and the formats.

        Returns:
            One result per entry: the shape, type and data hash as loaded, the SHA-256 of every
            file and the problems found (a header that contradicts the file name, formats that
            hold different data, feature types that contradict the type folder, a file not in
            the author's conventions, unreadable files).
        """
        return [check_entry(entry) for entry in self.entries]


def type_rule_problem(entry: CatalogEntry, dataset: Dataset) -> str:
    """How ``dataset`` breaks the rule of its type folder, or ``""`` (ADR-021).

    ``Quantitative/`` holds datasets whose features are all quantitative, ``Nominal/`` all
    nominal, ``Heterogeneous/`` both.
    """
    folder = entry.dataset_type
    found = dataset.dataset_type
    if folder is None or found is folder:
        return ""
    if folder is DatasetType.HETEROGENEOUS:
        return (
            f"{entry.name} is in {folder.folder}/, but all {dataset.n} features are {found.value} "
            f"— a heterogeneous dataset has quantitative and nominal features ({found.folder}/)"
        )
    other = dataset.nominal if folder is DatasetType.QUANTITATIVE else dataset.quantitative
    names = [feature_name(j) for j in range(dataset.n) if other[j]]
    shown = ", ".join(names[:8]) + (", …" if len(names) > 8 else "")
    kind = "nominal" if folder is DatasetType.QUANTITATIVE else "quantitative"
    return (
        f"{entry.name} is in {folder.folder}/, but {len(names)} feature(s) are {kind} ({shown}) "
        f"— every feature of a {folder.value} dataset is {folder.value} ({found.folder}/)"
    )


def check_entry(entry: CatalogEntry) -> EntryCheck:
    """The check of one entry (see :meth:`DatasetCatalog.check`)."""
    problems: list[str] = []
    sha = {f.suffix.lower(): file_sha256(f) for f in entry.files}
    hashes: dict[str, str] = {}
    shape: tuple[int, int, int] | None = None
    dataset_type: DatasetType | None = None
    for file in entry.files:  # one file in memory at a time: TCGA_LUAD holds 34 million values
        try:
            dataset = load_extended(file, entry.name)
        except DatasetError as error:
            problems.append(str(error))
            continue
        hashes[file.suffix.lower()] = dataset.content_hash()
        conventions = convention_problem(file, dataset)
        if conventions:
            problems.append(f"not in the author's conventions — {conventions}")
        if shape is None:  # the shape and the type of the first file that loads
            shape = (dataset.m, dataset.n, len(dataset.classes))
            dataset_type = dataset.dataset_type
            if entry.shape is not None and shape != entry.shape:
                problems.append(
                    f"{entry.path.name}: the file holds {shape}, its name says {entry.shape}"
                )
            rule = type_rule_problem(entry, dataset)
            if rule:
                problems.append(rule)
        del dataset
    if len(set(hashes.values())) > 1:
        problems.append(
            f"{entry.name}: the {' and '.join(hashes)} files hold different data "
            f"({entry.path.suffix} is used)"
        )
    return EntryCheck(
        entry, shape, hashes.get(entry.path.suffix.lower()), dataset_type, sha, tuple(problems)
    )


def find_datasets_root(start: Path | None = None) -> Path | None:
    """The dataset folder, or ``None`` if there is none.

    ``$ERDR_DATASETS`` if set, otherwise the nearest ``datasets`` folder from ``start`` (the
    working directory by default) upwards.
    """
    override = os.environ.get(ENVIRONMENT_VARIABLE)
    if override:
        root = Path(override)
        if not root.is_dir():
            raise DatasetError(f"{ENVIRONMENT_VARIABLE} = {override}: not a folder")
        return root
    folder = (start or Path.cwd()).resolve()
    for candidate in (folder, *folder.parents):
        if (candidate / DATASETS_DIR).is_dir():
            return candidate / DATASETS_DIR
    return None


def _grouped(files: list[Path]) -> dict[Path, list[Path]]:
    groups: dict[Path, list[Path]] = {}
    for file in files:
        groups.setdefault(file.with_suffix(""), []).append(file)
    for group in groups.values():
        group.sort(key=lambda f: EXTENSIONS.index(f.suffix.lower()))
    return groups


def _family_files(root: Path) -> list[Path]:
    """Dataset files in the family sub-folders (any depth), reserved folders skipped."""
    found: list[Path] = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        if folder.name.lower() in RESERVED_DIRS or folder.name.startswith("."):
            continue
        found += [f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in EXTENSIONS]
    return found


def _family(parts: tuple[str, ...]) -> tuple[str, DatasetType | None]:
    """(family, type folder) of a file's path inside the dataset folder."""
    dataset_type = DatasetType.from_folder(parts[0])
    if dataset_type is not None and len(parts) > 2:
        return parts[1], dataset_type
    return parts[0], None


def discover(root: Path) -> DatasetCatalog:
    """Scan a ``datasets`` folder (see the module docstring for the layout)."""
    entries: list[CatalogEntry] = []
    defaults = [root / f"{DEFAULT_STEM}{ext}" for ext in EXTENSIONS]
    present = [f for f in defaults if f.is_file()]
    if present:
        shape = read_shape(present[0])
        entries.append(CatalogEntry(DEFAULT_ID, DEFAULT_STEM, tuple(present), DEFAULT_ID, shape))
    found: list[
        tuple[str, tuple[Path, ...], tuple[int, int, int] | None, str, DatasetType | None]
    ] = []
    for stem, group in _grouped(_family_files(root)).items():
        family, dataset_type = _family(group[0].relative_to(root).parts)
        match = _SHAPE.match(stem.name)
        if match:
            m, n, c = int(match["m"]), int(match["n"]), int(match["c"])
            base, shape = f"{_slug(match['name'])}-{m}", (m, n, c)
        else:
            base, shape = _slug(stem.name), None
        found.append((base, tuple(group), shape, family, dataset_type))
    # the type folders in their order (quantitative, nominal, heterogeneous), then the others
    order = list(DatasetType)
    found.sort(key=lambda f: (order.index(f[4]) if f[4] else len(order), f[1][0].stem.lower()))
    bases = [base for base, *_ in found]
    for base, files, shape, family, dataset_type in found:
        shared = bases.count(base) > 1 and shape is not None  # Molecular-Biology (100, 10 | 50, 2)
        identifier = f"{base}-{shape[1]}" if shared and shape else base
        entries.append(CatalogEntry(identifier, files[0].stem, files, family, shape, dataset_type))
    ids = [e.id for e in entries]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise DatasetError(f"{root}: several datasets share the id(s) {', '.join(duplicates)}")
    return DatasetCatalog(root, tuple(entries))


def project_catalog(start: Path | None = None) -> DatasetCatalog | None:
    """The catalogue of the project's dataset folder, or ``None`` if there is none."""
    root = find_datasets_root(start)
    return discover(root) if root is not None else None


def resolve_dataset(source: str | Path | None = None, start: Path | None = None) -> Dataset:
    """Load a dataset by file path, id, display name or ``default`` (``None`` = the default).

    Order: an existing file; the project catalogue (``datasets`` folder); the package's built-in
    datasets (``heart-disease-7`` is also the default when there is no ``datasets`` folder).

    Raises:
        DatasetError: Nothing matches; the message lists what is available.
    """
    # data.builtin imports the loaders, which this module imports — look it up here
    from erdr.data.builtin import DATASETS, DEFAULT_BUILTIN, load_builtin
    from erdr.data.loaders import load_dataset

    key = DEFAULT_ID if source is None else str(source)
    path = Path(key)
    if path.is_file():
        return load_dataset(path)
    if path.suffix.lower() in {*EXTENSIONS, ".xlsx", ".xlsm", ".txt", ".parquet", ".pq"}:
        raise DatasetError(f"dataset file not found: {path}")
    catalog = project_catalog(start)
    if catalog is not None:
        entry = catalog.find(key)
        if entry is not None:
            return entry.load()
    if key == DEFAULT_ID and (catalog is None or catalog.default is None):
        return load_builtin(DEFAULT_BUILTIN)
    if key in DATASETS:
        return load_builtin(key)
    available = [e.id for e in catalog] if catalog is not None else []
    available += [f"builtin: {name}" for name in DATASETS.names()]
    raise DatasetError(f"unknown dataset {key!r}; available: {', '.join(available)}")
