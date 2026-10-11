"""Run folders: a saved ERDR run that can be listed, reopened and repeated (ADR-011).

``runs/<YYYYMMDD_HHMMSS>_<config hash[:8]>/``:

``manifest.yaml``
    versions, timings, hashes of the configuration, the dataset and every file, the result in
    brief (D, F, iterations) and the warnings;
``config.yaml``
    the configuration that was run;
``dataset.json``
    the sample E₀ exactly (names, types, ids, labels, values) — the run does not depend on the
    dataset file it was read from;
``result.json``
    Step 1 (r, g, z, d), the trace of every iteration, D and F;
``training.dat`` / ``.csv``, ``validation.dat`` / ``.csv``
    the two samples in the author's extended layout (``output.dataset_formats``).

:func:`load_run` repeats the run from ``config.yaml`` and ``dataset.json`` and checks that it gives
the stored D and F.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from erdr import __version__
from erdr.config.io import dumps, load_config
from erdr.data.schema import Dataset, FeatureType
from erdr.data.writers import write_extended
from erdr.errors import ERDRError
from erdr.notation import object_set
from erdr.services.experiment import ExperimentResult, run_experiment

MANIFEST = "manifest.yaml"
CONFIG = "config.yaml"
DATASET = "dataset.json"
RESULT = "result.json"


class RunError(ERDRError, RuntimeError):
    """A run folder is missing, incomplete, or does not repeat its stored result."""


@dataclass(frozen=True)
class RunInfo:
    """A run folder in brief (``erdr runs`` and the GUI)."""

    folder: Path
    run_id: str
    started: str
    dataset: str
    k: int
    reading: str
    training_size: int
    validation_size: int


def run_id(experiment: ExperimentResult) -> str:
    """``20261011_101500_0a1b2c3d`` — start time (UTC) and the configuration hash."""
    return f"{experiment.started:%Y%m%d_%H%M%S}_{experiment.config_hash[:8]}"


def dataset_to_data(dataset: Dataset) -> dict[str, Any]:
    """The dataset as plain JSON data (floats keep every bit: JSON uses their shortest repr)."""
    return {
        "name": dataset.name,
        "source": dataset.source,
        "feature_names": list(dataset.feature_names),
        "feature_types": [t.value for t in dataset.feature_types],
        "object_ids": list(dataset.object_ids),
        "labels": [v.item() for v in dataset.y],
        "categories": {k: list(v) for k, v in dataset.categories.items()},
        "X": dataset.X.tolist(),
    }


def dataset_from_data(data: dict[str, Any]) -> Dataset:
    """Inverse of :func:`dataset_to_data`."""
    return Dataset(
        X=np.array(data["X"], dtype=np.float64),
        y=data["labels"],
        feature_types=tuple(FeatureType(t) for t in data["feature_types"]),
        feature_names=tuple(data["feature_names"]),
        object_ids=tuple(data["object_ids"]),
        name=data["name"],
        categories={k: tuple(v) for k, v in data.get("categories", {}).items()},
        source=data.get("source"),
    )


def result_to_data(experiment: ExperimentResult) -> dict[str, Any]:
    """Step 1, the trace and the result as plain JSON data (0-based indices)."""
    result = experiment.result
    c = result.characteristics
    return {
        "k": c.k,
        "reading": result.readings.code,
        "z_scope": result.readings.z_scope.value,
        "epsilon": result.epsilon,
        "characteristics": {
            "r": c.r.tolist(),
            "g": c.g.tolist(),
            "z": c.z.tolist(),
            "d": c.d.tolist(),
            "nearest_enemy": c.nearest_enemy.tolist(),
            "kth_neighbour": c.kth_neighbour.tolist(),
            "priority": c.priority.tolist(),
        },
        "iterations": [
            {
                "t": it.number,
                "selected": it.selected,
                "queue_length": it.queue_length,
                "d": it.d,
                "r": it.r,
                "L": list(it.L),
                "covering": list(it.covering),
                "excluded": list(it.excluded),
                "decision": it.decision.value,
                "blocked_d": it.blocked_d,
                "changes": [[ch.object, ch.before, ch.after] for ch in it.changes],
                "moves": [[mv.object, mv.step] for mv in it.moves],
                "stopped_early": it.stopped_early,
            }
            for it in result.iterations
        ],
        "training": result.training.tolist(),
        "validation": result.validation.tolist(),
        "cases": {str(case.case.number): case.occurs for case in experiment.cases},
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def save_run(experiment: ExperimentResult, runs_dir: Path | None = None) -> Path:
    """Write ``experiment`` to a new run folder and return it."""
    root = Path(runs_dir if runs_dir is not None else experiment.config.output.runs_dir)
    base = run_id(experiment)
    folder = root / base
    suffix = 1
    while folder.exists():
        suffix += 1
        folder = root / f"{base}-{suffix}"
    folder.mkdir(parents=True)

    (folder / CONFIG).write_text(dumps(experiment.config), encoding="utf-8", newline="\n")
    _write_json(folder / DATASET, dataset_to_data(experiment.dataset))
    _write_json(folder / RESULT, result_to_data(experiment))
    for fmt in experiment.config.output.dataset_formats:
        write_extended(experiment.training_dataset, folder / f"training.{fmt}")
        write_extended(experiment.validation_dataset, folder / f"validation.{fmt}")

    names = experiment.object_names
    result = experiment.result
    manifest = {
        "run_id": folder.name,
        "erdr": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": version("numpy"),
        "started": experiment.started.isoformat(),
        "seconds": round(experiment.seconds, 6),
        "config_hash": experiment.config_hash,
        "dataset": {
            "name": experiment.dataset.name,
            "source": experiment.dataset.source,
            "content_hash": experiment.dataset_hash,
            "m": experiment.dataset.m,
            "n": experiment.dataset.n,
            "class_sizes": list(experiment.dataset.class_sizes),
        },
        "result": {
            "k": experiment.k,
            "reading": result.readings.label,
            "iterations": len(result.iterations),
            "training": object_set(result.training, names),
            "validation": object_set(result.validation, names),
            "training_size": int(result.training.size),
            "validation_size": int(result.validation.size),
        },
        "notes": list(experiment.notes),
        "warnings": list(experiment.warnings),
        "files": {
            path.name: _sha256(path) for path in sorted(folder.iterdir()) if path.name != MANIFEST
        },
    }
    (folder / MANIFEST).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return folder


def read_manifest(folder: Path) -> dict[str, Any]:
    """The manifest of a run folder.

    Raises:
        RunError: The folder has no readable manifest.
    """
    path = folder / MANIFEST
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise RunError(f"{folder}: no readable {MANIFEST} ({error})") from error
    if not isinstance(data, dict):
        raise RunError(f"{folder}: {MANIFEST} is not a mapping")
    return data


def load_run(folder: Path) -> ExperimentResult:
    """Repeat a saved run and check that it gives the stored D and F.

    Raises:
        RunError: Files are missing, or the repeated run differs from the stored result.
    """
    for name in (CONFIG, DATASET, RESULT):
        if not (folder / name).is_file():
            raise RunError(f"{folder}: {name} is missing — not a run folder")
    config = load_config(folder / CONFIG)
    dataset = dataset_from_data(json.loads((folder / DATASET).read_text(encoding="utf-8")))
    stored = json.loads((folder / RESULT).read_text(encoding="utf-8"))
    repeated = run_experiment(config, dataset)
    if (
        repeated.result.training.tolist() != stored["training"]
        or repeated.result.validation.tolist() != stored["validation"]
    ):
        raise RunError(f"{folder}: repeating the run gives another training sample")
    return repeated


def list_runs(runs_dir: Path) -> list[RunInfo]:
    """The run folders of ``runs_dir``, newest first (folders without a manifest are skipped)."""
    if not runs_dir.is_dir():
        return []
    found: list[RunInfo] = []
    for folder in sorted(runs_dir.iterdir(), reverse=True):
        if not (folder / MANIFEST).is_file():
            continue
        try:
            data = read_manifest(folder)
            result = data["result"]
            found.append(
                RunInfo(
                    folder=folder,
                    run_id=str(data["run_id"]),
                    started=str(data["started"]),
                    dataset=str(data["dataset"]["name"]),
                    k=int(result["k"]),
                    reading=str(result["reading"]),
                    training_size=int(result["training_size"]),
                    validation_size=int(result["validation_size"]),
                )
            )
        except (RunError, KeyError, TypeError, ValueError):
            continue
    return found


def latest_run(runs_dir: Path) -> Path | None:
    """The newest run folder of ``runs_dir``, or ``None``."""
    runs = list_runs(runs_dir)
    return runs[0].folder if runs else None


def started_at(folder: Path) -> datetime | None:
    """The start time recorded in a run's manifest, if readable."""
    try:
        return datetime.fromisoformat(str(read_manifest(folder)["started"]))
    except (RunError, KeyError, ValueError):
        return None
