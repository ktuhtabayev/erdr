# Desktop application

`erdr gui` (or `erdr-gui`, or the portable `erdr-gui.exe`) opens the default dataset. The pages
follow the workflow — **Dataset → Configure → Run → Results → Readings & k → Export** — and the
application computes nothing itself: a run, an analysis and an export are the services in a
worker thread, and the tables and figures on screen are the exporters' own (ADR-012).

## Appearance

The application has the design of the template project's desktop application — the same
colours, 10 pt base font, spacing, numbered page list, cards, buttons and tables (ADR-018).

| | |
|---|---|
| **View → Light theme** (default) · **Dark theme** · **Follow Windows** | **Ctrl+T** switches between light and dark |
| **View → Zoom in / Zoom out / Actual size** | **Ctrl++ / Ctrl+− / Ctrl+0** (85 % … 175 %) |
| **Ctrl+1 … Ctrl+6** | the pages; **F5** runs ERDR; **Ctrl+C** copies selected table cells |

The theme, the zoom and the window's size are remembered. `erdr gui --theme dark` (or
`erdr-gui.exe --theme dark`) chooses the theme from the command line. The status bar shows the
reading as a badge — `literal`, `closest` or `custom` — and a ⚠ badge whenever a switch differs
from the literal article text; a click opens Configure.

![The dark theme](images/gui/dark-results-iterations.png)

## Dataset

Choose a dataset of the project's folder or a built-in one, or open any file (extended layout,
CSV, Excel, the ERDR workbook). The summary shows the class sizes, the feature types and the
permitted k.

![Dataset](images/gui/dataset.png)

## Configure

Step 0 (normalizer, metric — with a parameter form generated from the plug-in — feature selection,
rounding) and Steps 1–6 (k with the k rule, ε, the readings A, B, C and the scope of z). The title
row shows which preset the settings match — `literal`, `closest` or `custom` — next to the
*Literal preset*, *Closest preset* and *Reset* buttons; a ⚠ box at the top names every switch that
differs from the literal article text. **File → Open configuration… / Save configuration as…**
read and write configuration files.

![Configure](images/gui/configure.png)

## Run

Runs in the background; the log shows every stage. *Save a run folder* writes a repeatable run.

![Run](images/gui/run.png)

## Results

Every table of the ERDR workbook for the run — key results, the data, ρ (and ρ_I, ρ_J), the
neighbour ranks, Step 1, the enemy spheres, the queue with its tie criteria, the iterations, the
counters, D and F with every object's route, the class composition and the 17 cases — and the
figures. Colours: blue = training sample D, orange = validation sample F, yellow = the selected
object or a tie decided by r, violet = a counter lowered by Step 5. Hover a cell for its exact
value.

![Iterations](images/gui/results-iterations.png)

![Step 1](images/gui/results-characteristics.png)

![Figures](images/gui/results-figure.png)

## Readings & k

Compare every reading of A, B, C (optionally with the own-class z) and sweep k for the literal,
the closest and the current reading — on all 270 objects this reproduces the workbook's
comparison with the article's Table 1.

![Readings and k](images/gui/readings.png)

## Export

Choose the formats and a folder; the readings comparison and the k sweep can be included.

![Export](images/gui/export.png)

## The portable executable

`scripts\build_exe.py` freezes the application with PyInstaller into `dist\erdr-gui\` (a folder,
copied as a whole; nothing is installed) and `dist\erdr-gui-<version>-windows.zip`, then runs
`erdr-gui.exe --self-test` in an empty folder — the built-in default dataset, a run that must give
the workbook's D, a table, a figure, the readings and every export format (ADR-013). CI builds it
on every push and attaches it to each release.

The screenshots are made by `scripts\gui_screenshots.py`.
