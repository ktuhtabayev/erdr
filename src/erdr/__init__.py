r"""Enemy-Radius Density Reduction (ERDR).

Implements the ERDR algorithm of §1.1 of N. A. Ignatev's article "Ансамбли алгоритмов
распознавания на основе синтетических признаков и контекстов k ближайших соседей": a labelled
sample E₀ is divided into a training sample D and a validation sample F = E₀ \ D. Every object
Sᵢ gets four numbers — the enemy radius r(Sᵢ), the own-class count g(Sᵢ) inside that radius, the
distance z(Sᵢ, k) to its k-th neighbour and the priority d(Sᵢ) = |z − r| / (z + r) — and a queue
by d decides which objects represent their neighbourhoods in D.

Layers: :mod:`.core` (pure numerical core: normalizers, metrics, Steps 1–6, cases),
:mod:`.config`, :mod:`.data`, :mod:`.services` (runs, readings, k sweeps, validation against the
workbook), :mod:`.export`, :mod:`.cli` and :mod:`.gui` (the desktop application, optional extra
``[gui]``).
"""

import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("erdr")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"

# A library never configures logging on import; applications call log.configure_logging().
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["__version__"]
