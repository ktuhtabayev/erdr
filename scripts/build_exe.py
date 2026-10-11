r"""Build the portable Windows executable of the desktop application with PyInstaller.

Run from the repository root::

    .\.venv\Scripts\python.exe -m pip install -e ".[gui,release]"
    .\.venv\Scripts\python.exe scripts\build_exe.py

The result is ``dist\erdr-gui\`` — a folder with ``erdr-gui.exe`` and everything it needs, to be
copied as a whole (nothing is installed) — and ``dist\erdr-gui-<version>-windows.zip``, the same
folder packed. The script then runs ``erdr-gui.exe --self-test`` in an empty folder: the frozen
application opens its built-in default dataset, runs ERDR (it must give the workbook's training
sample), shows a table and a figure, compares the readings and exports every format; the report
is ``dist\self-test.txt`` (``--no-test`` skips this) (ADR-013).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build" / "pyinstaller"
NAME = "erdr-gui"
PACKAGE = "erdr"
DISTRIBUTION = "erdr"
EXCLUDED = (
    # optional extras and tools of the development environment
    "pyarrow",
    "sklearn",
    "scipy",
    "pandas",
    "pytest",
    "hypothesis",
    "IPython",
    "tkinter",
    "mypy",
    "PyInstaller",
)
HIDDEN = (
    # figures are saved through backends matplotlib picks by file type at run time
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_svg",
)
LANGUAGES = ("en",)
"""Qt's own translations are kept for these languages only."""


def say(text: str) -> None:
    """Print a line."""
    print(text, flush=True)


def build() -> Path:
    """Freeze the application; returns the folder with the executable."""
    import PyInstaller.__main__

    arguments = [
        str(ROOT / "scripts" / "erdr_gui_launcher.py"),
        "--name",
        NAME,
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(ROOT / "src"),
        "--collect-data",
        PACKAGE,
        "--copy-metadata",
        DISTRIBUTION,
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
    ]
    for module in EXCLUDED:
        arguments += ["--exclude-module", module]
    for module in HIDDEN:
        arguments += ["--hidden-import", module]
    PyInstaller.__main__.run(arguments)
    return DIST / NAME


def prune(folder: Path) -> int:
    """Remove what the application never loads; returns the bytes freed.

    Qt's software OpenGL renderer (the interface is drawn without OpenGL) and Qt's translations
    of other languages.
    """
    qt = folder / "_internal" / "PySide6"
    kept = tuple(f"_{code}.qm" for code in LANGUAGES)
    unused = [qt / "opengl32sw.dll"]
    unused += [f for f in (qt / "translations").glob("*.qm") if not f.name.endswith(kept)]
    freed = 0
    for path in unused:
        if path.is_file():
            freed += path.stat().st_size
            path.unlink()
    return freed


def self_test(folder: Path) -> bool:
    """Run the frozen application's self-test; the report is ``dist/self-test.txt``.

    It runs in an empty folder, away from the project's ``datasets``, as it will on a machine
    that has only the executable.
    """
    report = DIST / "self-test.txt"
    report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as elsewhere:
        result = subprocess.run(
            [str(folder / f"{NAME}.exe"), "--self-test", str(report)],
            check=False,
            timeout=900,
            cwd=elsewhere,
        )
    if report.is_file():
        say(report.read_text(encoding="utf-8").rstrip())
    return result.returncode == 0 and report.is_file()


def pack(folder: Path) -> Path:
    """Pack the folder as ``erdr-gui-<version>-windows.zip`` next to it."""
    archive = shutil.make_archive(
        str(DIST / f"{NAME}-{version(DISTRIBUTION)}-windows"), "zip", root_dir=DIST, base_dir=NAME
    )
    return Path(archive)


def main(argv: list[str] | None = None) -> int:
    """Build, test and pack the executable."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--no-test", action="store_true", help="do not run the self-test")
    arguments = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:  # the report holds characters a Windows code page cannot encode
        reconfigure(encoding="utf-8", errors="replace")
    folder = build()
    say(f"removed {prune(folder) / 1e6:.0f} MB the application never loads")
    if not arguments.no_test and not self_test(folder):
        say("the self-test of the frozen application FAILED")
        return 1
    archive = pack(folder)
    size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / 1e6
    say(f"{folder}  ({size:.0f} MB)")
    say(f"{archive}  ({archive.stat().st_size / 1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
