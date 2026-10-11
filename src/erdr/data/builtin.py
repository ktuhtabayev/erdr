"""Built-in datasets shipped with the package (registry :data:`DATASETS`).

Byte-for-byte copies of the project's dataset files in the extended layout (``m, n, c`` / objects
/ type flags), so that an installation without the ``datasets`` folder — the Windows executable —
still has them. Heart-Disease is the Statlog (Heart) dataset of the UCI Machine Learning
Repository (CC BY 4.0): 6 quantitative and 7 nominal features (the file's type flags); class 1 =
absence, class 2 = presence of heart disease.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import as_file, files

from erdr.core.registry import Registry
from erdr.data.loaders import LoadOptions, load_extended_layout
from erdr.data.schema import Dataset


@dataclass(frozen=True)
class BuiltinDataset:
    """A dataset file inside the package."""

    filename: str
    """File in ``erdr/data/datasets``."""
    description: str
    """One line for listings."""

    def load(self) -> Dataset:
        """Read the dataset."""
        resource = files("erdr.data") / "datasets" / self.filename
        with as_file(resource) as path:
            return load_extended_layout(path, LoadOptions(name=path.stem))


DATASETS: Registry[BuiltinDataset] = Registry("datasets")
"""Built-in datasets by name."""

DEFAULT_BUILTIN = "heart-disease-7"
"""The default dataset when there is no ``datasets`` folder: the ERDR workbook's 7 objects."""

DATASETS.add(
    "heart-disease-7",
    BuiltinDataset(
        "Heart-Disease (7, 13, 2).csv",
        "the 7 objects of the ERDR workbook — rows 1, 10, 73, 143, 224, 226, 239 of "
        "Heart-Disease (270, 13, 2) (|K1| = 3, |K2| = 4)",
    ),
    summary="Heart-Disease (7, 13, 2) — the ERDR workbook (default)",
)
DATASETS.add(
    "heart-disease-270",
    BuiltinDataset(
        "Heart-Disease (270, 13, 2).csv",
        "Statlog (Heart), UCI: 270 objects (|K1| = 150, |K2| = 120)",
    ),
    summary="Heart-Disease (270, 13, 2) — Statlog (Heart), UCI",
)
DATASETS.add(
    "guide-example",
    BuiltinDataset(
        "ERDR-Guide (7, 4, 2).csv",
        "the worked example of the step-by-step guide: 7 objects, 2 quantitative + 2 nominal",
    ),
    summary="ERDR-Guide (7, 4, 2) — the step-by-step guide's example",
)


def load_builtin(name: str) -> Dataset:
    """Load the built-in dataset ``name`` (see :data:`DATASETS`)."""
    return DATASETS.get(name).load()
