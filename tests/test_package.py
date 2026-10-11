"""The package: version, typing marker, logging, notation and the module entry point."""

import io
import json
import logging
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import erdr
from erdr.log import configure_logging
from erdr.notation import changes_text, moves_text, object_order, object_set, subscript


def test_version_and_marker():
    assert erdr.__version__ != "0+unknown"
    assert (files("erdr") / "py.typed").is_file()


def test_notation():
    assert subscript(12) == "₁₂"
    assert object_set([]) == "∅"
    assert object_set([0, 2], ["a", "b", "c"]) == "{a, c}"
    assert object_order([]) == "—"
    assert moves_text([]) == "—"
    assert moves_text([(6, 5)]) == "S₇ (Step 5)"
    assert changes_text([(0, 3, 2)]) == "S₁: 3 → 2"


def test_logging(tmp_path: Path):
    stream = io.StringIO()
    path = tmp_path / "log.jsonl"
    logger = configure_logging("INFO", stream=stream, json_path=path)
    logging.getLogger("erdr.test").info("hello", extra={"k": 3, "label": "ρ"})
    configure_logging("WARNING", stream=stream)  # replaces its own handlers
    assert "hello k=3 label='ρ'" in stream.getvalue()
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["k"] == 3
    assert record["message"] == "hello"
    assert len([h for h in logger.handlers if getattr(h, "_erdr_handler", False)]) == 1


def test_module_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "erdr", "--version"], capture_output=True, text=True, check=True
    )
    assert erdr.__version__ in result.stdout
