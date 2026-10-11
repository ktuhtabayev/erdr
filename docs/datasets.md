# Datasets

## The datasets folder

```text
datasets/
  default.dat, default.csv            Heart-Disease (7, 13, 2) — the default experiment
  Heart-Disease/
    Heart-Disease (270, 13, 2).dat    the full Statlog (Heart) sample
    Heart-Disease (270, 13, 2).csv
  <Family>/<Name (m, n, c)>.dat|.csv  further datasets — just drop them in
  synthetic/                          reserved, not read
```

`erdr data list` shows the catalogue, `erdr data check` verifies every file (readable, header
(m, n, c) equal to the file name, `.dat` and `.csv` holding identical data, SHA-256 per file) and
`erdr data info <id>` summarizes one: sizes, types, classes, permitted k. Datasets are named by id
(`heart-disease-270`), display name (`Heart-Disease (270, 13, 2)`), `default` or a path. The
folder is found from the working directory upwards; `ERDR_DATASETS` overrides it. Without a
folder (the Windows executable) the package's built-in copies are used (ADR-007).

## The extended layout

The author's format, identical to the template project's:

```text
7,13,2,,,,,,,,,,,                       first row: m, n, c (the .csv pads it to n + 1 cells)
70,1,4,130,322,0,2,109,0,2.4,2,3,3,2    m rows: n feature values, then the class label
…
1,0,0,1,1,0,0,1,0,1,0,1,0,              last row: type flags, 1 = quantitative (I), 0 = nominal (J)
```

- `.csv` — comma-separated, CRLF line ends, integral values without a decimal point, the type
  row ends with an empty cell under the class column;
- `.dat` — space-separated, LF line ends, every feature value as a decimal (`70.0`), the class as
  it is.

`erdr.data.write_extended` writes exactly these conventions: reading and writing the author's
files reproduces them **byte for byte** (tested for the default and the 270-object files). The
files are stored byte for byte in Git (`.gitattributes`: `datasets/** -text`).

## The default dataset Heart-Disease (7, 13, 2)

`datasets/default.csv` and `default.dat` are rows **1, 10, 73, 143, 224, 226, 239** of
Heart-Disease (270, 13, 2), in that order, as S₁ … S₇ — the 7 objects of the ERDR workbook
(sheet *Dataset*). The data lines are copied byte for byte from the 270-object files; only the
first row changes to `7,13,2` / `7 13 2`. Class 1 = absence (K1: S₃, S₆, S₇), class 2 = presence
of heart disease (K2: S₁, S₂, S₄, S₅). The workbook explains the choice on *Object Selection*:
the smallest sample in which every one of the 17 cases occurs; rows 1 and 10 are S₁ and S₁₀ of
the earlier Heart-Disease (10, 13, 2) experiment.

The type flags of the file are kept: 6 quantitative features (x₁, x₄, x₅, x₈, x₁₀, x₁₂) and 7
nominal. The article (§3) counts 7 quantitative and 6 nominal — probably x₁₁, the ordered slope,
as quantitative; `dataset.feature_types` can override any type.

## Other formats

| Format | Files | Notes |
|---|---|---|
| `extended` (alias `template-extended`) | `.csv`, `.dat` | the author's layout; decimal commas accepted in `.dat` |
| `erdr-workbook` | `.xlsx` | the *Dataset* sheet of the ERDR workbook (x₁ … x₁₃ columns, *Type* row) |
| `csv` | `.csv`, `.txt` | a table with a header row; delimiter detected; class column last by default |
| `xlsx` | `.xlsx` | a table with a header row on the first sheet (or `dataset.sheet`) |
| `parquet` | `.parquet` | needs the extra `[parquet]` (pyarrow) |

In tables with a header row, types come from `dataset.feature_types`; others are inferred
(numeric → quantitative, otherwise nominal) **with a warning**, and nominal text becomes codes in
alphabetical order. Missing values are rejected with a message naming the cells. Class labels are
ordered numerically (or alphabetically): the first is K1.

## Built-in datasets

| Name | Content |
|---|---|
| `heart-disease-7` | Heart-Disease (7, 13, 2) — the default (byte-for-byte copy of `default.csv`) |
| `heart-disease-270` | Heart-Disease (270, 13, 2) — Statlog (Heart), UCI, CC BY 4.0 |
| `guide-example` | ERDR-Guide (7, 4, 2) — the worked example of the step-by-step guide |

Use them as `erdr run heart-disease-270` or `dataset.path: builtin:guide-example`.

## Writing the result

Every run folder holds `training.dat|csv` and `validation.dat|csv` (`output.dataset_formats`),
and the `datasets` export writes the same — the two samples in the extended layout with the
original values, ready for the next experiment of the ensemble.
