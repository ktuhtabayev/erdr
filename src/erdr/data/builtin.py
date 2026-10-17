"""Built-in datasets shipped with the package (registry :data:`DATASETS`).

Byte-for-byte copies of the ``.csv`` files of the project's dataset folder in the extended layout
(``m, n, c`` / objects / type flags), so that an installation without the ``datasets`` folder —
the Windows executable — still has them, grouped by dataset type like the folder (ADR-021).
Heart-Disease is the Statlog (Heart) dataset of the UCI Machine Learning Repository (CC BY 4.0):
6 quantitative and 7 nominal features (the file's type flags); class 1 = absence, class 2 =
presence of heart disease. TCGA_LUAD (589, 57772, 2) is not built in: it is 391 MB per file and
stays on the author's computer.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import as_file, files

from erdr.core.registry import Registry
from erdr.data.loaders import LoadOptions, load_extended_layout
from erdr.data.schema import Dataset, DatasetType


@dataclass(frozen=True)
class BuiltinDataset:
    """A dataset file inside the package."""

    filename: str
    """File in ``erdr/data/datasets``."""
    description: str
    """One line for listings."""
    dataset_type: DatasetType = DatasetType.HETEROGENEOUS
    """Quantitative, nominal or heterogeneous (the type folder it comes from; tested)."""

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
        (
            "the 7 objects of the ERDR workbook — rows 1, 10, 73, 143, 224, 226, 239 of "
            "Heart-Disease (270, 13, 2) (|K1| = 3, |K2| = 4)"
        ),
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

# ---------------------------------------------------------------- the datasets folder by type

_Q, _N, _H = DatasetType.QUANTITATIVE, DatasetType.NOMINAL, DatasetType.HETEROGENEOUS
for _name, _file, _type, _description, _summary in (
    (
        "cancer-589",
        "Cancer (589, 44, 2).csv",
        _Q,
        "44 quantitative features (0 … 3.17), |K1| = 530, |K2| = 59; source not recorded",
        "Cancer (589, 44, 2) — quantitative",
    ),
    (
        "hypertension-147",
        "Hypertension (147, 29, 2).csv",
        _Q,
        (
            "29 cardiological indicators; K1 = healthy (111), K2 = hypertension (36) — "
            "N. A. Ignatev's monograph"
        ),
        "Hypertension (147, 29, 2) — quantitative",
    ),
    (
        "spambase-4204",
        "Spambase (4204, 57, 2).csv",
        _Q,
        (
            "Spambase, UCI, without repeated rows: 57 quantitative; K1 = not spam (2528), "
            "K2 = spam (1676)"
        ),
        "Spambase (4204, 57, 2) — quantitative, UCI",
    ),
    (
        "molecular-biology-106",
        "Molecular-Biology (106, 57, 2).csv",
        _N,
        (
            "promoter gene sequences of E. coli, UCI: 57 nominal positions coded 1–4; "
            "K1 = promoter (53), K2 = not a promoter (53)"
        ),
        "Molecular-Biology (106, 57, 2) — nominal, UCI",
    ),
    (
        "molecular-biology-100-10",
        "Molecular-Biology (100, 10, 2).csv",
        _N,
        "Molecular-Biology (106, 57, 2) without S₅₁–S₅₃ and S₁₀₄–S₁₀₆, its first 10 positions",
        "Molecular-Biology (100, 10, 2) — nominal",
    ),
    (
        "molecular-biology-100-50",
        "Molecular-Biology (100, 50, 2).csv",
        _N,
        "Molecular-Biology (106, 57, 2) without S₅₁–S₅₃ and S₁₀₄–S₁₀₆, its first 50 positions",
        "Molecular-Biology (100, 50, 2) — nominal",
    ),
    (
        "uzb-kor-100",
        "Uzb-Kor (100, 24, 2).csv",
        _N,
        (
            "24 questionnaire answers (0 = no answer, 123 = several answers); K1 = Uzbek (50), "
            "K2 = Korean (50) — NUUz, sociology department"
        ),
        "Uzb-Kor (100, 24, 2) — nominal",
    ),
    (
        "german-1000",
        "German (1000, 20, 2).csv",
        _H,
        (
            "Statlog (German Credit), UCI: 7 quantitative + 13 nominal; K1 = good (700), "
            "K2 = bad (300)"
        ),
        "German (1000, 20, 2) — heterogeneous, UCI",
    ),
    (
        "ionosfera-350",
        "Ionosfera (350, 33, 2).csv",
        _H,
        (
            "Ionosphere radar returns: x₁ nominal (0/1) + 32 quantitative; K1 = bad (125), "
            "K2 = good (225)"
        ),
        "Ionosfera (350, 33, 2) — heterogeneous",
    ),
):
    DATASETS.add(_name, BuiltinDataset(_file, _description, _type), summary=_summary)


def load_builtin(name: str) -> Dataset:
    """Load the built-in dataset ``name`` (see :data:`DATASETS`)."""
    return DATASETS.get(name).load()
