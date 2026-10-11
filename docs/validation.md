# Validation

## Against the ERDR workbook

`erdr validate` (`erdr.services.validation.validate_workbook`) reads the inputs from the workbook
itself — the 7 selected objects (*Dataset*), k and ε, the readings A, B, C (*Parameters*) — runs
the engine and compares every computed sheet with the workbook's cached cell values (absolute
tolerance 1e-9 for numbers, equality for text and integers):

| Sheet | Checks | What is compared |
|---|---|---|
| Parameters | 5 | N, \|K1\|, \|K2\|, k_max, the permitted k |
| Dataset | 7 | each object equals its source row of *Source Dataset (270)* |
| Normalized Dataset | 103 | every unified value, min and max |
| Zhuravlev Distances | 147 | ρ, ρ_I, ρ_J for every pair |
| Sorted Neighbors | 42 | the rank matrix |
| ERDR Characteristics | 119 | nearest enemy, r, g, enemy rank, k-th neighbour, z, z − r, d, priority, the own-class list, the sphere matrix |
| Priority Queue | 14 | the order and the criterion of every adjacent pair |
| Hyperspheres (Step 1) | 235 | every enemy sphere (r, nearest enemy, own class inside and on it, enemies on it, g, the closed count, its members, its reading) and k-sphere (k-th neighbour, z, members by class, rank e, q, d from q, the relation of the spheres and what it means), the spheres that contain every object with its L, and the summary with its four checks |
| ERDR Trace | 214 | every iteration (Sᵢ, d, r, \|L\|, L, decision, counters, moves, sizes), g and F after every iteration, every object's route |
| Hyperspheres (Iterations) | 805 | the overview of every iteration (Sᵢ, candidates, spheres that contain Sᵢ, in D, L, decision) and every block: each object's class, F, own class, ρ(Sⱼ, Sᵢ), r(Sⱼ), r − ρ, containment, g before and after, g > 1, readings A and B, L, move and role; the block summary; the Step 6 blocks |
| Hypersphere Data | 950 | the diagrams' geometry: ρ_max, the angle step, every object's diagram (titles, ranks, ρ, angles, positions, counted in g), the strips, the radius plane and its lines of equal d, every iteration diagram (title, Sᵢ, ranks, ρ, r, L, counters, moves) |
| Training & Validation | 45 | sample, iterations, entry step, counter decreases, class composition, D and F |
| Case Checklist | 34 | every case: occurs, first occurrence |
| Readings (Switches) | 64 | all eight readings: order, D, F, sizes, iterations |
| Article Table 1 Check | 90 | five readings × k = 3, 5, 7, 13, 17 on all 270 objects (sizes and classes) and \|D\| for every odd k = 3 … 41 |
| Validation | 53 | the workbook's own checks of the engine |

All **2,927** checks pass. The CI runs `erdr validate` on every push.

## Golden tests

`tests/golden` holds the acceptance tests (marker `golden`):

- `test_workbook.py` — the validator, plus the workbook's *Validation* values written into the
  test (r, g, z, d, every iteration, D, F, all eight readings), so a change shows up even without
  the workbook;
- `test_guide.py` — every number of the step-by-step guide's worked example (Tables 3, 5, 6, 7,
  8 and the readings of section 11), and that ε does not change the result;
- `test_article_table1.py` — all 270 objects: the five readings at k = 3, 5, 7, 13, 17 with their
  class composition, and \|D\| for every odd k = 3 … 41 (marker `slow`).

Property-based tests (hypothesis) check on random samples that D and F partition E₀, that every
object is selected at most once, that D is exactly what moved, that L only holds covering objects,
that reading C = 2 moves at most one object per Step 5, that counters only fall by one and never
below 1, and that ε does not matter. On random samples with ties and every reading, the sphere view
holds too: g is the own class strictly inside the enemy sphere (and Sᵢ when r > 0), no enemy lies
inside it, d equals (1 − q)/(1 + q), and in every iteration the sphere test alone gives exactly L.
A copy of the workbook with three changed hypersphere values fails exactly those three checks.

## Findings for the article

- The literal reading of §1.1 keeps 165–201 of the 270 objects in D (61–74 %); the article's
  Table 1 reports 75–104 (28–39 %).
- None of the readings reproduces Table 1 exactly; the closest — processed objects stop covering
  (B = 2) and z(Sᵢ, k) from the own class — differs by 0 to 16 objects (k = 3: 75 = 75).
- |L| = 0 is not described in the text; the literal reading leaves Sᵢ in F.
- For Sⱼ ≠ Sᵢ the condition g(Sⱼ) > 1 in L always holds when Sⱼ covers Sᵢ (an object whose g falls
  to 1 leaves F at once), so it only decides whether Sᵢ itself is in L.
- g is written as a set in the article but used as its size; self-counting is confirmed by the
  text.

These are recorded as ADR-017.
