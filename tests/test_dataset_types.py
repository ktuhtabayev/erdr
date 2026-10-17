"""Dataset types (ADR-021) and the metric that follows them (ADR-022)."""

from pathlib import Path

import numpy as np
import pytest

from erdr.config import ExperimentConfig, plugin
from erdr.config.models import DistanceConfig, ERDRConfig, TypeMetricsConfig
from erdr.data import Dataset, DatasetType, FeatureType, load_builtin, write_extended
from erdr.data.catalog import check_entry, discover, type_rule_problem
from erdr.data.writers import _csv_number, _dat_number, convention_problem
from erdr.errors import ConfigError, RegistryError
from erdr.services.datasets import (
    Suitability,
    available_memory,
    check_type_metrics,
    choose_metric,
    megabytes,
    memory_estimate,
    memory_warning,
    suitability,
    suited_metrics,
    summarize,
)
from erdr.services.experiment import run_experiment

Q, N, H = DatasetType.QUANTITATIVE, DatasetType.NOMINAL, DatasetType.HETEROGENEOUS


def toy(types: str, name: str = "Toy") -> Dataset:
    """Four objects of two classes; ``types`` like ``"qn"`` (q = quantitative, n = nominal)."""
    values = np.array([[0.0, 1.0, 2.0], [1.0, 2.0, 1.0], [3.0, 1.0, 1.0], [4.0, 2.0, 2.0]])
    kinds = tuple(FeatureType.QUANTITATIVE if t == "q" else FeatureType.NOMINAL for t in types)
    return Dataset(X=values[:, : len(types)], y=[1, 1, 2, 2], feature_types=kinds, name=name)


# ---------------------------------------------------------------- the dataset type


def test_dataset_type_of_the_features():
    assert toy("qqq").dataset_type is Q
    assert toy("nn").dataset_type is N
    assert toy("qn").dataset_type is H
    assert DatasetType.from_folder("Nominal") is N
    assert DatasetType.from_folder("heterogeneous") is H
    assert DatasetType.from_folder("Heart-Disease") is None
    assert [kind.folder for kind in DatasetType] == ["Quantitative", "Nominal", "Heterogeneous"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("cancer-589", Q),
        ("hypertension-147", Q),
        ("molecular-biology-106", N),
        ("uzb-kor-100", N),
        ("german-1000", H),
        ("ionosfera-350", H),
        ("heart-disease-270", H),
    ],
)
def test_builtin_types(name: str, expected: DatasetType):
    assert load_builtin(name).dataset_type is expected


# ---------------------------------------------------------------- the type folders


def _write(folder: Path, dataset: Dataset) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for suffix in (".dat", ".csv"):
        write_extended(dataset, folder / f"{dataset.name} (4, {dataset.n}, 2){suffix}")


def test_type_folders_are_discovered_and_checked(tmp_path: Path):
    _write(tmp_path / "Quantitative" / "Good", toy("qq", "Good"))
    _write(tmp_path / "Quantitative" / "Mixed", toy("qn", "Mixed"))
    _write(tmp_path / "Nominal" / "Wrong", toy("q", "Wrong"))
    _write(tmp_path / "Heterogeneous" / "Plain", toy("nn", "Plain"))
    _write(tmp_path / "Family", toy("qn", "Loose"))  # a family folder outside the type folders
    catalog = discover(tmp_path)
    assert [e.id for e in catalog] == ["good-4", "mixed-4", "wrong-4", "plain-4", "loose-4"]
    assert [title for title, _ in catalog.groups()] == [
        "Quantitative",
        "Nominal",
        "Heterogeneous",
        "Other",
    ]
    entries = {e.id: e for e in catalog}
    assert entries["good-4"].family == "Good"
    assert entries["good-4"].dataset_type is Q
    assert entries["loose-4"].family == "Family"
    assert entries["loose-4"].dataset_type is None
    checks = {c.entry.id: c for c in catalog.check()}
    assert checks["good-4"].passed
    assert checks["loose-4"].passed
    assert checks["mixed-4"].dataset_type is H
    assert "is in Quantitative/, but 1 feature(s) are nominal (x₂)" in checks["mixed-4"].problems[0]
    assert "are quantitative" in checks["wrong-4"].problems[0]
    assert "all 2 features are nominal" in checks["plain-4"].problems[0]
    assert type_rule_problem(entries["good-4"], toy("qq")) == ""


def test_files_outside_the_conventions_are_reported(tmp_path: Path):
    family = tmp_path / "Nominal" / "Toy"
    _write(family, toy("nn"))
    dat = family / "Toy (4, 2, 2).dat"
    original = dat.read_bytes()
    dataset = toy("nn")
    assert convention_problem(dat, dataset) == ""
    dat.write_bytes(original.replace(b"\n", b"\r\n"))  # Windows line ends
    assert ".dat lines end with LF" in convention_problem(dat, dataset)
    check = check_entry(discover(tmp_path).entries[0])
    assert not check.passed
    assert "not in the author's conventions" in check.problems[0]
    dat.write_bytes(original.replace(b"1.0 2.0", b"1 2"))  # integers without a point
    assert "cell 1 is '1'; the .dat conventions write '1.0'" in convention_problem(dat, dataset)
    dat.write_bytes(original.rstrip(b"\n"))  # no line end at the end
    assert "must end with LF" in convention_problem(dat, dataset)
    dat.write_bytes(original + b"0 0\n")
    assert "text after the type row" in convention_problem(dat, dataset)
    dat.write_bytes(original.split(b"\n", 2)[0] + b"\n")
    assert "ends before the type row" in convention_problem(dat, dataset)
    dat.write_bytes(original.replace(b"2.0 1\n", b"2.0 1 7\n", 1))
    assert "cells; the .dat conventions write" in convention_problem(dat, dataset)
    wrong = family / "Toy.txt"
    wrong.write_bytes(original)
    assert "cannot be compared" in convention_problem(wrong, dataset)


def test_numbers_never_use_an_exponent():
    assert (_csv_number(70.0), _dat_number(70.0)) == ("70", "70.0")
    assert (_csv_number(2.4), _dat_number(2.4)) == ("2.4", "2.4")
    assert (_csv_number(-3e-05), _dat_number(-3e-05)) == ("-0.00003", "-0.00003")
    assert _dat_number(1e22) == "10000000000000000000000.0"
    assert float(_dat_number(0.1 + 0.2)) == 0.1 + 0.2  # the shortest digits that read back


# ---------------------------------------------------------------- metrics by dataset type


def test_suitability_follows_the_metric_domain():
    assert suitability("zhuravlev", Q) is Suitability.SUITED
    assert suitability("zhuravlev", N) is Suitability.SUITED
    assert suitability("euclidean", Q) is Suitability.SUITED
    assert suitability("euclidean", N) is Suitability.UNSUITED
    assert suitability("euclidean", H) is Suitability.PARTIAL
    assert suitability("hamming", N) is Suitability.SUITED
    assert suitability("hamming", Q) is Suitability.UNSUITED
    assert suited_metrics(H) == ("zhuravlev", "weighted-zhuravlev", "heom", "gower")
    assert "hamming" in suited_metrics(N)
    assert "euclidean" not in suited_metrics(N)
    assert "mahalanobis" in suited_metrics(Q)
    with pytest.raises(RegistryError):
        suitability("nothing", Q)


@pytest.mark.parametrize(
    ("types", "metric"), [("qq", "manhattan"), ("nn", "hamming"), ("qn", "zhuravlev")]
)
def test_auto_takes_the_metric_of_the_type(types: str, metric: str):
    choice = choose_metric(ExperimentConfig(), toy(types))
    assert choice.name == metric
    assert choice.automatic
    assert choice.label == f"{metric} (auto · {toy(types).dataset_type.value} dataset)"
    assert choice.note == ""


@pytest.mark.parametrize(
    "name",
    ["cancer-589", "hypertension-147", "molecular-biology-106", "uzb-kor-100", "ionosfera-350"],
)
def test_auto_gives_the_zhuravlev_results_bit_for_bit(name: str):
    """On every dataset type ``auto`` is the Zhuravlev metric — the literal default is kept."""
    dataset = load_builtin(name)
    zhuravlev = ExperimentConfig(distance=DistanceConfig(metric=plugin("zhuravlev")))
    auto, literal = run_experiment(dataset=dataset), run_experiment(zhuravlev, dataset)
    assert np.array_equal(auto.distances.matrix, literal.distances.matrix)
    assert np.array_equal(auto.result.training, literal.result.training)
    assert auto.warnings == ()


def test_a_metric_must_be_defined_on_the_dataset():
    euclidean = ExperimentConfig(distance=DistanceConfig(metric=plugin("euclidean")))
    with pytest.raises(ConfigError, match="Toy is a nominal dataset without quantitative"):
        choose_metric(euclidean, toy("nn"))
    small = ERDRConfig(k_rule="off")  # the toy has two objects per class
    hamming = ExperimentConfig(distance=DistanceConfig(metric=plugin("hamming")), erdr=small)
    with pytest.raises(ConfigError, match="choose auto or one of zhuravlev"):
        run_experiment(hamming, toy("qq"))
    # a single-type metric on a heterogeneous dataset runs, flagged
    choice = choose_metric(euclidean, toy("qn"))
    assert choice.partial
    assert choice.label == "euclidean"
    assert "sees only 1 quantitative feature(s)" in choice.note
    run = run_experiment(euclidean.model_copy(update={"erdr": small}), toy("qnn"))
    assert any("2 nominal feature(s) do not count" in w for w in run.warnings)
    only_nominal = ExperimentConfig(distance=DistanceConfig(features="nominal"))
    assert "sees only 1 nominal feature(s)" in choose_metric(only_nominal, toy("qn")).note
    named = ExperimentConfig(distance=DistanceConfig(features=("x₁",)))
    assert choose_metric(named, toy("qn")).quantitative_seen == 1
    with pytest.raises(ConfigError, match="unknown features"):
        choose_metric(ExperimentConfig(distance=DistanceConfig(features=("x9",))), toy("qn"))


def test_type_metrics_must_suit_their_type():
    chosen = TypeMetricsConfig(quantitative=plugin("euclidean"), nominal=plugin("gower"))
    config = ExperimentConfig(distance=DistanceConfig(type_metrics=chosen))
    assert choose_metric(config, toy("qq")).name == "euclidean"
    assert choose_metric(config, toy("nn")).name == "gower"
    check_type_metrics(config)
    check_type_metrics(ExperimentConfig())
    wrong = TypeMetricsConfig(heterogeneous=plugin("euclidean"))
    bad = ExperimentConfig(distance=DistanceConfig(type_metrics=wrong))
    with pytest.raises(ConfigError, match=r"type_metrics.heterogeneous = euclidean"):
        choose_metric(bad, toy("qn"))
    with pytest.raises(ConfigError, match="does not suit heterogeneous datasets"):
        check_type_metrics(bad)
    minkowski = TypeMetricsConfig(quantitative=plugin("minkowski", p=3))
    with_params = ExperimentConfig(distance=DistanceConfig(type_metrics=minkowski))
    assert choose_metric(with_params, toy("qq")).label == (
        "minkowski {'p': 3} (auto · quantitative dataset)"
    )


def test_summary_names_the_type_and_the_metric():
    s = summarize(load_builtin("uzb-kor-100"))
    assert s.dataset_type is N
    assert s.metric is not None
    assert s.metric.name == "hamming"
    assert s.metrics == suited_metrics(N)
    assert s.metric_problem == ""
    euclidean = ExperimentConfig(distance=DistanceConfig(metric=plugin("euclidean")))
    s = summarize(load_builtin("uzb-kor-100"), euclidean)
    assert s.metric is None
    assert "nominal dataset" in s.metric_problem


# ---------------------------------------------------------------- memory


def test_memory_estimate_and_warning():
    assert memory_estimate(1000, 20) == 8 * (3 * 1000 * 20 + 4 * 1000 * 1000)
    assert megabytes(memory_estimate(589, 57772)) == "789 MB"
    assert megabytes(5 * 2**30) == "5.0 GB"
    assert memory_warning(10, 3, free=2**30) == ""
    warning = memory_warning(10_000, 80, free=2**30)
    assert "needs about 3.0 GB of memory; 1.0 GB are free" in warning
    free = available_memory()
    assert free is None or free > 0
