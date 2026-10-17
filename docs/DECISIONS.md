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
- `erdr validate` reads the workbook's inputs (Dataset, Parameters) and compares 2,927 values on
  16 sheets, including the workbook's own *Validation* sheet (53 checks), the 270-object
  *Article Table 1 Check* (built from its *Source Dataset (270)* sheet) and, since the workbook's
  hypersphere sheets (ADR-020), *Hyperspheres (Step 1)*, *Hyperspheres (Iterations)* and
  *Hypersphere Data*. All pass (937 values on 13 sheets before ADR-020).
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
  (family folder directly under `datasets/`, no `raw/` level). *Amended by ADR-021:* the author
  moved them, unchanged, to `datasets/Heterogeneous/Heart-Disease/`; the datasets are grouped by
  type folder.
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

## ADR-018 — The desktop application shares the template's design; light by default (author)

*Accepted, 2026-10-11.*

**Author.** Make the ERDR application look like the template project's — the same style, font
sizes and spacing — and give it a light ("white") mode, not only the Windows dark window.

- `erdr.gui.theme` takes over the template's design tokens and style sheet unchanged in look:
  colours, a 10 pt base font (Qt's Windows default is 9 pt), page margins 18/14/18/12 px with 8 px
  spacing, the numbered page list of at least 184 px, cards, buttons (the main action of a page in
  the accent colour), inputs, tables with alternating rows, tabs and the status-bar badges.
- Themes: **light** (default), **dark**, and **system**, which shows the light or the dark palette
  as Windows is set — the styling is the same in every case. On Qt ≥ 6.8 the window frame follows
  the theme. The tinted table cells keep their light tints and dark ink in every theme, so they
  look as in Excel and in the HTML report.
- View → Zoom with the template's steps (0.85 … 1.75); the theme, the zoom and the window geometry
  are stored in the user's settings (`erdr/erdr`); tests and the self-test use their own ini file.
- A table model is created with its view as parent: owned by Python only, it could be freed while
  its view still existed, and restyling the application then crashed. The Results page deletes
  the tables of a previous run instead of only hiding them.

No numerical result changes.

## ADR-019 — One colour per meaning, everywhere (author)

*Accepted, 2026-10-11.*

**Author.** Give classes, nominal and quantitative features, the samples, the parameters and the
other categories distinct colours, consistently across the project — the GUI, the tables, the
figures, the legends and the experiment displays — following the template, without changing any
data or logic.

- **One source.** `erdr.export.theme` maps every *mark* — what a cell or a column means — to a
  light tint, a dark ink and a strong accent; the GUI, the Excel writer, the HTML report, the
  figures and the console all read it. `Table.header_marks` (new) says what kind of quantity a
  column holds; the cell marks of ADR-012 say what a value is. Marks never change a value; the
  CSV, JSON, Markdown and LaTeX exports stay plain.
- **The workbook's legend.** The colours are those of the ERDR workbook's *Overview* ("Colour
  legend"), which the template's workbooks share: quantitative feature (set I) `#DDEBF7`, nominal
  feature (set J) `#FFF2CC`, class label `#F4CCCC`, ERDR characteristic r, g, z `#E2EFDA`, d /
  selected / own class / literal / occurs `#C6EFCE`, member of L / decreased counter / tie by r
  `#FFE699`, enemy `#FDE9E7`, parameter `#E4DFEC`, type flags `#D9E1F2`, statistic `#F2F2F2`,
  warning `#FCE4D6`, does not occur `#FFC7CE`. Column headers take the colour of their category;
  the feature values themselves stay white, so the class cells beside them remain distinct.
- **Classes keep the figures' colours.** K1 blue, K2 orange, K3 aqua, … — the validated
  categorical palette of the template's figures, in fixed order, never cycled (a ninth class is
  grey in the figures and takes the class colour in the tables). The class cells of every table,
  the object headers and row labels of the m × m tables, the class columns of the compositions,
  the class bar of the Dataset page and every run figure use them.
- **One change to the workbook's legend.** The workbook draws the training sample D (and "moved
  to D", "tie decided by the index") in blue `#BDD7EE`, the class colour of K1. Here **D is aqua**
  (tint `#B3E5D9`, figures `#1BAF7A`) and the **validation sample F violet** (tint `#D6CFF7`,
  figures `#6250D6`), in the tables and in the sample-sizes figure alike; before, the tables drew D
  blue and F orange — the colours of K1 and K2 in the figures.
- **Figures.** In every figure of a run the colour is the class: the r–z chart now marks r
  (filled ●) and z (hollow ◇) in the class colour instead of blue and orange. The sample sizes
  are drawn in D's and F's colours, with the queue grey and dashed, and labelled at their ends.
  A reading keeps one colour in every figure: the literal reading green (as in the tables), the
  closest reading blue, further ones yellow and magenta (validated together); before, the sweep
  coloured readings by their position.
- **Non-literal readings stay flagged.** Switch values that differ from the article's text are in
  the warning colour in the readings, sweep and key-results tables, on the Configure page (the
  switch and the preset badge) and on the Run page; the console prints ⚠ lines in that colour.
- **Legends.** Each GUI table shows a legend of the marks it uses (the Results page follows the
  open tab); the Excel *Overview* and the HTML report list the marks of the export, by section
  (columns, classes, samples, steps of the algorithm, readings and checks). Cells and headers
  explain their colour in a tooltip (GUI, HTML).
- **Stages.** The Excel sheet tabs and the Results tabs carry the workbook's stage colours (data
  blue, Step 0 purple, Steps 1–5 orange, Step 6 green, readings gold).
- **Console.** `erdr` colours headers, classes, samples, warnings and validation marks on a
  terminal with the accents; nothing is coloured when the output is redirected or `NO_COLOR` is
  set.
- The template project is only read, never changed. Tints keep their light fill and dark ink in
  the dark theme (ADR-018).

No numerical result changes.

## ADR-020 — Steps 1–5 as hyperspheres, in the project's own style (author)

*Accepted, 2026-10-11.*

**Author.** The ERDR workbook was updated with hypersphere sheets. Take from it every
visualization that explains the algorithm, add our own where useful — from the input data through
the intermediate calculations to the result — place each where it supports its calculation, make
them dynamic where appropriate, and keep the project's current styling and formatting unchanged:
the new visuals follow the same style and formats.

- **The workbook's new sheets.** *Hyperspheres (Step 1)* (the enemy sphere (Sᵢ, r(Sᵢ)) and the
  k-sphere (Sᵢ, z(Sᵢ, k)) of every object, the spheres that contain each object, a summary with
  four checks, neighbourhood strips, the radius plane and one sphere diagram per object),
  *Hyperspheres (Iterations)* (per iteration, the enemy spheres of the own-class objects around the
  selected Sᵢ — the spheres in F that contain Sᵢ give L) and *Hypersphere Data* (the diagrams'
  coordinates). No existing sheet changed except the workbook's index; `erdr validate` passed
  unchanged on the new file.
- **One core, no I/O.** `erdr.core.hyperspheres` computes what the sheets show: per object the
  own class strictly inside the enemy sphere and on it, the enemies on it, the closed count ρ ≤ r,
  the k-sphere's members, q = min(r, z)/max(r, z) and d = (1 − q)/(1 + q), the relation of the two
  spheres; per iteration every object's distance to Sᵢ, its radius, whether its sphere contains Sᵢ,
  its counter before and after, whether readings A and B allow it, L and the moves; the workbook's
  texts (roles, readings of a sphere, the change of L since the start) and the layout of the
  diagrams (true distance from the centre, the centre's neighbour order clockwise from the top at
  equal angles). L rebuilt from the sphere test alone equals the engine's L in every iteration —
  a property test on random samples with ties and every reading checks it.
- **Exact where the workbook is silent.** When an object coincides with an enemy, r = 0 and g = 0
  (ADR-008): the object is not inside its own empty sphere, so g = [r > 0] + the own class strictly
  inside, and the closed count less every object on the sphere is g. The workbook's sample never
  has r = 0; its checks read the same.
- **Validation.** The validator now compares the three new sheets too: 235 + 805 + 950 checks — the
  sphere tables and checks, every iteration's block (also the Step 6 blocks), the diagrams'
  positions, ranks and angles, the strips, the radius plane and its lines of equal d. 2,927 checks
  in all, every one passing.
- **Tables** (`erdr.export.tables`, ADR-012): *enemy-spheres*, *k-spheres*, *covering*,
  *sphere-checks* (sheet *Hyperspheres (Step 1)*), *iteration-spheres* (one row per iteration) and
  *sphere-trace* (every object in every iteration — m rows per iteration, so it is built for samples
  up to 60 objects only; the desktop application shows any iteration of a larger sample on
  demand). They use the existing marks only.
- **Figures** in the project's style, not the workbook's chart styling: the colour of a mark is its
  class (K1 blue, K2 orange …), as in every figure of a run; nothing new is coloured. A sphere's
  state is told by its line and fill — the enemy sphere solid, the k-sphere dashed; in an
  iteration a sphere in L solid with the yellow of L (the tables' colour of L), in F but not in L
  dashed, of an object already in D dotted; markers filled in D, hollow in F, as on the 2-D map.
  The workbook draws L gold; next to K2's orange it fails the colour-vision check (ΔE 1.6
  deuteranopia, 9.4 normal vision), so the figures do not use it. Figures: *hyperspheres* (every
  object's spheres on one scale, up to 12 panels — for larger samples the first 12 of the queue),
  *strips*, *radius-plane*, *iteration-spheres* (iterations 1 … 12) and, one by one, the object and
  iteration diagrams; above 36 objects the diagrams leave out their spokes, draw only the spheres
  that contain Sᵢ and rasterize their markers inside SVG.
- **Placement.** The sphere figures go where their calculation is: on the *Hyperspheres* sheets of
  the Excel export (the other figures stay on *Charts*), right before their tables in the HTML
  report (the others stay at the top), in `figures/` with `figures/hyperspheres/` and
  `figures/iteration-spheres/` for the single diagrams. The new sheets carry the Steps 1–5 tab
  colour.
- **Dynamic.** The Results page has a *Hyperspheres* tab: the spheres of any object, the spheres
  of any iteration, the strips or the radius plane, with ◀ ▶ and *Play* (1.6 s per step, stops at
  Step 6), the matching table, its legend and the block's summary; a double click on an object's or
  an iteration's row of a table opens it there. The figures export also writes
  `figures/iteration-spheres.gif`, the iterations as an animation (`gif` in the figure formats).
  `erdr spheres` prints the same tables and saves the same figures (`--object`, `--iteration`,
  `--figure`).
- **A GUI fix found on the way.** A figure shown after its canvas was laid out kept its own size
  (the canvas clipped it) — `FigureView` now gives it the canvas's size, as matplotlib's resize
  handler would.
- **Qt owns every widget (0.4.1).** In 0.4.0 the hypersphere explorer was created without a
  parent and joined the tab widget only when a run arrived; in the GUI tests that never run ERDR it
  stayed owned by Python until the interpreter shut down, after the Qt application — Qt aborted
  (exit code 1 or 127 after every test had passed; the CI run of v0.4.0 failed, so 0.4.0 has no
  release). The explorer is now a child of the Results page from the start and one widget kept
  across runs. 0.4.0 also let the Results page delete the pages of an earlier run; 0.4.1 detaches
  them again as before (it clears its tabs before the loop that would delete them — unlike what
  ADR-018 says), the behaviour every earlier release ran with.

No numerical result changes.

## ADR-021 — Datasets by type: Quantitative, Nominal, Heterogeneous (author)

*Accepted, 2026-10-17.*

**Author.** Categorized datasets were added to `datasets/` — the folders `Quantitative/`,
`Nominal/` and `Heterogeneous/` — to be integrated throughout the project following the rules of
each dataset type; a dataset that does not match the default structure is reported first.

- **The review.** Every file was checked against the extended layout and the author's
  conventions (ADR-007). All of them loaded, with headers equal to their names and `.dat` equal to
  `.csv`. What did not match was reported, and the author decided:
  - every new `.dat` file had Windows line ends and integers without a decimal point → **rewritten
    in the conventions of `default.dat`** (LF, `70.0`), the data checked against the `.csv`
    (the 391 MB TCGA_LUAD file streamed and compared row by row);
  - Ionosfera (350, 33, 2) and DDoS (10000, 80, 2) were in `Quantitative/` with one nominal
    feature → Ionosfera **moved to `Heterogeneous/`**, the DDoS files **deleted** (both versions;
    the 22-feature one held 380 distinct rows in 10,000, the 80-feature one 13 constant columns);
  - Spambase (4595, 57, 2) had the class labels 0/1 and 391 repeated rows → **deleted**; Spambase
    (4204, 57, 2) is exactly that file without the repeats, labels 1/2 (verified);
  - TCGA_LUAD (589, 57772, 2) is 391 MB per file, over GitHub's 100 MB → **kept on the author's
    computer only**: its `.dat`/`.csv` are in `.gitignore`, its `ReadMe.txt` (how to download it)
    is in Git; erdr catalogues and runs it when present.
- **The rule of the type folders.** A dataset's type comes from its feature flags
  (`DatasetType`: quantitative = every flag 1, nominal = every flag 0, heterogeneous = both), and
  the folder must agree: `erdr data check` reports a nominal feature in `Quantitative/`, a
  quantitative one in `Nominal/`, a single-type dataset in `Heterogeneous/`. The catalogue reads
  `<Type>/<Family>/<Name (m, n, c)>.dat|.csv`; a family folder directly under `datasets/` is still
  read (*Other*). Heart-Disease (270, 13, 2) moved to `Heterogeneous/Heart-Disease/` — byte for
  byte the same files (amends ADR-007).
- **The conventions are checked.** `erdr data check` compares every file line by line with what
  `write_extended` writes for its data and names the first line that departs (streamed, so a file
  of any size). The writer now writes numbers without an exponent (`0.00003` as Ionosfera's
  `.csv` does, not `3e-05`); Heart-Disease and the default dataset are written as before, byte for
  byte. A test reads and rewrites every file of the folder (except the local-only one).
- **Large files.** The extended-layout loader parses each row as it reads it, so TCGA_LUAD (34
  million values) never holds all its cells as text; a run on it needs about 790 MB and takes
  162 s on the development laptop (7.7 GB). `erdr data info`, `erdr run` and the GUI estimate the
  memory of a run (8·(3·m·n + 4·m²) bytes, calibrated on German and Spambase) and warn when it is
  more than the free memory. `erdr data check DATASET…` checks only the named datasets.
- **Built-in.** The package carries byte-for-byte copies of the `.csv` files of every dataset of
  the folder except TCGA_LUAD (1.3 MB), with their type, so the Windows executable has them; the
  GUI and `erdr data list` group them by type. A test keeps the copies equal to the folder.
- **Everywhere.** `erdr data list` groups the catalogue by type folder (with each type's rule and
  metric), `erdr data info` names the type, the metric and the metrics that suit, `erdr run`
  prints the type in its header; the GUI's chooser lists the type folders as headings, the summary
  shows the type in the colour of its features (heterogeneous: the type-row colour — no new
  colour), the exports name the dataset type in their settings.
- **Public repository.** The repository is public (ADR-014): Uzb-Kor (a questionnaire of the
  NUUz sociology department), Hypertension (from N. A. Ignatev's monograph) and Cancer (source not
  recorded) become public when pushed, and are built into released executables.

No numerical result of an existing dataset changes; `erdr validate` passes unchanged (2,927).

## ADR-022 — The metric follows the dataset type (author)

*Accepted, 2026-10-17.*

**Author.** «Choose metrics based on dataset types.»

- **Suitability.** A metric declares its domain (ADR-010). On a quantitative dataset the
  quantitative and the heterogeneous metrics suit, on a nominal one Hamming and the heterogeneous
  metrics, on a heterogeneous one the heterogeneous metrics (Zhuravlev, weighted Zhuravlev, HEOM,
  Gower). A metric not defined on the dataset's features — Euclidean on Uzb-Kor, Hamming on
  Cancer — is a `ConfigError` that lists the metrics that suit (before: «the feature selection
  is empty»). A single-type metric on a heterogeneous dataset still runs on its part of the
  features, as before, but is **flagged ⚠** (run warnings, the settings of every export, the
  CLI, the GUI): it ignores the other feature type.
- **`distance.metric: auto` (the default).** The metric is taken from `distance.type_metrics`
  by the dataset's type: quantitative → `manhattan`, nominal → `hamming`, heterogeneous →
  `zhuravlev`. These are the Zhuravlev metric and its two parts ρ_I = Σ_I |x′ − y′| and
  ρ_J = Σ_J [x ≠ y]: on single-type data they give **the Zhuravlev distances bit for bit** (same
  summation order, same rounding) — tested on every dataset type — so the literal default of
  CLAUDE.md and ADR-002 is kept on every dataset, and `erdr validate` passes unchanged. A metric of
  `type_metrics` must suit its type (checked by `erdr config check` and before a run); it may carry
  parameters (`minkowski {p: 3}`). Choosing, say, Euclidean for quantitative datasets changes
  numerical results — the author's choice, made in the configuration or the GUI.
- **Shown everywhere.** Runs record the metric chosen (`ExperimentResult.metric_choice`); the
  exports and the CLI write it as `manhattan (auto · quantitative dataset)`. The shipped
  configurations name `metric: auto` with the `type_metrics` block. The GUI's metric box starts
  with *auto — the metric of the dataset type*; under it one box per type offers the metrics that
  suit that type; metrics not defined on the loaded dataset are disabled with the reason as
  tooltip, and a single-type metric on heterogeneous data shows the ⚠ box.
- The ρ_I / ρ_J tables of the *Zhuravlev Distances* sheet are written when the metric is
  Zhuravlev, as before; on single-type data `auto` runs Manhattan or Hamming, whose matrix is the
  *Distances* sheet.

No numerical result changes.
