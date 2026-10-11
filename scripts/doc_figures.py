r"""Draw the figures of ``docs/visualizations.md`` (the default experiment, every figure).

Run from the repository root::

    .\.venv\Scripts\python.exe scripts\doc_figures.py

Every figure of a run, the spheres of S₂, the spheres of iteration 2 and the animation of the
iterations go to ``docs/images/figures`` — the same drawings the exports and the desktop
application make.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "figures"


def main() -> int:
    """Draw every figure of the default run into ``docs/images/figures``."""
    from erdr.data import load_builtin
    from erdr.export.figures import (
        figure_names,
        iteration_animation,
        iteration_spheres_figure,
        object_spheres_figure,
        run_figure,
        save_figure,
    )
    from erdr.services.experiment import run_experiment

    run = run_experiment(dataset=load_builtin("heart-disease-7"))
    OUT.mkdir(parents=True, exist_ok=True)
    for key, _ in figure_names():
        print(save_figure(run_figure(key, run), OUT / f"{key}.png", dpi=110))
    print(save_figure(object_spheres_figure(run, 1), OUT / "object-2.png", dpi=110))
    print(save_figure(iteration_spheres_figure(run, 2), OUT / "iteration-2.png", dpi=110))
    print(iteration_animation(run, OUT / "iteration-spheres.gif", dpi=80))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
