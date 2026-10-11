"""Steps 1–6, the readings, the k rule and the cases — including property-based tests."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from erdr.core.algorithm import Decision, run_erdr
from erdr.core.cases import CASES, detect_cases
from erdr.core.characteristics import compute_characteristics, priority_order
from erdr.core.k_rule import largest_defined_k, permitted_k
from erdr.core.readings import (
    CLOSEST,
    LITERAL,
    BlockedCover,
    Readings,
    SelfInL,
    Step5Return,
    ZScope,
    all_readings,
)
from erdr.errors import AlgorithmUndefinedError
from erdr.services.experiment import ExperimentResult

# ---------------------------------------------------------------- readings and the k rule


def test_reading_codes_and_labels():
    assert LITERAL.code == "111"
    assert LITERAL.is_literal
    assert CLOSEST.code == "121"
    assert CLOSEST.z_scope is ZScope.OWN_CLASS
    assert CLOSEST.label == "A=1 B=2 C=1 · z: own class"
    assert Readings.from_code("212") == Readings(
        SelfInL.EXCLUDED, BlockedCover.KEPT, Step5Return.FIRST_MOVE
    )
    assert Readings("excluded", "dropped", "first-move", "own-class").code == "222"  # type: ignore[arg-type]
    assert [r.code for r in all_readings()] == [
        "111",
        "112",
        "121",
        "122",
        "211",
        "212",
        "221",
        "222",
    ]
    assert len(all_readings((ZScope.ALL, ZScope.OWN_CLASS))) == 16
    with pytest.raises(ValueError, match="three digits"):
        Readings.from_code("13")


def test_k_rule():
    rule = permitted_k([3, 4])
    assert rule.ks == (3,)
    assert rule.text == "3"
    assert 3 in rule
    assert permitted_k([150, 120]).text == "3, 5, …, 237"
    assert permitted_k([2, 5]).ks == ()
    assert permitted_k([2, 5]).text == "none"
    assert permitted_k([4, 5]).text == "3, 5"
    assert largest_defined_k([3, 4]) == 6
    assert largest_defined_k([3, 4], ZScope.OWN_CLASS) == 2
    assert largest_defined_k([]) == 0


# ---------------------------------------------------------------- Step 1


def test_characteristics_errors(default_run: ExperimentResult):
    D = default_run.distances.matrix
    y = default_run.dataset.class_index
    with pytest.raises(AlgorithmUndefinedError, match="two classes"):
        compute_characteristics(D, np.zeros(7, dtype=np.int64), 3)
    with pytest.raises(AlgorithmUndefinedError, match="between 1 and 6"):
        compute_characteristics(D, y, 7)
    with pytest.raises(AlgorithmUndefinedError, match="own-class"):
        compute_characteristics(D, y, 3, z_scope=ZScope.OWN_CLASS)
    own = compute_characteristics(D, y, 2, z_scope="own-class")
    assert own.z_scope is ZScope.OWN_CLASS


def test_priority_order():
    d = np.array([0.1, 0.0, 0.0, 0.0])
    r = np.array([1.0, 2.0, 1.0, 1.0])
    assert priority_order(d, r).tolist() == [2, 3, 1, 0]


def test_zero_radius_gives_zero_priority():
    # S₁ and S₂ coincide but belong to different classes: r = 0, g = 0
    D = np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [1.0, 1.0, 0.0]])
    c = compute_characteristics(D, np.array([0, 1, 1]), 1)
    assert c.r[0] == 0.0
    assert c.g[0] == 0
    assert c.z[0] == 0.0  # its nearest neighbour coincides with it
    assert c.d[0] == 0.0  # z + r = 0 → d = 0 (ADR-008)
    result = run_erdr(D, np.array([0, 1, 1]), 1)
    assert result.training.size + result.validation.size == 3


# ---------------------------------------------------------------- Steps 2–6


def test_run_errors(default_run: ExperimentResult):
    D = default_run.distances.matrix
    y = default_run.dataset.class_index
    with pytest.raises(AlgorithmUndefinedError, match="ε"):
        run_erdr(D, y, 3, epsilon=0.0)
    with pytest.raises(ValueError, match="another k"):
        run_erdr(D, y, 3, characteristics=default_run.result.characteristics, readings=CLOSEST)


def test_state_replay_and_queue(default_run: ExperimentResult):
    result = default_run.result
    final = result.state_after(len(result.iterations))
    assert np.array_equal(final.in_d, result.training_mask)
    assert not final.in_queue.any()
    assert result.queue_before(1) == tuple(int(i) for i in result.characteristics.priority)
    assert len(result.queue_before(2)) == result.iterations[1].queue_length
    with pytest.raises(IndexError):
        result.state_after(99)
    assert [m.object for m in result.entry_order] == [6, 0, 4, 1, 5]


def test_reading_c2_stops_at_the_first_move(default_run: ExperimentResult):
    D = default_run.distances.matrix
    y = default_run.dataset.class_index
    result = run_erdr(D, y, 3, readings=Readings.from_code("112"))
    third = result.iterations[2]
    assert third.stopped_early
    assert [m.object for m in third.moves] == [0]


def test_reading_a2_never_puts_the_selected_object_in_l(default_run: ExperimentResult):
    result = run_erdr(
        default_run.distances.matrix,
        default_run.dataset.class_index,
        3,
        readings=Readings.from_code("211"),
    )
    assert all(it.selected not in it.L for it in result.iterations)
    assert any(it.selected in it.excluded for it in result.iterations)


@st.composite
def samples(draw: st.DrawFn) -> tuple[np.ndarray, np.ndarray]:
    m = draw(st.integers(4, 18))
    points = draw(
        st.lists(
            st.tuples(st.integers(0, 6), st.integers(0, 6), st.integers(0, 2)),
            min_size=m,
            max_size=m,
        )
    )
    classes = draw(st.lists(st.integers(0, 1), min_size=m, max_size=m))
    classes[0], classes[1] = 0, 1  # both classes present
    X = np.array(points, dtype=float)
    D = np.round(np.abs(X[:, None, :] - X[None, :, :]).sum(axis=2), 10)
    return D, np.array(classes, dtype=np.int64)


@settings(max_examples=150, deadline=None)
@given(samples(), st.sampled_from(all_readings()), st.integers(1, 3))
def test_invariants_on_random_samples(sample, reading, k):
    D, y = sample
    m = y.size
    result = run_erdr(D, y, min(k, m - 1), readings=reading)
    training, validation = set(result.training.tolist()), set(result.validation.tolist())
    assert training.isdisjoint(validation)
    assert training | validation == set(range(m))
    assert len(result.iterations) <= m
    processed = [it.selected for it in result.iterations]
    assert len(processed) == len(set(processed))  # every object is selected at most once
    moved = [mv.object for it in result.iterations for mv in it.moves]
    assert sorted(moved) == sorted(training)  # D is exactly what moved
    c = result.characteristics
    assert np.all(c.g >= 0)
    assert np.all((c.d >= 0) & (c.d <= 1))
    for it in result.iterations:
        assert set(it.L) <= set(it.covering)
        if it.decision is Decision.MOVE:
            assert [mv.object for mv in it.moves] == [it.selected]
        if reading.step5_return is Step5Return.FIRST_MOVE:
            assert sum(1 for mv in it.moves if mv.step == 5) <= 1
        assert all(change.after == change.before - 1 >= 1 for change in it.changes)
    # ε only marks processed objects
    again = run_erdr(D, y, min(k, m - 1), readings=reading, epsilon=3.7)
    assert again.training.tolist() == result.training.tolist()
    assert len(detect_cases(result)) == len(CASES)


# ---------------------------------------------------------------- cases


def test_cases_of_the_default_run(default_run: ExperimentResult):
    found = {case.case.number: case for case in default_run.cases}
    assert [c.number for c in CASES] == list(range(1, 18))
    assert all(case.occurs for case in found.values())
    assert found[1].first == "k rule"
    assert found[6].iterations == (4,)
    assert found[9].iterations == (2, 3)
    assert found[10].iterations == (1, 2, 3)
    assert found[15].first == "3"
    assert {c.kind for c in CASES} == {"branch", "extra"}


def test_cases_that_do_not_occur():
    # two pairs far apart: no k is permitted (min|Kᵢ| = 2), every object is a border object
    positions = np.array([0.0, 1.0, 10.0, 11.0])
    D = np.abs(positions[:, None] - positions[None, :])
    found = {
        case.case.number: case for case in detect_cases(run_erdr(D, np.array([0, 0, 1, 1]), 1))
    }
    assert not found[1].occurs
    assert found[1].first == "—"
    assert found[3].occurs  # g = 2 for every object
    assert not found[2].occurs
    assert not found[4].occurs  # the ties of d are decided by the index, never by r
    assert found[5].occurs
    assert found[15].iterations == (1, 2)  # each Step 5 moves both members of L
    assert not found[8].occurs
    assert not found[16].occurs  # F is empty
    assert not found[17].occurs
