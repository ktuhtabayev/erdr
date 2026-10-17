# erdr — project memory for Claude Code

Python implementation (library + CLI + desktop GUI + portable Windows executable) of the
Enemy-Radius Density Reduction (ERDR) algorithm — §1.1 of N. A. Ignatev's article — which divides a
labelled sample E₀ into a training sample D and a validation sample F = E₀ \ D. Use "Enemy-Radius
Density Reduction (ERDR)" as its full title in the documentation.

Start here: `README.md`, `docs/algorithm.md`, `docs/DECISIONS.md` (authoritative decisions).

Non-negotiables (details in docs/DECISIONS.md):
- Specification = `resources/Experiments/ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx`; `erdr validate` must pass all its checks (tolerance 1e-9). The step-by-step guide in `resources/Interpretation/` is the second oracle (tests/golden).
- Default = the literal reading (A = B = C = 1, z over any class), min–max over E₀, Zhuravlev metric (`distance.metric: auto` — the metric follows the dataset type: Zhuravlev on heterogeneous data, its Manhattan/Hamming part on quantitative/nominal data, bit-identical; ADR-022), k = 3, ε = 0.001. The open points A, B, C and the scope of z are switches; every non-literal reading must stay flagged in the CLI, the GUI and the exports.
- Permitted k: odd, k_min = 3, k_max = 2·min|Kᵢ| − 3 from the sample — never hard-coded.
- Distances and d rounded to 10 decimals; ties → smaller index; |L| = 0 leaves Sᵢ in F; Step 5 takes L by ascending index.
- `datasets/default.*` = rows 1, 10, 73, 143, 224, 226, 239 of Heart-Disease (270, 13, 2), byte for byte; dataset files are written in the author's exact .csv/.dat conventions (those of default.csv/.dat — `erdr data check` enforces them).
- `datasets/` is grouped by type: `Quantitative/`, `Nominal/`, `Heterogeneous/` — the feature flags must match the folder (ADR-021). TCGA_LUAD (391 MB) stays local (git-ignored, not built in); every other dataset is also a built-in copy.
- Never modify `resources/` or the template project `../context-synthetic-recognition` (read-only reference). `resources/Article/` stays out of Git.
- The core performs no I/O; the GUI computes nothing; CLI and GUI share the services.
- Record decisions in `docs/DECISIONS.md`; ask the author before changing anything that alters numerical results.
- Quality gates: ruff, mypy strict, pytest (coverage ≥ 90 %); Windows only; Python 3.12 `.venv`.
