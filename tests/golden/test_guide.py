"""Acceptance tests: the worked example of the step-by-step guide (7 objects, 4 features).

Every number below is printed in ``resources/Interpretation/ERDR Algorithm – Step-by-Step Guide
with a Worked Example - Opus 5.5.docx`` (Tables 3, 5, 6, 7, 8 and section 11).
"""

import numpy as np
import pytest

from erdr.core.algorithm import Decision, run_erdr
from erdr.core.readings import Readings
from erdr.notation import object_order, object_set
from erdr.services.experiment import ExperimentResult

pytestmark = pytest.mark.golden

TABLE_3 = np.array(
    [
        [0, 2.85, 1.60, 2.95, 3.20, 2.95, 2.65],
        [2.85, 0, 1.25, 1.90, 2.15, 2.30, 1.00],
        [1.60, 1.25, 0, 2.15, 2.40, 2.55, 2.25],
        [2.95, 1.90, 2.15, 0, 0.25, 0.40, 2.10],
        [3.20, 2.15, 2.40, 0.25, 0, 0.65, 2.35],
        [2.95, 2.30, 2.55, 0.40, 0.65, 0, 1.70],
        [2.65, 1.00, 2.25, 2.10, 2.35, 1.70, 0],
    ]
)


def test_table_3_distances(guide_run: ExperimentResult):
    assert np.allclose(guide_run.distances.matrix, TABLE_3, atol=1e-12)


def test_table_5_four_numbers(guide_run: ExperimentResult):
    c = guide_run.result.characteristics
    assert c.r.tolist() == pytest.approx([2.65, 1.00, 2.15, 1.90, 2.15, 2.30, 1.00])
    assert c.g.tolist() == [2, 1, 3, 3, 3, 4, 1]
    assert c.z.tolist() == pytest.approx([2.85, 1.90, 2.15, 1.90, 2.15, 1.70, 2.10])
    assert c.d.tolist() == pytest.approx(
        [0.2 / 5.5, 0.9 / 2.9, 0, 0, 0, 0.6 / 4.0, 1.1 / 3.1], abs=1e-10
    )


def test_table_6_queue(guide_run: ExperimentResult):
    c = guide_run.result.characteristics
    assert object_order(c.priority) == "S₄ → S₃ → S₅ → S₁ → S₆ → S₂ → S₇"


def test_table_7_every_iteration(guide_run: ExperimentResult):
    its = guide_run.result.iterations
    assert [it.selected + 1 for it in its] == [4, 3, 5, 6, 2, 7]
    assert [object_set(it.L) for it in its] == [
        "{S₄, S₅, S₆}",
        "{S₁, S₃}",
        "{S₄, S₅, S₆}",
        "{S₆}",
        "{S₃}",
        "∅",
    ]
    assert [it.decision for it in its] == [
        Decision.CORRECT,
        Decision.CORRECT,
        Decision.CORRECT,
        Decision.MOVE,
        Decision.MOVE,
        Decision.STAY,
    ]
    assert [it.d_size for it in its] == [0, 1, 3, 4, 5, 5]
    assert its[0].blocked_d == pytest.approx(-0.001)
    assert its[3].blocked_d == pytest.approx(-0.1510)


def test_table_8_counters(guide_run: ExperimentResult):
    history = guide_run.result.counter_history()
    assert history.tolist() == [
        [2, 1, 3, 3, 3, 4, 1],
        [2, 1, 3, 2, 2, 3, 1],
        [1, 1, 2, 2, 2, 3, 1],
        [1, 1, 2, 1, 1, 2, 1],
        [1, 1, 2, 1, 1, 2, 1],
        [1, 1, 2, 1, 1, 2, 1],
        [1, 1, 2, 1, 1, 2, 1],
    ]


def test_step_6_result(guide_run: ExperimentResult):
    assert object_set(guide_run.result.training) == "{S₁, S₂, S₄, S₅, S₆}"
    assert object_set(guide_run.result.validation) == "{S₃, S₇}"


@pytest.mark.parametrize(
    ("code", "training"),
    [("211", "{S₃, S₄, S₅, S₇}"), ("121", "{S₁, S₅, S₆}"), ("112", "{S₁, S₂, S₄, S₅, S₇}")],
)
def test_section_11_other_readings(guide_run: ExperimentResult, code: str, training: str):
    result = run_erdr(
        guide_run.distances.matrix,
        guide_run.dataset.class_index,
        3,
        readings=Readings.from_code(code),
    )
    assert object_set(result.training) == training


@pytest.mark.parametrize("epsilon", [1e-6, 0.001, 0.5, 5.0])
def test_epsilon_does_not_change_the_result(guide_run: ExperimentResult, epsilon: float):
    result = run_erdr(guide_run.distances.matrix, guide_run.dataset.class_index, 3, epsilon=epsilon)
    assert result.training.tolist() == guide_run.result.training.tolist()
