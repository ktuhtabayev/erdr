"""The hypersphere explorer of the Results page: Steps 1–5 as spheres, step by step.

The sheets *Hyperspheres (Step 1)* and *Hyperspheres (Iterations)*, object by object and
iteration by iteration.

Choose a view — the two spheres of an object, the spheres around the selected object of an
iteration, the neighbourhood strips or the radius plane — and step through the objects or the
iterations with ◀ ▶ or *Play*. The figure and the table under it are the exporters' own
(ADR-012, ADR-020); the GUI computes nothing.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from erdr.export.figures import (
    iteration_spheres_figure,
    new_figure,
    object_spheres_figure,
    run_figure,
)
from erdr.export.tables import (
    Table,
    enemy_spheres_table,
    iteration_detail_table,
    k_spheres_table,
    object_spheres_table,
)
from erdr.gui.widgets import FigureView, Legend, TableView, hint
from erdr.notation import object_set
from erdr.services.experiment import ExperimentResult

VIEWS = (
    ("object", "The spheres of an object (Step 1)"),
    ("iteration", "The spheres around Sᵢ in an iteration (Steps 2–5)"),
    ("strips", "Neighbourhood strips of every object (Step 1)"),
    ("plane", "Radius plane (r, z) — d of every object (Step 1)"),
)
"""The views of the explorer: key → name."""
PLAY_MILLISECONDS = 1600
"""How long *Play* shows every object or iteration."""
_HELP = {
    "object": "Sᵢ in the centre, every other object at its true distance ρ (neighbour order "
    "clockwise from the top). Solid circle: the enemy sphere r(Sᵢ) — g(Sᵢ) counts the own-class "
    "objects strictly inside (filled); dashed: the k-sphere z(Sᵢ, k); d compares the two radii.",
    "iteration": "The selected Sᵢ in the centre, every object at its true distance ρ(Sⱼ, Sᵢ). "
    "Every own-class object carries its enemy sphere: the spheres in F that contain Sᵢ "
    "(r(Sⱼ) − ρ(Sⱼ, Sᵢ) > 0) and whose g > 1 form L (solid, yellow); dashed: in F, not in L; "
    "dotted: already in D. Filled markers are in D, hollow ones in F.",
    "strips": "One strip per object, the first of the Step 2 queue at the top: every neighbour at "
    "its distance; the solid tick is r, the dashed tick z — the closer they are, the smaller d.",
    "plane": "Every object at (r, z). d is constant on every line through the origin: on the "
    "diagonal z = r (d = 0, first in the queue); objects on one point tie in d and r.",
}


class SpheresExplorer(QWidget):
    """Steps 1–5 as hyperspheres, object by object and iteration by iteration."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """The controls, the figure and the table of the view on show."""
        super().__init__(parent)
        self.result: ExperimentResult | None = None
        self.table: Table | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        self.view_choice = QComboBox()
        for key, name in VIEWS:
            self.view_choice.addItem(name, key)
        self.previous_button = QPushButton("◀")
        self.previous_button.setToolTip("The previous object or iteration")
        self.item_choice = QComboBox()
        self.item_choice.setMinimumContentsLength(28)
        self.next_button = QPushButton("▶")
        self.next_button.setToolTip("The next object or iteration")
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("primary")
        self.play_button.setCheckable(True)
        self.play_button.setToolTip("Step through the objects or iterations by themselves")
        row.addWidget(QLabel("View:"))
        row.addWidget(self.view_choice)
        row.addSpacing(12)
        for widget in (self.previous_button, self.item_choice, self.next_button, self.play_button):
            row.addWidget(widget)
        row.addStretch(1)
        layout.addLayout(row)
        self.help = hint("")
        layout.addWidget(self.help)

        splitter = QSplitter(Qt.Orientation.Vertical)
        upper = QSplitter(Qt.Orientation.Horizontal)  # the figure, and what it shows in words
        self.figure_view = FigureView()
        upper.addWidget(self.figure_view)
        self.summary = QLabel()
        self.summary.setObjectName("note")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.summary.setMinimumWidth(220)
        side = QScrollArea()
        side.setWidget(self.summary)
        side.setWidgetResizable(True)
        side.setFrameShape(QFrame.Shape.NoFrame)
        upper.addWidget(side)
        upper.setStretchFactor(0, 3)
        upper.setStretchFactor(1, 1)
        upper.setSizes([960, 340])
        splitter.addWidget(upper)
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 4, 0, 0)
        self.table_view = TableView()
        self.legend = Legend()
        lower_layout.addWidget(self.table_view, 1)
        lower_layout.addWidget(self.legend)
        splitter.addWidget(lower)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([500, 300])
        layout.addWidget(splitter, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(PLAY_MILLISECONDS)
        self.timer.timeout.connect(self._advance)
        self.view_choice.currentIndexChanged.connect(lambda _: self._view_changed())
        self.item_choice.currentIndexChanged.connect(lambda _: self._draw())
        self.previous_button.clicked.connect(lambda: self.step(-1))
        self.next_button.clicked.connect(lambda: self.step(1))
        self.play_button.toggled.connect(self.play)
        self._view_changed()

    # ------------------------------------------------------------------ state

    @property
    def view(self) -> str:
        """The key of the view on show (``object``, ``iteration``, ``strips``, ``plane``)."""
        return str(self.view_choice.currentData())

    def show_result(self, result: ExperimentResult | None) -> None:
        """Explore ``result`` (nothing for ``None``)."""
        self.play(False)
        self.result = result
        self._fill_items()
        self._draw()

    def show_object(self, i: int) -> None:
        """The spheres of object ``i`` (0-based)."""
        self._select("object", i)

    def show_iteration(self, t: int) -> None:
        """The spheres of iteration ``t`` (1-based; past the last: Step 6)."""
        self._select("iteration", t - 1)

    def _select(self, view: str, index: int) -> None:
        self.view_choice.setCurrentIndex(self.view_choice.findData(view))
        if 0 <= index < self.item_choice.count():
            self.item_choice.setCurrentIndex(index)

    def _view_changed(self) -> None:
        self.play(False)
        self.help.setText(_HELP[self.view])
        self._fill_items()
        self._draw()

    def _fill_items(self) -> None:
        """The objects (in index order) or the iterations (with Step 6) of the view."""
        result = self.result
        stepped = self.view in ("object", "iteration")
        for widget in (self.previous_button, self.item_choice, self.next_button, self.play_button):
            widget.setEnabled(stepped and result is not None)
        self.item_choice.blockSignals(True)
        self.item_choice.clear()
        if result is not None and self.view == "object":
            c = result.result.characteristics
            for i, name in enumerate(result.object_names):
                self.item_choice.addItem(
                    f"{name}  ·  queue {int(c.position[i])}  ·  d {float(c.d[i]):.3f}", i
                )
        elif result is not None and self.view == "iteration":
            names = result.object_names
            for it in result.result.iterations:
                self.item_choice.addItem(
                    f"t = {it.number}  ·  Sᵢ = {names[it.selected]}  ·  |L| = {len(it.L)}",
                    it.number,
                )
            self.item_choice.addItem("Step 6  ·  the result", len(result.result.iterations) + 1)
        self.item_choice.blockSignals(False)

    # ------------------------------------------------------------------ stepping

    def step(self, direction: int) -> None:
        """Show the previous (−1) or the next (+1) object or iteration."""
        count = self.item_choice.count()
        if count == 0:
            return
        self.item_choice.setCurrentIndex((self.item_choice.currentIndex() + direction) % count)

    def play(self, on: bool) -> None:
        """Start or stop stepping through the objects or iterations by themselves."""
        if on and self.item_choice.count() > 1 and self.view in ("object", "iteration"):
            if self.item_choice.currentIndex() == self.item_choice.count() - 1:
                self.item_choice.setCurrentIndex(0)
            self.timer.start()
        else:
            self.timer.stop()
            on = False
        if self.play_button.isChecked() != on:
            self.play_button.blockSignals(True)
            self.play_button.setChecked(on)
            self.play_button.blockSignals(False)
        self.play_button.setText("Pause" if on else "Play")

    def _advance(self) -> None:
        """One step of *Play*; it stops on the last object or at Step 6."""
        if self.item_choice.currentIndex() >= self.item_choice.count() - 1:
            self.play(False)
            return
        self.step(1)

    # ------------------------------------------------------------------ drawing

    def _draw(self) -> None:
        result = self.result
        if result is None:
            self.figure_view.show_figure(new_figure())
            self.table_view.setModel(None)
            self.legend.show_table(None)
            self.summary.setText("Run ERDR to explore its spheres.")
            self.table = None
            return
        view = self.view
        data = self.item_choice.currentData()
        lines: tuple[tuple[str, str], ...] = ()
        if view == "object":
            i = int(data) if data is not None else 0
            figure = object_spheres_figure(result, i)
            table = object_spheres_table(result, i)
        elif view == "iteration":
            t = int(data) if data is not None else 1
            figure = iteration_spheres_figure(result, t)
            table = iteration_detail_table(result, t)
            lines = tuple(table.extra.items())
            if t > len(result.result.iterations):
                names = result.object_names
                lines = (
                    ("Training sample D", object_set(result.result.training, names)),
                    ("Validation sample F", object_set(result.result.validation, names)),
                )
        elif view == "strips":
            figure = run_figure("strips", result)
            table = enemy_spheres_table(result)
        else:
            figure = run_figure("radius-plane", result)
            table = k_spheres_table(result)
        self.figure_view.show_figure(figure)
        self.table = table
        labels = result.dataset.classes
        self.table_view.show_table(table, class_labels=labels)
        self.legend.show_table(table, labels)
        heading = f"<b>{html.escape(table.title)}</b>"
        details = "".join(
            f"<br>{html.escape(name)}: <b>{html.escape(value)}</b>" for name, value in lines
        )
        self.summary.setText(heading + details)
