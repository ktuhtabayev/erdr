# Exporting

A run is exported with `erdr run --export FORMATS`, `erdr export [RUN] -f FORMATS` (repeats a
saved run first) or the GUI's Export page. `all` is every format.

| Format | Files | Content |
|---|---|---|
| `csv` | `csv/<table>.csv` | one file per table; every float exactly; UTF-8 with BOM (Excel shows S₁, ρ, ∅) |
| `json` | `run.json` | every table, the settings, notes and warnings |
| `markdown` | `report.md` | the settings and every table |
| `latex` | `latex/<table>.tex`, `latex/tables.tex` | booktabs tables, ASCII only (S$_{1}$, $\rho$) |
| `xlsx` | `workbook.xlsx` | tables stacked per sheet like the ERDR workbook; figures on *Charts*; cell marks as fills |
| `figures` | `figures/<figure>.png`, `.svg` | the 2-D map, r and z, priorities, sample sizes, class composition (+ readings, sweep) |
| `html` | `report.html` | one self-contained page: settings, figures (inline SVG), tables |
| `datasets` | `datasets/training|validation.dat|csv` | D and F in the author's extended layout |

The tables mirror the workbook's sheets: key results, dataset, normalized data, ρ (and ρ_I, ρ_J),
sorted neighbours, Step 1, enemy spheres, queue, iterations, counters, routes (D and F), class
composition, cases — plus the readings comparison and the k sweep when they are included. For
samples larger than 60 objects the m × m tables are left out of Markdown, LaTeX and HTML (they
stay in CSV, JSON and Excel).

## Figures

The figures use one categorical palette in a fixed order (blue, orange, aqua, …), validated for
colour-vision deficiency; the class is also told by the marker shape and the sample by the fill
(filled = D, hollow = F), so nothing rests on colour alone. The 2-D map is a classical
multidimensional scaling of ρ — positions are approximate.

![The sample sizes through the iterations](images/gui/results-figure.png)

From Python:

```python
from pathlib import Path
from erdr.export import export_result, ExportOptions
from erdr.services.analysis import compare_readings

export_result(
    run, Path("exports"), ["xlsx", "html"], ExportOptions(readings=compare_readings(run.dataset))
)
```
