# Changelog

All notable changes are recorded here, following [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The datasets folder by type (ADR-021): `datasets/Quantitative/` (Cancer (589, 44, 2),
  Hypertension (147, 29, 2), Spambase (4204, 57, 2), TCGA_LUAD (589, 57772, 2)), `Nominal/`
  (Molecular-Biology (106, 57, 2), (100, 50, 2), (100, 10, 2), Uzb-Kor (100, 24, 2)) and
  `Heterogeneous/` (German (1000, 20, 2), Heart-Disease (270, 13, 2), Ionosfera (350, 33, 2)),
  each with the author's `ReadMe.txt`. `DatasetType` (quantitative, nominal, heterogeneous) comes
  from the feature flags; the catalogue knows each dataset's type folder and family and groups them.
- `erdr data check` checks that the feature types match the type folder and that every file is
  written in the author's conventions (line by line, any size), and takes dataset ids to check
  only those; `erdr data list` groups the datasets by type with each type's metric; `erdr data
  info` names the type, the metric, the metrics that suit and the memory of a run (`-c FILE` for
  a configuration's metric).
- The metric follows the dataset type (ADR-022): `distance.metric: auto` (the default) takes the
  metric of the type from `distance.type_metrics` — quantitative → Manhattan, nominal → Hamming,
  heterogeneous → Zhuravlev, the Zhuravlev distances bit for bit on every type. A metric not
  defined on the dataset's features is refused with the metrics that suit; a single-type metric
  on heterogeneous data is flagged ⚠ in the CLI, the GUI and the exports. Runs record the metric
  chosen (`ExperimentResult.metric_choice`); the exports name the dataset type and the metric.
- Every dataset of the folder except TCGA_LUAD is built in (byte-for-byte `.csv` copies with their
  type), so the Windows executable has them.
- GUI: the dataset chooser lists the type folders as headings and the built-in datasets by type;
  the summary shows the dataset type, the metric and the metrics that suit; the Configure page
  offers *auto* with one metric per type and disables the metrics the loaded dataset cannot take;
  the Run page shows the metric that will run.
- A memory estimate of a run (8·(3·m·n + 4·m²) bytes) with a warning in `erdr data info`, `erdr
  run` and the GUI when it is more than the free memory.

### Changed

- The new datasets' `.dat` files were rewritten in the conventions of `default.dat` (LF, every
  value as a decimal); the data are unchanged. Heart-Disease (270, 13, 2) moved, byte for byte,
  to `datasets/Heterogeneous/Heart-Disease/`.
- The extended-layout writer never writes an exponent (`0.00003`, not `3e-05`), as the author's
  files do; the loader parses each row as it reads it, so a 391 MB file loads without holding
  its text.
- The shipped configurations say `metric: auto` with the `type_metrics` block (the same results).
- TCGA_LUAD's data files are kept out of Git (391 MB per file, over GitHub's limit); its
  `ReadMe.txt` says where to download it.

## [0.4.1] — 2026-10-11 — the explorer's owner

### Fixed

- The GUI tests could end with exit code 1 (or 127) after all of them had passed: the hypersphere
  explorer of 0.4.0 was created without a Qt parent, so a window that never ran ERDR left it to be
  destroyed after the Qt application, when Python shut down. The explorer now belongs to the
  Results page from the start, and the page detaches the tables of an earlier run as before 0.4.0
  (ADR-020). The CI run of v0.4.0 failed on this, so 0.4.0 has no release.

## [0.4.0] — 2026-10-11 — Steps 1–5 as hyperspheres

### Added

- Steps 1–5 as hyperspheres, from the ERDR workbook's new sheets *Hyperspheres (Step 1)*,
  *Hyperspheres (Iterations)* and *Hypersphere Data* (ADR-020): `erdr.core.hyperspheres` computes
  every object's enemy sphere (r, the own class strictly inside and on it, the closed count) and
  k-sphere (its members, the rank e of the nearest enemy, q = min(r, z)/max(r, z) and
  d = (1 − q)/(1 + q)), the spheres that contain every object, and in every iteration the spheres
  around the selected Sᵢ — L is exactly the sphere test r(Sⱼ) − ρ(Sⱼ, Sᵢ) > 0 with g > 1 and the
  readings A and B.
- Tables: *enemy-spheres*, *k-spheres*, *covering*, *sphere-checks*, *iteration-spheres* and
  *sphere-trace* (every object in every iteration, for samples up to 60 objects), in every export,
  the Results page and the `erdr` command.
- Figures in the project's style: the spheres of every object on one scale, the neighbourhood
  strips, the radius plane (r, z) with its lines of equal d, the spheres around Sᵢ in every
  iteration; the object and iteration diagrams one by one in `figures/hyperspheres/` and
  `figures/iteration-spheres/`, and the iterations as an animation,
  `figures/iteration-spheres.gif`. In Excel they stand on the *Hyperspheres* sheets, in the HTML
  report before their tables.
- The **Hyperspheres** tab of the Results page: the spheres of any object or iteration, the strips
  and the radius plane, with ◀ ▶ and *Play*, the matching table, legend and summary; a double click
  on an object's or an iteration's row opens it there.
- `erdr spheres` — every object's spheres, one object's (`--object`) or one iteration's
  (`--iteration`), and the figure (`--figure`).
- `erdr validate` compares the three new sheets too: 2,927 checks (937 before), all passing.
- *Visualizations* in the documentation: every figure, what it shows, how to read it and where it
  is; `scripts\doc_figures.py` draws its images.

### Fixed

- A figure shown after the canvas was laid out kept its own size, so the canvas could clip it; it
  now gets the canvas's size.
- The Results page cleared its tabs before deleting them, so the tables of earlier runs were kept
  in memory; they are deleted now.

## [0.3.0] — 2026-10-11 — colour categories: one colour per meaning

### Added

- Colour categories across the project, one colour per meaning (ADR-019), from one source
  (`erdr.export.theme`) — the ERDR workbook's colour legend. Column headers show what a column
  holds (quantitative or nominal feature, class, r g z, d, parameter, sample); cells show the
  class of an object (K1 blue, K2 orange — as in every figure), the samples D (aqua) and F
  (violet), the steps of the algorithm, and ⚠ switches that are not the literal article reading.
- Legends: under every table of the desktop application (the Results page follows the open
  tab), on the Excel *Overview* and in the HTML report — each lists the colours it uses; tooltips
  explain a cell's or a header's colour.
- The Dataset page shows the feature types and the classes in their colours and a bar of the
  class sizes; the Run page and the status bar show D and F in their colours and the settings as
  parameter chips; the Configure page turns a non-literal switch and the preset badge orange.
- Excel sheet tabs and the Results tabs carry the workbook's stage colours.
- The `erdr` command colours its tables and ⚠ lines on a terminal (`NO_COLOR` turns it off).

### Changed

- The training sample D is aqua and the validation sample F violet in the tables (they were blue
  and orange, the figures' colours of the classes K1 and K2).
- Figures: the r–z chart draws r and z in the class colour; the sample sizes use the colours of D
  and F with end labels; a reading keeps one colour in every figure (literal green, closest blue).
- The Excel workbook uses the ERDR workbook's title bars and column headers.

## [0.2.0] — 2026-10-11 — the template's design, light and dark themes

### Added

- Light and dark themes for the desktop application: **View → Light theme** (the default),
  **Dark theme** and **Follow Windows**, **Ctrl+T** to switch; `erdr gui --theme` and
  `erdr-gui --theme` choose one from the command line (ADR-018).
- **View → Zoom in / Zoom out / Actual size** (Ctrl++, Ctrl+−, Ctrl+0; 85 % to 175 %), page
  shortcuts Ctrl+1 … Ctrl+6, and **Ctrl+C** to copy selected table cells.
- The theme, the zoom and the window's size are remembered between sessions.
- The status bar shows the reading as a badge and a ⚠ badge when a switch differs from the
  literal article text.
- A direct link to the Windows app (the latest release) at the top of the README.

### Changed

- The desktop application has the design of the template project's — the same colours, 10 pt
  base font, spacing, numbered page list, cards, buttons and tables. The Configure page shows the
  matching preset with *Literal preset* and *Closest preset* buttons in its title row, the ⚠ box
  on top and each plug-in's formula under its selector.
- The documentation screenshots show the light theme (and one of the dark theme).

### Fixed

- The desktop application could crash when its appearance changed after several runs: a table's
  model was owned by Python only and could be freed while its view was still alive. Models now
  belong to their views, and the Results page deletes the tables of the previous run.
- The release notes of a GitHub release were the fallback text "Release v<version>": the release
  job's CHANGELOG lookup used a wildcard pattern that never matched. It now matches the entry by
  its literal heading.

## [0.1.0] — 2026-10-11 — ERDR: library, CLI, desktop application, executable

### Added

- The ERDR algorithm of §1.1: Step 0 (scale unification, distances), Step 1 (r, g, z, d and the
  static queue order), Steps 2–6 (queue, L, blocking, counter corrections, D and F) with a
  replayable trace of every iteration, and the 17 cases of the workbook's checklist.
- The open points of the article as typed switches — readings A, B, C and the class scope of
  z(Sᵢ, k) — with the presets `literal` (default) and `closest`; every non-literal reading is
  flagged (ADR-003, ADR-004).
- The k rule (odd k from 3 to 2·min|Kᵢ| − 3) with `enforce`, `warn` and `off` (ADR-005).
- Normalizers: min–max (default), none, z-score, robust, max-abs, decimal scaling, rank, unit
  length. Metrics: Zhuravlev (default), weighted Zhuravlev, HEOM, Gower, Manhattan, Euclidean,
  Chebyshev, Minkowski, Canberra, cosine, Mahalanobis, Hamming; feature selection by domain.
- Datasets: `datasets/default.csv` and `default.dat` — Heart-Disease (7, 13, 2), rows 1, 10, 73,
  143, 224, 226, 239 of the 270-object files, byte for byte; the dataset catalogue and checks;
  loaders for the extended layout, CSV and Excel tables, the ERDR workbook and Parquet; a writer
  that reproduces the author's files byte for byte; built-in datasets (ADR-007).
- Typed configuration (YAML, TOML, JSON) with a canonical hash; shipped configurations.
- Services: the experiment runner, repeatable run folders with manifests, the readings comparison,
  k sweeps, dataset summaries and the validation against every computed sheet of the ERDR
  workbook — 937 checks, all passing (ADR-001).
- Exports: CSV, JSON, Markdown, LaTeX, an Excel workbook laid out like the ERDR workbook, PNG/SVG
  figures (2-D map, r and z, priorities, sample sizes, class composition, readings, sweep), a
  self-contained HTML report and the training/validation samples.
- The `erdr` command: `run`, `readings`, `sweep`, `validate`, `runs`, `export`, `data`,
  `config`, `plugins`, `gui`.
- The desktop application (PySide6): Dataset, Configure, Run, Results, Readings & k, Export;
  background work in worker threads; `--self-test`.
- The portable Windows executable (`scripts/build_exe.py`, PyInstaller), self-tested in an empty
  folder (ADR-013).
- Tests: golden tests against the workbook, the step-by-step guide's worked example and the
  270-object Table 1 values; property-based tests of the algorithm's invariants; unit, CLI and GUI
  tests — 150 tests, 94 % branch coverage; mypy strict; ruff.
- Repository: GitHub Actions on Windows (lint, types, tests on Python 3.11–3.13, `erdr validate`,
  strict docs build and GitHub Pages, the executable, releases from tags), pre-commit, MkDocs
  documentation, decision log.
