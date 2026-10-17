# Extending

Normalizers, metrics, dataset formats and export formats are plug-ins chosen by name from a
`Registry`. A plug-in registered in your own package is available in the configuration, the CLI
and the GUI — whose parameter form is generated from the plug-in's parameter type.

## A metric

```python
import numpy as np
from pydantic import Field
from pydantic.dataclasses import dataclass

from erdr.core.metrics import METRICS, round_distances, traits
from erdr.core.registry import PARAMS_CONFIG


@dataclass(frozen=True, config=PARAMS_CONFIG)
class LorentzianParams:
    scale: float = Field(default=1.0, gt=0.0)


@METRICS.register(
    "lorentzian", summary="Σ ln(1 + |x′ − y′| / s) on I", params_type=LorentzianParams
)
@traits(domain="quantitative")
def lorentzian(A, B, quantitative, decimals, params=None, /):
    s = (params or LorentzianParams()).scale
    total = np.zeros((A.shape[0], B.shape[0]))
    for j in range(A.shape[1]):
        total += np.log1p(np.abs(A[:, j, None] - B[None, :, j]) / s)
    return round_distances(total, decimals)
```

A metric receives the unified values of the selected features and returns the rounded distance
matrix. `traits` declares its domain (`any`, `quantitative`, `nominal`), an optional fit step
(statistics over E₀, e.g. the covariance of `mahalanobis`) and an optional check of its parameters
against the selected features. No metric reads a class label.

## A normalizer

A normalizer `(X, quantitative, params) -> Scaling` estimates its constants on E₀; see
`erdr.core.normalizers` (`minmax`, `z-score`, …) for the pattern. Register it with
`@NORMALIZERS.register("name", summary=…, params_type=…)`.

## A dataset format or an export format

```python
from erdr.data.loaders import LOADERS  # (path, LoadOptions) -> Dataset
from erdr.export import EXPORTERS  # (run, folder, ExportOptions) -> list[Path]
```

## From another package

Entry points make the plug-ins available without importing anything:

```toml
[project.entry-points."erdr.metrics"]
lorentzian = "my_package.metrics:lorentzian"
```

Groups: `erdr.metrics`, `erdr.normalizers`, `erdr.loaders`, `erdr.exporters`
(`Registry.load_entry_points()`).

## A dataset

Drop `<Name> (m, n, c).dat` and `.csv` in the extended layout into a family folder of the type
folder that fits its features — `datasets/Quantitative/`, `Nominal/` or `Heterogeneous/`;
`erdr data check` verifies it, including the type folder and the author's file conventions
(`erdr.data.write_extended` writes them). The metric follows its type ([Datasets](datasets.md)).
To build a small dataset into the package, copy its `.csv` to `src/erdr/data/datasets/` and add
it to `erdr.data.builtin` with its type.

## A reading

The readings A, B, C and the scope of z are typed switches (`erdr.core.readings`); a new open point
of the text would become a new field of `Readings` and `ReadingsConfig`, a branch in
`erdr.core.algorithm.run_erdr`, a line in `reading_notes` (so it is flagged) and a column of the
readings table — and must be agreed with the author first (it changes numerical results).
