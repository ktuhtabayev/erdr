"""Dataset schema, loaders, writers, the dataset folder and the built-in datasets."""

import logging
from pathlib import Path

import numpy as np
import openpyxl
import pytest

from erdr.config.models import DatasetConfig
from erdr.data import (
    DATASETS,
    Dataset,
    FeatureType,
    detect_format,
    extended_text,
    load_builtin,
    load_dataset,
    load_from_config,
    shape_name,
    write_extended,
)
from erdr.data.catalog import (
    ENVIRONMENT_VARIABLE,
    discover,
    find_datasets_root,
    project_catalog,
    read_shape,
    resolve_dataset,
)
from erdr.errors import DatasetError
from tests.conftest import DATASETS as DATASETS_DIR
from tests.conftest import HEART_270, ROOT, SELECTED_ROWS, WORKBOOK

# ---------------------------------------------------------------- the default dataset files


@pytest.mark.parametrize(("suffix", "newline"), [(".csv", b"\r\n"), (".dat", b"\n")])
def test_default_files_are_the_selected_rows_of_the_270_file(suffix: str, newline: bytes):
    full = (HEART_270.parent / f"{HEART_270.name}{suffix}").read_bytes().split(newline)[:-1]
    default = (DATASETS_DIR / f"default{suffix}").read_bytes().split(newline)[:-1]
    assert default[0].replace(b"7", b"270", 1) == full[0]
    assert default[1:-1] == [full[row] for row in SELECTED_ROWS]
    assert default[-1] == full[-1]  # the type flags


def test_default_dataset_is_the_workbook_dataset(default_dataset: Dataset):
    workbook = load_dataset(WORKBOOK)
    assert workbook.name == "Heart-Disease (7, 13, 2)"
    assert workbook.object_ids == default_dataset.object_ids
    assert np.array_equal(workbook.X, default_dataset.X)
    assert workbook.y.tolist() == default_dataset.y.tolist()
    assert workbook.feature_types == default_dataset.feature_types
    assert default_dataset.class_sizes == (3, 4)
    assert default_dataset.type_flags == (1, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 0)


@pytest.mark.parametrize("stem", ["default", "Heart-Disease/Heart-Disease (270, 13, 2)"])
@pytest.mark.parametrize("suffix", [".csv", ".dat"])
def test_writer_reproduces_the_author_files_byte_for_byte(stem: str, suffix: str):
    path = DATASETS_DIR / f"{stem}{suffix}"
    assert extended_text(load_dataset(path), suffix).encode("utf-8") == path.read_bytes()


def test_csv_and_dat_hold_the_same_data():
    csv = load_dataset(HEART_270.parent / f"{HEART_270.name}.csv")
    dat = load_dataset(HEART_270.parent / f"{HEART_270.name}.dat")
    assert csv.content_hash() == dat.content_hash()
    assert csv.class_sizes == (150, 120)


def test_builtin_copies_match_the_folder(default_dataset: Dataset, heart270: Dataset):
    assert load_builtin("heart-disease-7").content_hash() == default_dataset.content_hash()
    folder = load_dataset(HEART_270.parent / f"{HEART_270.name}.dat")
    assert heart270.content_hash() == folder.content_hash()
    assert set(DATASETS.names()) == {"heart-disease-7", "heart-disease-270", "guide-example"}
    guide = load_builtin("guide-example")
    assert (guide.m, guide.n, guide.class_sizes) == (7, 4, (3, 4))


# ---------------------------------------------------------------- loaders


def test_detect_format(tmp_path: Path):
    assert detect_format(DATASETS_DIR / "default.csv") == "extended"
    assert detect_format(DATASETS_DIR / "default.dat") == "extended"
    assert detect_format(WORKBOOK) == "erdr-workbook"
    table = tmp_path / "t.csv"
    table.write_text("a,b,class\n1,2,x\n", encoding="utf-8")
    assert detect_format(table) == "csv"
    assert detect_format(tmp_path / "t.parquet") == "parquet"
    with pytest.raises(DatasetError, match="unknown dataset extension"):
        detect_format(tmp_path / "t.json")


def test_csv_table_with_inferred_types(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    path = tmp_path / "table.csv"
    path.write_text(
        "id;age;colour;class\na;30;red;yes\nb;40;blue;no\nc;35;red;yes\n", encoding="utf-8"
    )
    with caplog.at_level(logging.WARNING, logger="erdr"):
        dataset = load_dataset(path, id_column="id")
    assert dataset.feature_names == ("age", "colour")
    assert dataset.feature_types == (FeatureType.QUANTITATIVE, FeatureType.NOMINAL)
    assert dataset.categories["colour"] == ("blue", "red")
    assert dataset.object_ids == ("a", "b", "c")
    assert dataset.classes == ("no", "yes")
    assert "inferred" in caplog.text
    typed = load_dataset(path, id_column="id", feature_types={"age": "nominal"})
    assert typed.feature_types[0] is FeatureType.NOMINAL


def test_xlsx_table(tmp_path: Path):
    path = tmp_path / "table.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    for row in (["x1", "x2", "class"], [1, 2, 1], [2, 3, 2], [3, 1, 1]):
        sheet.append(row)
    book.save(path)
    dataset = load_dataset(path)
    assert (dataset.m, dataset.n) == (3, 2)
    assert dataset.class_sizes == (2, 1)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("3 2 2\n1 2 1\n1 2 2\n1 1\n", "rows are expected"),
        ("x y z\n1 2 1\n", "first row"),
        ("2 2 2\n1 a 1\n1 2 2\n1 1\n", "not a number"),
        ("2 2 2\n1 2 1\n1 2 2\n1 1 0 0\n", "type row"),
        ("2 2 3\n1 2 1\n1 2 2\n1 1\n", "c = 3"),
        ("2 2 2\n1 2 1\n1 2 2\n1 7\n", "flags"),
        ("", "empty"),
    ],
)
def test_extended_layout_errors(tmp_path: Path, text: str, message: str):
    path = tmp_path / "bad.dat"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DatasetError, match=message):
        load_dataset(path)


def test_missing_file_and_parquet(tmp_path: Path):
    with pytest.raises(DatasetError, match="not found"):
        load_dataset(tmp_path / "missing.csv")
    path = tmp_path / "t.parquet"
    path.write_bytes(b"PAR1")
    with pytest.raises(DatasetError, match=r"pyarrow|Parquet"):
        load_dataset(path)


def test_load_from_config(
    tmp_path: Path, default_dataset: Dataset, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(ROOT)
    assert load_from_config(DatasetConfig()).content_hash() == default_dataset.content_hash()
    assert load_from_config(DatasetConfig(path="builtin:guide-example")).m == 7
    assert load_from_config(DatasetConfig(path="heart-disease-270")).m == 270
    relative = load_from_config(DatasetConfig(path="default.dat"), base_dir=DATASETS_DIR)
    assert relative.m == 7


# ---------------------------------------------------------------- schema


def test_dataset_validation():
    with pytest.raises(DatasetError, match="2-D"):
        Dataset(X=np.zeros(3), y=[1, 2, 1], feature_types=(FeatureType.QUANTITATIVE,))
    with pytest.raises(DatasetError, match="non-finite"):
        Dataset(X=np.array([[np.nan]]), y=[1], feature_types=(FeatureType.QUANTITATIVE,))
    with pytest.raises(DatasetError, match="labels"):
        Dataset(X=np.zeros((2, 1)), y=[1], feature_types=(FeatureType.QUANTITATIVE,))
    with pytest.raises(DatasetError, match="all integers or all strings"):
        Dataset(X=np.zeros((2, 1)), y=[1, "a"], feature_types=(FeatureType.QUANTITATIVE,))
    with pytest.raises(DatasetError, match="unique"):
        Dataset(
            X=np.zeros((2, 1)), y=[1, 2], feature_types=("quantitative",), object_ids=("a", "a")
        )
    with pytest.raises(DatasetError, match="flags must be 1"):
        FeatureType.from_flag(3)


def test_subset_and_types(default_dataset: Dataset):
    part = default_dataset.subset([0, 2], name="part")
    assert part.object_ids == ("S₁", "S₃")
    assert part.name == "part"
    changed = default_dataset.with_feature_types({"x₂": "quantitative"})
    assert changed.quantitative[1]
    with pytest.raises(DatasetError, match="unknown features"):
        default_dataset.with_feature_types({"nope": "nominal"})
    assert "m=7" in repr(default_dataset)


# ---------------------------------------------------------------- writers


def test_write_extended(tmp_path: Path, default_dataset: Dataset):
    path = write_extended(default_dataset.subset([0, 1, 2]), tmp_path / "out" / "part.dat")
    assert path.read_text(encoding="utf-8").startswith("3 13 2\n")
    with pytest.raises(DatasetError, match="already exists"):
        write_extended(default_dataset, path, overwrite=False)
    with pytest.raises(DatasetError, match=r".csv or .dat"):
        extended_text(default_dataset, ".txt")
    spaced = Dataset(X=np.zeros((2, 1)), y=["a b", "c"], feature_types=("nominal",))
    with pytest.raises(DatasetError, match="cannot be written"):
        extended_text(spaced, ".dat")
    assert shape_name("Heart-Disease (270, 13, 2)", default_dataset) == "Heart-Disease (7, 13, 2)"
    assert shape_name("plain", default_dataset) == "plain (7, 13, 2)"


# ---------------------------------------------------------------- the dataset folder


def test_project_catalog():
    catalog = project_catalog(ROOT)
    assert catalog is not None
    assert [e.id for e in catalog] == ["default", "heart-disease-270"]
    assert catalog.default is not None
    assert catalog.default.shape == (7, 13, 2)
    assert catalog.default.label == "default (7, 13, 2)"
    entry = catalog.find("Heart-Disease (270, 13, 2)")
    assert entry is not None
    assert entry.family == "Heart-Disease"
    assert entry.formats == (".dat", ".csv")
    assert all(check.passed for check in catalog.check())
    assert len(catalog) == 2


def test_discover_layout(tmp_path: Path):
    family = tmp_path / "Toy"
    family.mkdir()
    (family / "Toy (2, 1, 2).dat").write_text("2 1 2\n1.0 1\n2.0 2\n1\n", encoding="utf-8")
    (family / "Toy (2, 1, 2).csv").write_text("2,1,2\n1,1\n3,2\n1,\n", encoding="utf-8")
    (family / "loose.dat").write_text("2 1 2\n1.0 1\n2.0 2\n1\n", encoding="utf-8")
    (tmp_path / "synthetic").mkdir()
    (tmp_path / "synthetic" / "Skip (1, 1, 1).dat").write_text("x", encoding="utf-8")
    catalog = discover(tmp_path)
    assert [e.id for e in catalog] == ["loose", "toy-2"]
    checks = {c.entry.id: c for c in catalog.check()}
    assert not checks["toy-2"].passed  # the .csv holds other data
    assert read_shape(family / "loose.dat") == (2, 1, 2)
    assert read_shape(tmp_path / "missing.dat") is None


def test_discover_rejects_shared_ids(tmp_path: Path):
    for family in ("A", "B"):
        (tmp_path / family).mkdir()
        (tmp_path / family / "same.dat").write_text("2 1 2\n1.0 1\n2.0 2\n1\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="share the id"):
        discover(tmp_path)


def test_resolve_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENVIRONMENT_VARIABLE, raising=False)
    assert resolve_dataset("heart-disease-270", start=ROOT).m == 270
    assert resolve_dataset(str(DATASETS_DIR / "default.csv")).m == 7
    with pytest.raises(DatasetError, match="not found"):
        resolve_dataset(str(tmp_path / "missing.csv"))
    with pytest.raises(DatasetError, match="unknown dataset"):
        resolve_dataset("nothing", start=ROOT)
    # without a datasets folder: the built-in default
    monkeypatch.chdir(tmp_path)
    assert find_datasets_root(tmp_path) is None
    assert resolve_dataset(None, start=tmp_path).name == "Heart-Disease (7, 13, 2)"
    assert resolve_dataset("guide-example", start=tmp_path).n == 4
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, str(DATASETS_DIR))
    assert find_datasets_root(tmp_path) == DATASETS_DIR
    monkeypatch.setenv(ENVIRONMENT_VARIABLE, str(tmp_path / "missing"))
    with pytest.raises(DatasetError, match="not a folder"):
        find_datasets_root(tmp_path)
