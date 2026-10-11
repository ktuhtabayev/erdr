"""Fixtures of the GUI tests: a main window in a temporary working folder, messages captured."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from erdr.gui.window import MainWindow
from tests.conftest import ROOT

RUN_TIMEOUT = 120_000


@pytest.fixture
def messages() -> list[str]:
    """What the window reported to the user."""
    return []


@pytest.fixture
def window(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, messages: list[str]
) -> Iterator[MainWindow]:
    """The main window; the dataset folder is the project's, runs and exports go to tmp_path."""
    monkeypatch.chdir(ROOT)
    created = MainWindow()
    created.show_message = lambda title, text: messages.append(f"{title}: {text}")  # type: ignore[method-assign]
    created.run_page.runs_dir = tmp_path / "runs"
    created.export_page.folder.setText(str(tmp_path / "exports"))
    qtbot.addWidget(created)
    yield created
    created.wait()
    created.run_page.log_bridge.detach()


Run = Callable[[MainWindow], None]


@pytest.fixture
def run(qtbot: QtBot) -> Run:
    """Run ERDR in a window's worker thread and wait for the result."""

    def start(window: MainWindow) -> None:
        with qtbot.waitSignal(window.run_page.finished, timeout=RUN_TIMEOUT) as blocker:
            window.run_page.start()
        assert blocker.args == [True]
        assert window.state.result is not None

    return start


@pytest.fixture
def loaded(window: MainWindow) -> MainWindow:
    """A window with the default dataset loaded."""
    assert window.dataset_page.load("default")
    return window
