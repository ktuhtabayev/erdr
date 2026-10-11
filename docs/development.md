# Development

## Setup (Windows PowerShell)

The project-local virtual environment uses Python 3.12, like the template project
(`context-synthetic-recognition`); the package supports Python ≥ 3.11.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,docs,release]"
.\.venv\Scripts\pre-commit.exe install
```

The virtual environment stores absolute paths; if the project folder moves, create it again.

## Everyday commands

```powershell
.\.venv\Scripts\python.exe -m pytest --cov              # tests + coverage (≥ 90 %)
.\.venv\Scripts\python.exe -m pytest -m golden          # acceptance tests (workbook, guide, Table 1)
.\.venv\Scripts\python.exe -m pytest -m "not slow"      # skip the 270-object sweeps
.\.venv\Scripts\python.exe -m pytest -m gui             # the desktop application (no window appears)
.\.venv\Scripts\erdr.exe validate                       # the package against the ERDR workbook
.\.venv\Scripts\ruff.exe check .                        # lint
.\.venv\Scripts\ruff.exe format .                       # format
.\.venv\Scripts\mypy.exe                                # strict type check of src/
.\.venv\Scripts\pre-commit.exe run --all-files          # all hooks
.\.venv\Scripts\mkdocs.exe serve                        # documentation at http://127.0.0.1:8000
.\.venv\Scripts\python.exe scripts\gui_screenshots.py   # the screenshots of docs/gui.md
.\.venv\Scripts\python.exe scripts\build_exe.py         # the portable Windows executable
```

## Git and GitHub workflow

- **Branches:** `main` is always green. Work on `feat/<topic>` or `fix/<topic>`; merge into `main`
  with a merge commit once CI passes.
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`,
  `docs:`, `test:`, `refactor:`, `chore:`, `ci:`, `build:`), with a body that explains *why*.
- **Versions:** [Semantic Versioning](https://semver.org/); every release is recorded in
  `CHANGELOG.md` (Keep a Changelog) and tagged `v<version>`.
- **CI** (`.github/workflows/ci.yml`, Windows): lint and type-check; tests on Python 3.11, 3.12,
  3.13 and `erdr validate`; strict documentation build (published to GitHub Pages from `main`);
  the Windows executable with its self-test, kept as the artifact `erdr-gui-windows`.
- **Releasing:** bump `version` in `pyproject.toml`, add the `CHANGELOG.md` entry, merge into
  `main`, then `git tag v<version>` and `git push --tags`. The *GitHub Release* job attaches the
  executable built from exactly the tagged commit, with the changelog entry as release notes.

## Conventions

- **Decisions:** every decision goes into [DECISIONS.md](DECISIONS.md). Anything that changes
  numerical results is agreed with the author first.
- **Protected material:** `resources/` is never modified; the linters and hooks exclude it and
  `datasets/`, and Git stores them byte for byte. `resources/Article/` (the unpublished article)
  is not committed (ADR-014).
- **Docstrings:** Google style; every public function names the article step it implements and
  uses the article's notation (ρ, ε, ∅, Sᵢ).
- **Layers:** the core performs no I/O; the GUI computes nothing; CLI and GUI call the same
  services ([Architecture](architecture.md)).
- **Windows only:** the project is developed, tested and released on Windows (like the template).

## The Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[gui,release]"
.\.venv\Scripts\python.exe scripts\build_exe.py
```

PyInstaller freezes the desktop application into `dist\erdr-gui\` (copy the folder as a whole)
and packs it as `dist\erdr-gui-<version>-windows.zip`; the script then runs
`erdr-gui.exe --self-test` in an empty folder and fails if the frozen application does not pass.
The report is `dist\self-test.txt` (ADR-013). No code signing: Windows SmartScreen warns about an
unknown publisher on first start.
