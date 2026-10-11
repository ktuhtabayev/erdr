"""Shared paths and fixtures."""

import os
from pathlib import Path

import pytest

from erdr.data import Dataset, load_builtin
from erdr.data.catalog import resolve_dataset
from erdr.services.experiment import ExperimentResult, run_experiment

# GUI tests draw into memory: no window appears and no display is needed (set before Qt loads)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
CONFIGS = ROOT / "configs"
WORKBOOK = ROOT / "resources" / "Experiments" / "ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx"
"""The ERDR workbook: the specification and its golden values."""
HEART_270 = DATASETS / "Heart-Disease" / "Heart-Disease (270, 13, 2)"
"""Stem of the full Heart-Disease files (.csv and .dat)."""
SELECTED_ROWS = (1, 10, 73, 143, 224, 226, 239)
"""The source rows of the workbook's 7 objects S₁ … S₇."""


@pytest.fixture(scope="session")
def default_dataset() -> Dataset:
    """Heart-Disease (7, 13, 2) — ``datasets/default.dat``."""
    return resolve_dataset("default", start=ROOT)


@pytest.fixture(scope="session")
def heart270() -> Dataset:
    """Heart-Disease (270, 13, 2) from the package's built-in copy."""
    return load_builtin("heart-disease-270")


@pytest.fixture(scope="session")
def guide_dataset() -> Dataset:
    """The worked example of the step-by-step guide: 7 objects, 4 features, 2 classes."""
    return load_builtin("guide-example")


@pytest.fixture(scope="session")
def default_run(default_dataset: Dataset) -> ExperimentResult:
    """ERDR on the default dataset with the default (literal) configuration."""
    return run_experiment(dataset=default_dataset)


@pytest.fixture(scope="session")
def guide_run(guide_dataset: Dataset) -> ExperimentResult:
    """ERDR on the guide's example with the default (literal) configuration."""
    return run_experiment(dataset=guide_dataset)
