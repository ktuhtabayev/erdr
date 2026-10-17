# Command line

`erdr` (or `python -m erdr`). Global options: `--version`, `-v`/`-vv` (more log output). Errors
are reported in one line with exit code 2; failed validations exit with 1.

On a terminal the output uses the project's colours (ADR-019): column headers by what they hold,
the classes K1, K2 and the samples D, F in their colours, ⚠ lines orange, ✓ green and ✗ red.
Redirected output has no colour codes, and `NO_COLOR=1` turns colour off.

| Command | What it does |
|---|---|
| `erdr run [DATASET] [-c FILE]` | runs ERDR; prints Step 1, every iteration, D, F, the routes and the cases (`--brief` for the result only, `--all` for every row) |
| `erdr spheres [DATASET] [-s OBJECT \| -t ITERATION] [-f FIGURE]` | Steps 1–5 as hyperspheres: every object's spheres, one object's, or one iteration's; saves the figure |
| `erdr readings [DATASET] [--both-z]` | every combination of the readings A, B, C (and the own-class z) |
| `erdr sweep [DATASET] [--k 3-41] [-r 111 -r 121:own]` | \|D\| and its class composition for many k and readings |
| `erdr validate [--against WORKBOOK] [--fast] [--details]` | the package against every computed sheet of the ERDR workbook |
| `erdr runs` · `erdr export [RUN] -f FORMATS` | list run folders; repeat a saved run and export it (`--readings`, `--sweep`) |
| `erdr data list` · `check [DATASET…]` · `info [DATASET] [-c FILE]` | the dataset folder by type, its checks (type folders, file conventions), one dataset's summary (type, metric, memory) |
| `erdr config show` · `init FILE` · `check FILE` | presets and configuration files |
| `erdr plugins` | normalizers, metrics, dataset formats, export formats, built-in datasets |
| `erdr gui [DATASET] [-c FILE]` | the desktop application |

## erdr run

```powershell
erdr run                                         # the workbook's experiment
erdr run heart-disease-270 --brief -k 5
erdr run -p closest heart-disease-270            # preset readings
erdr run -r 211 --z-scope own-class -k 1 --k-rule warn
erdr run --metric minkowski --normalizer robust  # other Step 0 plug-ins (defaults for their parameters)
erdr run uzb-kor-100 --brief                     # a nominal dataset: metric hamming (auto)
erdr run -c configs\heart-disease-270.yaml --save --export all
```

`--save` writes a run folder (`runs/<time>_<config hash>/`: manifest, configuration, the dataset,
Step 1 and the trace, the training and validation samples); `--export FORMATS` writes the chosen
formats into `<run>/export` or `--out`. Overrides are applied to the configuration file's values
and validated.

## erdr data

```text
> erdr data list
datasets folder: D:\PhD\CODING\erdr\datasets
  default                    default                            (7, 13, 2)       .dat, .csv
Quantitative/  every feature quantitative · metric (auto): manhattan
  cancer-589                 Cancer (589, 44, 2)                (589, 44, 2)     .dat, .csv
  …
  tcga-luad-589              TCGA_LUAD (589, 57772, 2)          (589, 57772, 2)  .dat, .csv  401 MB
Nominal/  every feature nominal · metric (auto): hamming
  …
Heterogeneous/  quantitative and nominal features · metric (auto): zhuravlev
  …

> erdr data info uzb-kor-100
Uzb-Kor (100, 24, 2)  (100, 24, 2)
  type          nominal — every feature nominal
  classes       K1 = 1: 50 · K2 = 2: 50
  quantitative  0: —
  nominal       24: x₁, x₂, …, x₂₄
  metric        hamming (auto · nominal dataset)
  suited        zhuravlev, weighted-zhuravlev, heom, gower, hamming
  memory        about 1 MB for a run
  permitted k   3, 5, …, 97  (odd k from 3 to 2·min|Kᵢ| − 3 = 97)
```

`erdr data check` checks every dataset of the folder (or only the ones named): header against
name, `.dat` against `.csv`, feature types against the type folder, the author's file conventions
line by line; it exits with 1 when a problem is found. `erdr data info -c FILE` shows the metric
that configuration runs on the dataset, or ⚠ why it cannot. `erdr run` warns before a run that
needs more memory than is free (TCGA_LUAD: about 790 MB).

## erdr spheres

```powershell
erdr spheres                              # every object's enemy sphere and k-sphere, the checks,
                                          # and the spheres around Sᵢ in every iteration
erdr spheres --object S2 -f s2.svg        # the two spheres of S₂, and their diagram
erdr spheres -t 2 -f iteration-2.png      # iteration 2: every object's sphere, L, the moves
erdr spheres heart-disease-270 -p closest -t 1
```

Without `--object` or `--iteration`, `--figure` saves the spheres of every object (up to 12
panels). The settings options are those of `erdr run`; a non-literal reading is flagged with ⚠.

## erdr readings and erdr sweep

```text
$ erdr readings --both-z
…
6 different training samples from 16 readings

$ erdr sweep heart-disease-270 --k 3,5,7,13,17 -r 111 -r 121:own
```

A sweep without `--k` covers every permitted k; ranges like `3-41` step over odd k. Readings are
codes of A, B, C; `:own` takes z over the own class. Pairs for which z(Sᵢ, k) does not exist are
skipped.

## erdr validate

```text
$ erdr validate
ERDR algorithm [Heart-Disease (7, 13, 2)].xlsx  ·  tolerance 1e-09
  Parameters                     5 checks  ✓
  …
  Hyperspheres (Step 1)        235 checks  ✓
  …
  Validation                    53 checks  ✓
  2927 checks
validation passed
```

The workbook is found under `resources/Experiments/` from the working directory upwards;
`--fast` skips the 270-object runs of *Article Table 1 Check*.
