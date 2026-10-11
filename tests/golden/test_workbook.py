"""Acceptance tests: the ERDR workbook ``ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx``.

The validator compares every computed sheet with the workbook's cached cells; the explicit values
below are the workbook's *Validation* sheet, so a change shows up even without the workbook.
"""

import pytest

from erdr.core.algorithm import run_erdr
from erdr.core.readings import all_readings
from erdr.notation import object_order, object_set
from erdr.services.experiment import ExperimentResult
from erdr.services.validation import validate_workbook
from tests.conftest import WORKBOOK

pytestmark = pytest.mark.golden

R = (5.60708061, 7.4699698919, 5.60708061, 3.7071187508, 7.1117040273, 3.7071187508, 3.9109813746)
G = (3, 4, 3, 1, 3, 1, 2)
Z = (5.60708061, 6.3691657565, 5.60708061, 6.2175670209, 7.1117040273, 5.2172783643, 5.0314314939)
D = (0.0, 0.0795428388, 0.0, 0.2529498997, 0.0, 0.1692169896, 0.1252961741)
READINGS = {
    "111": ("{S₁, S₂, S₅, S₆, S₇}", "S₁ → S₃ → S₅ → S₂ → S₆ → S₄"),
    "112": ("{S₁, S₄, S₅, S₆, S₇}", "S₁ → S₃ → S₅ → S₂ → S₆ → S₄"),
    "121": ("{S₂, S₅, S₇}", "S₁ → S₃ → S₅ → S₂ → S₆ → S₄"),
    "122": ("{S₂, S₅, S₇}", "S₁ → S₃ → S₅ → S₂ → S₆ → S₄"),
    "211": ("{S₁, S₃, S₄, S₅}", "S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄"),
    "212": ("{S₁, S₃, S₄}", "S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄"),
    "221": ("{S₃, S₅}", "S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄"),
    "222": ("{S₃, S₅}", "S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄"),
}


def test_every_sheet_of_the_workbook_matches():
    report = validate_workbook(WORKBOOK)
    assert report.passed, [
        f"{c.section}: {c.name}: {c.expected!r} vs {c.actual!r}" for c in report.failures[:10]
    ]
    sections = {name: total for name, total, _ in report.sections()}
    assert sections["Validation"] == 53  # the workbook's own 53 checks
    assert sections["Article Table 1 Check"] == 90
    assert len(report.checks) == 937


def test_step1_values(default_run: ExperimentResult):
    c = default_run.result.characteristics
    assert c.r.tolist() == pytest.approx(R, abs=1e-9)
    assert c.g.tolist() == list(G)
    assert c.z.tolist() == pytest.approx(Z, abs=1e-9)
    assert c.d.tolist() == pytest.approx(D, abs=1e-9)
    assert object_order(c.priority) == "S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄"
    assert c.decided_by()[:2] == ("index", "r")  # both tie rules of Step 2 occur


def test_iterations_and_result(default_run: ExperimentResult):
    result = default_run.result
    assert [it.selected + 1 for it in result.iterations] == [1, 3, 5, 2, 6, 4]
    assert [len(it.L) for it in result.iterations] == [3, 2, 3, 1, 1, 0]
    moves = [[(m.object + 1, m.step) for m in it.moves] for it in result.iterations]
    assert moves == [[], [(7, 5)], [(1, 5), (5, 5)], [(2, 4)], [(6, 4)], []]
    assert object_set(result.training) == "{S₁, S₂, S₅, S₆, S₇}"
    assert object_set(result.validation) == "{S₃, S₄}"
    assert sum(case.occurs for case in default_run.cases) == 17


@pytest.mark.parametrize("reading", all_readings(), ids=lambda r: r.code)
def test_all_eight_readings(default_run: ExperimentResult, reading):
    result = run_erdr(
        default_run.distances.matrix, default_run.dataset.class_index, 3, readings=reading
    )
    training, order = READINGS[reading.code]
    assert object_set(result.training) == training
    assert object_order(result.processing_order) == order
