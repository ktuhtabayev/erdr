# Configuration

One `ExperimentConfig` (pydantic v2) describes a run completely. Unknown keys are errors, values
are checked, instances are immutable, and the SHA-256 of the canonical JSON form identifies a
configuration independently of its file format (ADR-011). YAML, TOML and JSON are read and
written.

```powershell
erdr config show                      # the default (literal) configuration
erdr config show --preset closest     # B = 2 + own-class z
erdr config init my.yaml              # start a file
erdr config check my.yaml             # validate; hash, preset, non-literal readings
erdr run -c my.yaml
```

## The default (literal) configuration

```yaml
schema_version: 1
name: erdr
description: ''
dataset:
  path: null              # null = datasets/default.dat; or a file, a dataset id, builtin:<name>
  format: auto            # auto | extended | erdr-workbook | csv | xlsx | parquet
  sheet: null
  class_column: null
  id_column: null
  feature_types: null     # {name: quantitative | nominal} overrides the file's types
  missing_values: error
preprocessing:
  normalizer: {name: minmax, params: {}}
distance:
  metric: {name: auto, params: {}}     # auto = the metric of the dataset type, or a metric
  type_metrics:                        # the metric auto takes for each dataset type (ADR-022)
    quantitative: {name: manhattan, params: {}}
    nominal: {name: hamming, params: {}}
    heterogeneous: {name: zhuravlev, params: {}}
  features: auto          # auto | all | quantitative | nominal | [feature names]
  decimals: 10
erdr:
  k: 3
  k_rule: enforce         # enforce | warn | off
  epsilon: 0.001
  d_decimals: 10
  readings:
    self_in_l: included   # A: included (1) | excluded (2)
    blocked_cover: kept   # B: kept (1) | dropped (2)
    step5_return: after-all   # C: after-all (1) | first-move (2)
    z_scope: all          # all | own-class
output:
  runs_dir: runs
  dataset_formats: [dat, csv]
```

A plug-in may be given by name alone: `normalizer: rank`.

## Step 0

`preprocessing.normalizer` — `minmax` (default), `none`, `z-score` (`ddof`: 1 or 0), `robust`,
`max-abs`, `decimal-scaling`, `rank`, `unit-length`. Every normalizer is fitted on the objects of
E₀ and maps a feature without spread to 0; nominal codes are never changed.

`distance.metric` — `auto` (default: the metric of the dataset type, below), `zhuravlev`
(aliases `zhuravlyov`, `juravlev`), `weighted-zhuravlev` (`quantitative_weight`,
`nominal_weight`, `feature_weights`), `heom`, `gower`, `manhattan`, `euclidean`, `chebyshev`,
`minkowski` (`p ≥ 1`), `canberra`, `cosine`, `mahalanobis`, `hamming`.
`distance.features: auto` gives every metric its domain — all features for heterogeneous metrics,
set I for Euclidean and the like, set J for Hamming; an explicit selection outside the domain is
an error that names the features.

**The metric follows the dataset type** ([Datasets](datasets.md#dataset-types), ADR-022). With
`metric: auto` the metric comes from `distance.type_metrics` by the type of the dataset —
quantitative → `manhattan`, nominal → `hamming`, heterogeneous → `zhuravlev`. These are the
Zhuravlev metric and its two parts, so `auto` gives the Zhuravlev distances bit for bit on every
dataset (the literal default). Each entry must suit its type: a quantitative or heterogeneous
metric for quantitative datasets, Hamming or a heterogeneous metric for nominal ones, a
heterogeneous metric for heterogeneous ones (`erdr config check` verifies it); an entry may carry
parameters:

```yaml
distance:
  metric: auto
  type_metrics:
    quantitative: {name: minkowski, params: {p: 3}}   # changes the results on quantitative data
```

A metric named in `metric` is used for every dataset it is defined on: on a dataset without its
feature type (Euclidean on a nominal dataset) the run stops with an error that lists the metrics
that suit; a single-type metric on a heterogeneous dataset runs on its part of the features and is
flagged ⚠.

## Steps 1–6

- `erdr.k` — k of z(Sᵢ, k).
- `erdr.k_rule` — `enforce` (default) rejects a k outside odd 3 … 2·min|Kᵢ| − 3; `warn` logs it
  and records it in the run; `off` only requires that z(Sᵢ, k) exists (ADR-005).
- `erdr.epsilon` — ε > 0 of the blocking; any ε gives the same result.
- `erdr.d_decimals` — rounding of d.
- `erdr.readings` — the open points of §1.1 ([The algorithm](algorithm.md#readings-the-open-points)).

## Presets and shipped files

| Preset | Readings | Use |
|---|---|---|
| `literal` (default) | A = B = C = 1, z of any class | the article's text; reproduces the workbook |
| `closest` | B = 2, own-class z | the reading closest to the article's Table 1 |

`configs/default.yaml` (the workbook), `configs/heart-disease-270.yaml` (literal, |D| = 198 for
k = 3) and `configs/heart-disease-270-closest.yaml` (|D| = 75 for k = 3). Every YAML/TOML file
written by the package starts with a comment header naming the preset and every non-literal
reading.

## Command-line overrides

`erdr run` accepts `--preset`, `--k`, `--epsilon`, `--reading 121`, `--z-scope own-class`,
`--metric`, `--normalizer` and `--k-rule` on top of a configuration file; the result is validated
like a file.
