"""The ``erdr`` command line."""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from erdr import __version__
from erdr.cli.app import app
from tests.conftest import CONFIGS, ROOT, WORKBOOK

runner = CliRunner()
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def invoke(*args: str) -> tuple[int, str]:
    result = runner.invoke(app, list(args))
    return result.exit_code, ANSI.sub("", result.output)


@pytest.fixture(autouse=True)
def in_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)


def test_version_and_help():
    code, out = invoke("--version")
    assert code == 0
    assert __version__ in out
    code, out = invoke("--help")
    assert code == 0
    assert "readings" in out


def test_config_commands(tmp_path: Path):
    code, out = invoke("config", "show", "--preset", "closest")
    assert code == 0
    assert "blocked_cover: dropped" in out
    code, out = invoke("config", "show", "--format", "json")
    assert '"schema_version": 1' in out
    path = tmp_path / "c.yaml"
    assert invoke("config", "init", str(path))[0] == 0
    code, out = invoke("config", "init", str(path))
    assert code == 2
    assert "already exists" in out
    code, out = invoke("config", "check", str(CONFIGS / "heart-disease-270-closest.yaml"))
    assert code == 0
    assert "preset  closest" in out
    assert "⚠ B" in out
    bad = tmp_path / "bad.yaml"
    bad.write_text("erdr:\n  k: 0\n", encoding="utf-8")
    assert invoke("config", "check", str(bad))[0] == 2


def test_data_commands():
    code, out = invoke("data", "list")
    assert code == 0
    assert "heart-disease-270" in out
    assert "guide-example" in out
    code, out = invoke("data", "info", "heart-disease-270")
    assert code == 0
    assert "permitted k   3, 5, …, 237" in out
    code, out = invoke("data", "check")
    assert code == 0
    assert "✓ default" in out
    assert invoke("data", "info", "nothing")[0] == 2


def test_plugins():
    code, out = invoke("plugins")
    assert code == 0
    assert "zhuravlev" in out
    assert "[quantitative]" in out
    assert "datasets" in out


def test_run(tmp_path: Path):
    code, out = invoke("run")
    assert code == 0
    assert "{S₁, S₂, S₅, S₆, S₇}" in out
    assert "Step 1 · r, g, z, d" in out
    assert "17 of 17" in out
    code, out = invoke(
        "run",
        "heart-disease-270",
        "--brief",
        "-r",
        "121",
        "--z-scope",
        "own-class",
        "--save",
        "--runs-dir",
        str(tmp_path / "runs"),
        "-e",
        "csv,datasets",
    )
    assert code == 0, out
    assert "75  by class 42, 33" in out
    assert "⚠ not the literal" in out
    assert "run saved" in out
    assert list((tmp_path / "runs").glob("*/export/csv/summary.csv"))
    code, out = invoke("run", "--k", "5")
    assert code == 2
    assert "outside the k rule" in out
    code, out = invoke(
        "run",
        "-k",
        "5",
        "--k-rule",
        "warn",
        "--metric",
        "euclidean",
        "--normalizer",
        "rank",
        "--brief",
    )
    assert code == 0
    assert "metric euclidean" in out
    assert invoke("run", "--reading", "13")[0] == 2
    code, out = invoke(
        "run", "-c", str(CONFIGS / "heart-disease-270.yaml"), "--brief", "--preset", "literal"
    )
    assert "198" in out


def test_readings_and_sweep():
    code, out = invoke("readings", "--both-z")
    assert code == 0
    assert "6 different training samples from 16 readings" in out
    code, out = invoke("sweep", "heart-disease-270", "--k", "3,5", "-r", "111", "-r", "121:own")
    assert code == 0
    assert "198" in out
    assert "75" in out
    code, out = invoke("sweep", "--k", "1-3")
    assert code == 0


def test_validate():
    code, out = invoke("validate", "--fast")
    assert code == 0
    assert "validation passed" in out
    code, out = invoke("validate", "--against", str(WORKBOOK), "--tolerance", "-1", "--fast")
    assert code == 1
    assert "✗" in out


def test_runs_and_export(tmp_path: Path):
    runs = tmp_path / "runs"
    assert "no runs" in invoke("runs", "--runs-dir", str(runs))[1]
    assert invoke("export", "--runs-dir", str(runs))[0] == 2
    assert invoke("run", "--brief", "--save", "--runs-dir", str(runs))[0] == 0
    code, out = invoke("runs", "--runs-dir", str(runs))
    assert "|D| = 5" in out
    code, out = invoke(
        "export", "--runs-dir", str(runs), "-f", "json,html", "--readings", "--sweep"
    )
    assert code == 0, out
    assert "exported" in out


def test_spheres_command(tmp_path: Path):
    code, out = invoke("spheres")
    assert code == 0
    assert "Step 1 · Enemy spheres" in out
    assert "border object — it can never cover" in out
    assert "Steps 2–5 · Spheres around the selected Sᵢ" in out
    code, out = invoke("spheres", "--object", "S2", "--figure", str(tmp_path / "s2.svg"))
    assert code == 0
    assert "The spheres of S₂" in out
    assert (tmp_path / "s2.svg").is_file()
    code, out = invoke("spheres", "-t", "2", "-f", str(tmp_path / "t2.png"))
    assert code == 0
    assert "Moved to D: S₇ (Step 5)" in out
    assert (tmp_path / "t2.png").is_file()
    code, out = invoke("spheres", "-t", "9")
    assert "queue empty → Step 6" in out
    code, out = invoke("spheres", "-p", "closest", "heart-disease-270", "-t", "1")
    assert code == 0
    assert "⚠ not the literal article reading" in out
    assert invoke("spheres", "--object", "S99")[0] == 2
    assert invoke("spheres", "-t", "0")[0] == 2
    assert invoke("spheres", "-s", "1", "-t", "1")[0] == 2
    code, out = invoke("spheres", "--object", "4", "-f", str(tmp_path / "s4.png"))
    assert code == 0
    assert "The spheres of S₄" in out
    code, out = invoke("spheres", "-f", str(tmp_path / "all.png"))
    assert (tmp_path / "all.png").is_file()
