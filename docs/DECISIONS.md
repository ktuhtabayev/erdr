# Architecture and method decisions (ADR log)

Every decision that shapes the method, the numbers or the architecture is recorded here; anything
that changes numerical results is asked of the author before it is changed (CLAUDE.md).

Status values: *accepted*, *superseded by ADR-n*.

!!! warning "Three points of §1.1 are open"
    Whether Sᵢ is in its own L (A), whether processed objects keep covering (B) and where Step 5
    returns to Step 2 (C) — and the class scope of z(Sᵢ, k) — are switches. The default is the
    literal text, which reproduces the workbook; the preset *closest* is the reading nearest to
    the article's Table 1 (ADR-003, ADR-004).

---

## ADR-001 — The ERDR workbook is the specification

*Accepted, 2026-10-11.*

- `resources/Experiments/ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx` specifies every
  computation; its cached cell values are acceptance tests (tolerance 1e-9).
- `erdr validate` reads the workbook's inputs (Dataset, Parameters) and compares 937 values on
  13 sheets, including the workbook's own *Validation* sheet (53 checks) and the 270-object
  *Article Table 1 Check* (built from its *Source Dataset (270)* sheet). All pass.
- The step-by-step guide (`resources/Interpretation/…docx`) is a second oracle: its worked example
  is a golden test and a built-in dataset.
- The workbook mentions a reference engine *erdrlab*; no such code exists in the resources, so the
  engine was written from the article, the guide and the workbook, and checked against all three.
- `resources/` is never modified.

## ADR-002 — Defaults are the workbook's settings

*Accepted, 2026-10-11.*

Min–max scaling over the objects of E₀, the Zhuravlev metric on all features with the file's type
flags, distances and d rounded to 10 decimals, k = 3, ε = 0.001, readings A = B = C = 1 with z of
any class. `ExperimentConfig()` is this configuration; `configs/default.yaml` writes it out.

## ADR-003 — The open points of §1.1 are typed switches

*Accepted, 2026-10-11.*

- **A** `self_in_l: included | excluded` — Sᵢ satisfies ρ(Sᵢ, Sᵢ) = 0 < r(Sᵢ), so literally it is in
  L whenever g(Sᵢ) > 1.
- **B** `blocked_cover: kept | dropped` — blocked objects stay in F (literal); with `dropped` only
  Sᵢ and objects still waiting in the queue can be in L (Sᵢ is still waiting when L is built).
- **C** `step5_return: after-all | first-move` — with `first-move` Step 5 takes L in ascending
  index and returns to Step 2 right after the first object whose g falls to 1.
- **z** `z_scope: all | own-class` — the article does not say over which objects the k-th
  neighbour is taken.

Values 1/2 are the workbook's codes (`Readings.code`, e.g. `121`). Every non-literal reading is
named in the configuration header, the CLI, the GUI and every export (`reading_notes`).

## ADR-004 — Presets *literal* (default) and *closest*

*Accepted, 2026-10-11.*

`closest` = B = 2 with the own-class z: on all 270 objects it gives |D| = 75, 76, 71, 88, 94 for
k = 3, 5, 7, 13, 17 against 75, 77, 77, 104, 102 in Table 1 (the literal reading: 198, 190, 201,
177, 165). Shipped as `configs/heart-disease-270-closest.yaml`. On the 7-object default dataset
the own-class z is undefined for k = 3 (K1 has 3 objects), so no `closest` file is shipped for it.

## ADR-005 — The k rule

*Accepted, 2026-10-11.*

- Permitted k: odd k from k_min = 3 (fixed) to k_max = 2·min|Kᵢ| − 3, class sizes counted from the
  sample — the rule of the author's other experiments and of the workbook's *Parameters*.
- `erdr.k_rule`: `enforce` (default) rejects another k with a message listing the permitted ones;
  `warn` logs it and records it in the run; `off` skips the rule.
- Always required: z(Sᵢ, k) exists — k ≤ m − 1 (any class) or k ≤ min|Kᵢ| − 1 (own class);
  otherwise `AlgorithmUndefinedError`.

## ADR-006 — Indexing and notation

*Accepted, 2026-10-11.*

Objects, features and classes are shown 1-based (S₁, x₁, K1) with subscript digits; code is
0-based. Sets print as {S₁, S₃} (∅ when empty), orders as S₁ → S₃ → S₅, moves as `S₇ (Step 5)`,
counter changes as `S₁: 3 → 2` — the workbook's own wording, so the validator compares text.

## ADR-007 — Datasets: folder, default dataset, formats

*Accepted, 2026-10-11.*

- The existing `datasets/Heart-Disease/Heart-Disease (270, 13, 2).csv|.dat` are kept as they are
  (family folder directly under `datasets/`, no `raw/` level).
- `datasets/default.csv` and `default.dat` = Heart-Disease (7, 13, 2): rows 1, 10, 73, 143, 224,
  226, 239 of the 270-object files, copied byte for byte (only the first row becomes `7,13,2` /
  `7 13 2`) — identical to the workbook's *Dataset* sheet (tested).
- The catalogue reads `default.*` and `<Family>/<Name (m, n, c)>.dat|.csv` at any depth (`.dat`
  preferred; `synthetic/` reserved); `ERDR_DATASETS` overrides the folder.
- `write_extended` reproduces the author's `.csv` (CRLF, padded header, integral values without a
  point, trailing empty cell in the type row) and `.dat` (LF, decimals) conventions byte for byte.
- Built-in copies (`heart-disease-7`, `heart-disease-270`, `guide-example`) serve installations
  without the folder; `heart-disease-7` is the default there.
- Formats: `extended`, `erdr-workbook`, `csv`, `xlsx`, `parquet` (extra). Missing values are
  errors. Class labels sorted: the first is K1.

## ADR-008 — Numerical conventions

*Accepted, 2026-10-11.*

- Distances rounded to 10 decimals (quantitative part first, then the sum); a symmetric matrix is
  never rounded twice. d rounded to 10 decimals as well.
- Neighbours by (ρ, index); the nearest enemy is the first enemy in that order.
- A quantitative feature without spread maps to 0 (every normalizer).
- z + r = 0 (an object coincides with an enemy and its nearest neighbour) → d = 0; r = 0 → g = 0.
- |L| = 0: Sᵢ is only blocked and stays in F (the article does not describe it).
- Step 5 decreases the members of L in ascending index.

## ADR-009 — Spelling of the metric: *Zhuravlev*

*Accepted, 2026-10-11.*

The ERDR workbook and guide write *Zhuravlev*; the registry name is `zhuravlev`, with the
template project's spelling `zhuravlyov` and `juravlev` as aliases.

## ADR-010 — Metrics and normalizers as plug-ins with traits

*Accepted, 2026-10-11.*

The template project's normalizers and metrics (same author, MIT) are adapted: ERDR fits them on
the whole sample E₀ (there is no held-out data), and a single feature selection replaces the
template's base operators. `distance.features: auto` gives each metric its declared domain. A
metric's fit step (ranges, covariance) sees no class labels.

## ADR-011 — Configuration and run folders

*Accepted, 2026-10-11.*

Typed, strict, immutable pydantic models; YAML/TOML/JSON; SHA-256 of the canonical JSON form.
Relative dataset paths resolve against the configuration file. A run folder holds the
configuration, the dataset as JSON (independent of the file it came from), Step 1 and the trace,
the two samples and a manifest with versions and SHA-256 of every file; `load_run` repeats the run
and checks that it gives the stored D and F.

## ADR-012 — One table and figure model for every export and the GUI

*Accepted, 2026-10-11.*

`erdr.export.tables` builds plain tables mirroring the workbook's sheets; cells carry semantic
marks mapped to the same tints in the GUI, Excel and HTML. `erdr.export.figures` draws on given
axes (no pyplot state), so the GUI embeds the exported drawings. One categorical palette in fixed
order, validated for colour-vision deficiency; class is also encoded by marker shape and the
sample by fill. m × m tables of samples larger than 60 objects are left out of the text reports.

## ADR-013 — The portable Windows executable

*Accepted, 2026-10-11.*

PyInstaller, one folder (not one file: no unpacking on every start, fewer virus-scanner
complaints), packed as a zip; Qt's software OpenGL and other languages' translations removed.
`erdr-gui --self-test REPORT` checks a frozen installation without a window; the build fails if it
does not pass. About 150 MB unpacked, 70 MB packed. Built in CI and attached to every release.

## ADR-014 — Public repository; the article stays local

*Accepted, 2026-10-11.*

The workbook, the guide and the datasets are committed; `resources/Article/` (the unpublished
article by N. A. Ignatev) is listed in `.gitignore` and stays on disk unchanged. Protected folders
are stored byte for byte (`-text`); other text files use LF.

## ADR-015 — Engineering conventions

*Accepted, 2026-10-11.*

Python ≥ 3.11, developed in a project-local `.venv` on Python 3.12.10 (the template's version);
`src/` layout, setuptools, editable install. ruff (lint + format, line length 100), mypy strict,
pytest with hypothesis and pytest-qt, coverage ≥ 90 %, pre-commit, GitHub Actions on Windows,
mkdocs-material (MkDocs 1.x), Conventional Commits, Keep a Changelog, Semantic Versioning. MIT.

## ADR-016 — More than two classes

*Accepted, 2026-10-11.*

ERDR's definitions hold for any number of classes (an enemy is an object of any other class;
the k rule takes min over the classes; the cases ask for every class in D and F). The engine
supports c ≥ 2; it is validated on two classes, the article's setting.

## ADR-017 — Findings for the article

*Accepted, 2026-10-11.*

The literal reading of §1.1 does not reproduce Table 1 (165–201 objects in D against 75–104); the
closest reading found (B = 2 with the own-class z) differs by 0–16. |L| = 0 is not described.
g(Sⱼ) > 1 in L only ever excludes Sᵢ itself. g is written as a set but used as its size. The
article counts 7 quantitative features where the data file flags 6 (probably x₁₁). These are
reported, not "fixed": the defaults follow the text and the file.
