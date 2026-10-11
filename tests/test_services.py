"""The experiment runner, analyses, dataset summaries, run folders and workbook validation."""

import json
from pathlib import Path

import numpy as np
import pytest

from erdr.config import ERDRConfig, ExperimentConfig, plugin
from erdr.config.models import DistanceConfig, ReadingsConfig
from erdr.core.readings import CLOSEST, LITERAL, ZScope
from erdr.data import Dataset
from erdr.errors import AlgorithmUndefinedError, ConfigError, DatasetError
from erdr.services.analysis import compare_readings, sweep_k
from erdr.services.datasets import summarize
from erdr.services.experiment import ExperimentResult, check_k_rule, run_experiment
from erdr.services.runs import (
    RESULT,
    RunError,
    dataset_from_data,
    dataset_to_data,
    latest_run,
    list_runs,
    load_run,
    read_manifest,
    save_run,
    started_at,
)
from erdr.services.validation import find_workbook, validate_workbook
from tests.conftest import ROOT, WORKBOOK

# ---------------------------------------------------------------- the runner


def test_run_experiment(default_run: ExperimentResult):
    assert default_run.k == 3
    assert default_run.permitted.ks == (3,)
    assert len(default_run.config_hash) == 64
    assert default_run.dataset_hash == default_run.dataset.content_hash()
    assert default_run.notes == ()
    assert default_run.warnings == ()
    training = default_run.training_dataset
    assert training.name == "default (5, 13, 2) training"
    assert training.object_ids == ("S₁", "S₂", "S₅", "S₆", "S₇")
    assert default_run.validation_dataset.m == 2
    assert default_run.class_counts(default_run.result.training) == (2, 3)


def test_k_rule_modes(default_dataset: Dataset):
    k5 = ExperimentConfig(erdr=ERDRConfig(k=5))
    with pytest.raises(ConfigError, match="outside the k rule"):
        run_experiment(k5, default_dataset)
    warned = run_experiment(ExperimentConfig(erdr=ERDRConfig(k=5, k_rule="warn")), default_dataset)
    assert warned.warnings
    assert "permitted: 3" in warned.warnings[0]
    off = ExperimentConfig(erdr=ERDRConfig(k=1, k_rule="off"))
    assert check_k_rule(off, default_dataset)[1] == ()
    with pytest.raises(AlgorithmUndefinedError, match="z\\(Sᵢ, k\\)"):
        run_experiment(ExperimentConfig(erdr=ERDRConfig(k=7, k_rule="off")), default_dataset)


def test_other_metrics_normalizers_and_features(default_dataset: Dataset):
    config = ExperimentConfig(
        preprocessing={"normalizer": plugin("z-score")},  # type: ignore[arg-type]
        distance=DistanceConfig(metric=plugin("euclidean")),
    )
    run = run_experiment(config, default_dataset)
    assert run.distances.metric == "euclidean"
    assert run.distances.features.tolist() == [0, 3, 4, 7, 9, 11]
    named = run_experiment(
        ExperimentConfig(distance=DistanceConfig(features=("x₁", "x₄"))), default_dataset
    )
    assert named.distances.features.tolist() == [0, 3]
    with pytest.raises(ConfigError, match="unknown features"):
        run_experiment(
            ExperimentConfig(distance=DistanceConfig(features=("nope",))), default_dataset
        )


def test_closest_reading_on_270(heart270: Dataset):
    config = ExperimentConfig(erdr=ERDRConfig(readings=ReadingsConfig.from_readings(CLOSEST)))
    run = run_experiment(config, heart270)
    assert run.result.training.size == 75  # the article's Table 1, k = 3
    assert len(run.notes) == 2


# ---------------------------------------------------------------- analyses


def test_compare_readings(default_dataset: Dataset):
    calls: list[tuple[int, int]] = []
    rows = compare_readings(
        default_dataset,
        z_scopes=(ZScope.ALL, ZScope.OWN_CLASS),
        progress=lambda d, t: calls.append((d, t)),
    )
    assert len(rows) == 16
    assert calls[-1] == (16, 16)
    literal = rows[0]
    assert literal.readings == LITERAL
    assert literal.training == (0, 1, 4, 5, 6)
    assert literal.training_by_class == (2, 3)
    own = rows[8]
    assert own.error is not None  # K1 has 3 objects: no 3rd own-class neighbour
    assert len({row.training for row in rows if row.error is None}) == 6


def test_sweep(default_dataset: Dataset):
    rows = sweep_k(default_dataset, ks=[1, 2, 3, 9])
    assert {(row.k, row.readings) for row in rows} == {
        (1, LITERAL),
        (1, CLOSEST),
        (2, LITERAL),
        (2, CLOSEST),
        (3, LITERAL),
    }
    assert [row.permitted for row in rows if row.k == 3] == [True]
    assert rows[0].share == rows[0].training_size / 7
    assert sweep_k(default_dataset)[0].k == 3  # default: the permitted k


def test_summarize(default_dataset: Dataset):
    s = summarize(default_dataset)
    assert s.shape == "(7, 13, 2)"
    assert s.class_text == "K1 = 1: 3 · K2 = 2: 4"
    assert s.quantitative == ("x₁", "x₄", "x₅", "x₈", "x₁₀", "x₁₂")
    assert s.permitted.text == "3"
    assert (s.largest_k, s.largest_k_own_class) == (6, 2)


# ---------------------------------------------------------------- run folders


def test_run_folders(tmp_path: Path, default_run: ExperimentResult):
    folder = save_run(default_run, tmp_path)
    second = save_run(default_run, tmp_path)
    assert second.name == folder.name + "-2"
    names = {p.name for p in folder.iterdir()}
    assert names == {
        "manifest.yaml",
        "config.yaml",
        "dataset.json",
        "result.json",
        "training.dat",
        "training.csv",
        "validation.dat",
        "validation.csv",
    }
    manifest = read_manifest(folder)
    assert manifest["result"]["training"] == "{S₁, S₂, S₅, S₆, S₇}"
    assert set(manifest["files"]) == names - {"manifest.yaml"}
    assert started_at(folder) is not None
    repeated = load_run(folder)
    assert repeated.result.training.tolist() == [0, 1, 4, 5, 6]
    runs = list_runs(tmp_path)
    assert {r.folder for r in runs} == {folder, second}
    assert latest_run(tmp_path) in {folder, second}
    assert latest_run(tmp_path / "none") is None
    # a tampered result is detected
    data = json.loads((folder / RESULT).read_text(encoding="utf-8"))
    data["training"] = [0]
    (folder / RESULT).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RunError, match="another training sample"):
        load_run(folder)
    with pytest.raises(RunError, match="not a run folder"):
        load_run(tmp_path)
    with pytest.raises(RunError, match="manifest"):
        read_manifest(tmp_path)


def test_dataset_json_round_trip(heart270: Dataset):
    again = dataset_from_data(json.loads(json.dumps(dataset_to_data(heart270))))
    assert again.content_hash() == heart270.content_hash()
    assert np.array_equal(again.X, heart270.X)


# ---------------------------------------------------------------- validation


def test_validation_report_parts():
    report = validate_workbook(WORKBOOK, skip=("table1", "readings"))
    assert report.passed
    sheets = [name for name, _, _ in report.sections()]
    assert "Article Table 1 Check" not in sheets
    assert "Readings (Switches)" not in sheets
    assert find_workbook(ROOT) == WORKBOOK
    assert report.failures == ()


def test_validation_detects_a_difference():
    report = validate_workbook(WORKBOOK, tolerance=-1.0)  # nothing numeric can pass
    assert not report.passed
    assert report.failures


def test_validation_rejects_other_files(tmp_path: Path):
    other = tmp_path / "other.xlsx"
    import openpyxl

    openpyxl.Workbook().save(other)
    with pytest.raises(DatasetError, match="not an ERDR workbook"):
        validate_workbook(other)
    broken = tmp_path / "broken.xlsx"
    broken.write_bytes(b"not a workbook")
    with pytest.raises(DatasetError, match="cannot read"):
        validate_workbook(broken)
    assert find_workbook(tmp_path) is None
