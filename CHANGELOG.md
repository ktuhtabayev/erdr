# Changelog

All notable changes are recorded here, following [Keep a Changelog](https://keepachangelog.com/)
and [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
