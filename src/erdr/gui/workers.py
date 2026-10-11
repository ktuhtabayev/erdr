"""Background work: a run, an analysis or an export in a worker thread.

The interface never blocks — on the 270-object dataset a k sweep takes seconds. A :class:`Task`
runs one plain function of the services in a :class:`~PySide6.QtCore.QThread` and reports its
result or its error back to the GUI thread through signals.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from erdr.errors import ERDRError

logger = logging.getLogger(__name__)


class Task(QThread):
    """Runs ``function()`` in a worker thread."""

    succeeded = Signal(object)
    """The function's return value."""
    failed = Signal(str)
    """A user-facing message (deliberate errors) or a traceback (bugs)."""
    progressed = Signal(int, int)
    """(done, total) from a progress callback."""

    def __init__(self, function: Callable[..., Any], parent: QObject | None = None) -> None:
        """Prepare the task; :meth:`start` runs it."""
        super().__init__(parent)
        self._function = function

    def report(self, done: int, total: int) -> None:
        """A progress callback for the services (thread-safe: it only emits a signal)."""
        self.progressed.emit(done, total)

    def run(self) -> None:
        """Run the function (in the worker thread)."""
        try:
            result = self._function()
        except ERDRError as error:
            self.failed.emit(str(error))
        except Exception:  # a bug: show the traceback instead of losing it in the thread
            logger.exception("background task failed")
            self.failed.emit(traceback.format_exc())
        else:
            self.succeeded.emit(result)


class TaskRunner(QObject):
    """Keeps the running tasks alive and lets a page wait for them (tests, closing)."""

    def __init__(self, parent: QObject | None = None) -> None:
        """No task yet."""
        super().__init__(parent)
        self._tasks: list[Task] = []

    def start(
        self,
        function: Callable[..., Any],
        on_success: Callable[[Any], None],
        on_failure: Callable[[str], None],
        on_progress: Callable[[int, int], None] | None = None,
        *,
        with_progress: bool = False,
    ) -> Task:
        """Run ``function`` in a new task; ``with_progress`` passes it the task's callback."""
        holder: list[Task] = []

        def call() -> Any:
            return function(holder[0].report) if with_progress else function()

        task = Task(call, self)
        holder.append(task)
        task.succeeded.connect(on_success)
        task.failed.connect(on_failure)
        if on_progress is not None:
            task.progressed.connect(on_progress)
        task.finished.connect(lambda: self._forget(task))
        self._tasks.append(task)
        task.start()
        return task

    def _forget(self, task: Task) -> None:
        if task in self._tasks:
            self._tasks.remove(task)
        task.deleteLater()

    def busy(self) -> bool:
        """Whether a task is running."""
        return any(task.isRunning() for task in self._tasks)

    def wait(self, milliseconds: int = 60_000) -> bool:
        """Wait for every running task; returns whether all ended in time."""
        return all(task.wait(milliseconds) for task in list(self._tasks))
