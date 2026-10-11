# Changelog

All notable changes are recorded here, following [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
