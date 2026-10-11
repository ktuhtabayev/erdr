"""Acceptance tests: all 270 objects (sheet *Article Table 1 Check* of the ERDR workbook)."""

import pytest

from erdr.core.readings import CLOSEST, LITERAL, Readings, ZScope
from erdr.data import Dataset
from erdr.services.analysis import sweep_k

pytestmark = [pytest.mark.golden, pytest.mark.slow]

READINGS = {
    "literal": LITERAL,
    "B = 2": Readings.from_code("121"),
    "own-class z": Readings.from_code("111", ZScope.OWN_CLASS),
    "closest": CLOSEST,
    "A = 2": Readings.from_code("211"),
}
TABLE_1 = {  # k → reading → (|D|, |D ∩ K1|, |D ∩ K2|)
    3: {
        "literal": (198, 111, 87),
        "B = 2": (81, 46, 35),
        "own-class z": (194, 105, 89),
        "closest": (75, 42, 33),
        "A = 2": (124, 62, 62),
    },
    5: {
        "literal": (190, 110, 80),
        "B = 2": (73, 40, 33),
        "own-class z": (192, 106, 86),
        "closest": (76, 44, 32),
        "A = 2": (121, 66, 55),
    },
    7: {
        "literal": (201, 114, 87),
        "B = 2": (72, 39, 33),
        "own-class z": (202, 115, 87),
        "closest": (71, 38, 33),
        "A = 2": (130, 78, 52),
    },
    13: {
        "literal": (177, 97, 80),
        "B = 2": (84, 50, 34),
        "own-class z": (179, 98, 81),
        "closest": (88, 50, 38),
        "A = 2": (106, 59, 47),
    },
    17: {
        "literal": (165, 96, 69),
        "B = 2": (90, 52, 38),
        "own-class z": (173, 96, 77),
        "closest": (94, 52, 42),
        "A = 2": (100, 59, 41),
    },
}
SWEEP = {  # k → (|D| literal, |D| closest), odd k = 3 … 41
    3: (198, 75),
    5: (190, 76),
    7: (201, 71),
    9: (192, 81),
    11: (180, 85),
    13: (177, 88),
    15: (174, 90),
    17: (165, 94),
    19: (168, 94),
    21: (162, 94),
    23: (158, 90),
    25: (158, 91),
    27: (160, 90),
    29: (157, 89),
    31: (163, 90),
    33: (157, 92),
    35: (162, 92),
    37: (162, 91),
    39: (159, 91),
    41: (159, 91),
}


def test_five_readings_against_table_1(heart270: Dataset):
    rows = sweep_k(heart270, ks=list(TABLE_1), readings=list(READINGS.values()))
    name = {reading: key for key, reading in READINGS.items()}
    found = {
        (row.k, name[row.readings]): (row.training_size, *row.training_by_class) for row in rows
    }
    expected = {(k, key): value for k, values in TABLE_1.items() for key, value in values.items()}
    assert found == expected


def test_sweep_over_odd_k(heart270: Dataset):
    rows = sweep_k(heart270, ks=list(SWEEP), readings=[LITERAL, CLOSEST])
    found: dict[int, list[int]] = {}
    for row in rows:
        found.setdefault(row.k, []).append(row.training_size)
    assert {k: tuple(v) for k, v in found.items()} == SWEEP
    assert all(row.permitted for row in rows)
