# ERDR — Enemy-Radius Density Reduction

**ERDR** is the algorithm of §1.1 of N. A. Ignatev's article *«Ансамбли алгоритмов распознавания
на основе синтетических признаков и контекстов k ближайших соседей»*. It divides a labelled sample
E₀ into a **training sample D** and a **validation sample F = E₀ \ D**, using for every object the
distance to the nearest object of the other class (its *enemy radius*) together with the local
density of its own class inside that radius.

This project implements ERDR as a Python library, the `erdr` command line, a desktop application
and a portable Windows executable. The Excel workbook
`resources/Experiments/ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx` is the executable
specification: `erdr validate` compares the package with every one of its computed sheets — 937
values, all equal ([Validation](validation.md)).

!!! warning "Three points of §1.1 are open — they are switches"
    Whether Sᵢ belongs to its own L (**A**), whether processed objects keep covering (**B**) and
    where «Перейти к шагу 2» stands in Step 5 (**C**) are not fixed by the text, nor is the class
    scope of z(Sᵢ, k). The default is the **literal** reading; the preset **closest** (B = 2 with
    the own-class z) is the reading closest to the article's Table 1. Every non-literal reading is
    flagged ([The algorithm](algorithm.md#readings-the-open-points), ADR-003, ADR-004).

## In one paragraph

Every object gets a ball that reaches exactly to the nearest object of the other class — its
enemy sphere — and a counter g that starts at the number of objects of its own class inside that
ball, itself included. ERDR puts the objects in a queue by a score d and visits them one by one.
For the visited object it collects the set L: the objects of its class that are not yet in the
training sample, hold it inside their ball and still have a counter above 1. If L has exactly one
member, the visited object goes into the training sample. If L has several members, each lowers
its counter by one, and a member whose counter reaches 1 goes into the training sample. If L is
empty, nothing happens. Objects that never reach the training sample form the validation sample.

## The default experiment

The default dataset `datasets/default.dat` (and `.csv`) is **Heart-Disease (7, 13, 2)**: rows 1,
10, 73, 143, 224, 226 and 239 of Heart-Disease (270, 13, 2) — the smallest sample in which all 17
cases of the algorithm occur (workbook sheet *Object Selection*).

```text
$ erdr run --brief
default (7, 13, 2)  (m = 7, n = 13)  ·  k = 3  ·  A=1 B=1 C=1 · z: any class
Step 2 queue order: S₁ → S₃ → S₅ → S₂ → S₇ → S₆ → S₄
iterations: 6
D (training):      5  by class 2, 3   {S₁, S₂, S₅, S₆, S₇}
F (validation):    2  by class 1, 1   {S₃, S₄}
cases: 17 of 17 occur
```

## Where to go next

- [The algorithm](algorithm.md) — every step with its formula, the readings, the cases.
- [Command line](cli.md) and [Desktop application](gui.md) — how to run it.
- [Configuration](configuration.md) and [Datasets](datasets.md) — what can be changed.
- [Architecture](architecture.md) and [Extending](extending.md) — how it is built; adding metrics,
  normalizers, dataset formats and export formats.
- [Decisions](DECISIONS.md) — every decision that shapes the numbers.
