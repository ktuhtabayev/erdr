# Datasets

## The datasets folder

The folder is organized by **dataset type** — the types of the features (ADR-021):

```text
datasets/
  default.dat, default.csv              Heart-Disease (7, 13, 2) — the default experiment
  Quantitative/                         every feature quantitative (set J empty)
    Cancer/Cancer (589, 44, 2)
    Hypertension/Hypertension (147, 29, 2)
    Spambase/Spambase (4204, 57, 2)
    TCGA_LUAD/TCGA_LUAD (589, 57772, 2)   on the author's computer only (see below)
  Nominal/                              every feature nominal (set I empty)
    Molecular-Biology/Molecular-Biology (106, 57, 2), (100, 50, 2), (100, 10, 2)
    Uzb-Kor/Uzb-Kor (100, 24, 2)
  Heterogeneous/                        quantitative and nominal features
    German/German (1000, 20, 2)
    Heart-Disease/Heart-Disease (270, 13, 2)   the full Statlog (Heart) sample
    Ionosfera/Ionosfera (350, 33, 2)
  <Type>/<Family>/<Name (m, n, c)>.dat|.csv   further datasets — just drop them in
  Datasets-Tree.txt, */ReadMe.txt       the author's notes (features, classes, sources)
  synthetic/                            reserved, not read
```

Every dataset has a `.dat` and a `.csv` file holding the same data (the `.dat` is read) and a
`ReadMe.txt` with the meaning of its features and classes and its source. A family folder directly
under `datasets/` (outside the type folders) is still read; `erdr data list` shows it as *Other*.

`erdr data list` shows the catalogue by type folder, `erdr data check [DATASET…]` verifies every
file — readable, header (m, n, c) equal to the file name, `.dat` and `.csv` holding identical data,
**the feature types matching the type folder**, **the file written in the author's conventions
byte for byte**, SHA-256 per file — and `erdr data info <id>` summarizes one: sizes, dataset type,
the metric it gets and the metrics that suit it, feature types, classes, permitted k, the memory
of a run. Datasets are named by id (`heart-disease-270`), display name (`Heart-Disease (270, 13,
2)`), `default` or a path; ids are `<name>-<m>`, with `-<n>` added when two datasets would share
one (`molecular-biology-100-10`, `molecular-biology-100-50`). The folder is found from the working
directory upwards; `ERDR_DATASETS` overrides it. Without a folder (the Windows executable) the
package's built-in copies are used (ADR-007).

## Dataset types

| Type | Folder | Features | Metric (`auto`) | Metrics that suit it |
|---|---|---|---|---|
| quantitative | `Quantitative/` | all quantitative (I) | `manhattan` | the quantitative metrics (Manhattan, Euclidean, Chebyshev, Minkowski, Canberra, cosine, Mahalanobis) and the heterogeneous ones |
| nominal | `Nominal/` | all nominal (J) | `hamming` | Hamming and the heterogeneous metrics |
| heterogeneous | `Heterogeneous/` | both | `zhuravlev` | the heterogeneous metrics (Zhuravlev, weighted Zhuravlev, HEOM, Gower) |

The type of a dataset comes from its type flags (`Dataset.dataset_type`); `erdr data check`
reports a dataset whose flags contradict its folder — a nominal feature in `Quantitative/`, say.

**The metric follows the dataset type** (ADR-022). `distance.metric: auto` (the default) takes the
metric of the type from `distance.type_metrics`. The defaults are the Zhuravlev metric of the
article and its two parts: on quantitative data ρ = Σ_I |x′ − y′| is the Manhattan distance of the
unified values, on nominal data ρ = Σ_J [x ≠ y] the Hamming distance — **bit for bit**, so `auto`
gives the literal results on every dataset (tested). A metric named explicitly must be defined on
the dataset's features: a quantitative metric on a nominal dataset (or Hamming on a quantitative
one) is an error that lists the metrics that suit; a single-type metric on a heterogeneous dataset
runs on its part of the features and is **flagged ⚠** in the CLI, the GUI and every export. Step 0's
normalizer only acts on quantitative features, so on a nominal dataset it has no effect.

## The datasets

The default reading (k = 3, `auto`) on every dataset of the folder:

| Dataset | Type | I / J | Classes (K1 / K2) | k ≤ | \|D\| | Source |
|---|---|---|---|---|---|---|
| Cancer (589, 44, 2) | quantitative | 44 / 0 | 530 / 59 | 115 | 583 | not recorded (perhaps 44 genes of TCGA_LUAD) |
| Hypertension (147, 29, 2) | quantitative | 29 / 0 | healthy 111 / ill 36 | 69 | 137 | N. A. Ignatev's monograph |
| Spambase (4204, 57, 2) | quantitative | 57 / 0 | not spam 2528 / spam 1676 | 3349 | 3105 | UCI Spambase without its 391 repeated rows |
| TCGA_LUAD (589, 57772, 2) | quantitative | 57772 / 0 | adenocarcinoma 530 / healthy 59 | 115 | 523 | GDC TCGA LUAD, log-transformed (UCSC Xena) |
| Molecular-Biology (106, 57, 2) | nominal | 0 / 57 | promoter 53 / not 53 | 103 | 86 | UCI promoter gene sequences, A C G T coded 1–4 |
| Molecular-Biology (100, 50, 2) | nominal | 0 / 50 | 50 / 50 | 97 | 72 | the 106 without S₅₁–S₅₃, S₁₀₄–S₁₀₆; first 50 positions |
| Molecular-Biology (100, 10, 2) | nominal | 0 / 10 | 50 / 50 | 97 | 52 | the same objects, first 10 positions |
| Uzb-Kor (100, 24, 2) | nominal | 0 / 24 | Uzbek 50 / Korean 50 | 97 | 65 | questionnaire, NUUz sociology department |
| German (1000, 20, 2) | heterogeneous | 7 / 13 | good 700 / bad 300 | 597 | 696 | UCI Statlog (German Credit) |
| Heart-Disease (270, 13, 2) | heterogeneous | 6 / 7 | absence 150 / presence 120 | 237 | 198 | UCI Statlog (Heart) |
| Ionosfera (350, 33, 2) | heterogeneous | 32 / 1 | bad 125 / good 225 | 247 | 295 | Ionosphere (Kaggle), without repeated rows and constant columns |

Notes from the review of the files (2026-10-17; the values are the author's, unchanged):

- Uzb-Kor codes an unanswered question as 0 and several answers as one code (12, 123, 1234, 204,
  1004, 1034); each code is a category of its own. Its ReadMe lists a few answers still to be
  compared with the questionnaires.
- Ionosfera's x₁ is nominal (0/1), so the dataset is heterogeneous.
- Spambase (4204, 57, 2) is the UCI file of 4595 objects without its repeated rows (first
  occurrences, in order) and with the classes 0/1 renumbered 1/2; the 4595-object file and the
  DDoS files are no longer in the folder.

### TCGA_LUAD stays on the author's computer

`TCGA_LUAD (589, 57772, 2)` is 391 MB per file — over GitHub's limit of 100 MB — so its `.dat` and
`.csv` are in `.gitignore`; its `ReadMe.txt` (in Git) says where to download it. When the files
are present, erdr catalogues and runs it like any other dataset: it is read row by row, and a run
needs about 790 MB of memory (162 s on the development laptop, |D| = 523). `erdr data info`, `erdr
run` and the GUI warn when a run needs more memory than is free. It is not built into the package
or the Windows executable.

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

Numbers are written in the shortest form that reads back exactly, never with an exponent
(`0.00003`, not `3e-05`). `erdr.data.write_extended` writes exactly these conventions — those of
`default.csv` and `default.dat` — and every dataset file of the folder follows them: reading and
writing any of them reproduces it **byte for byte** (tested for every file), and `erdr data check`
names the first line of a file that departs from them. The new datasets' `.dat` files came with
Windows line ends and integers without a decimal point; they were rewritten in these conventions
on 2026-10-17 (the data unchanged, checked against the `.csv`). The files are stored byte for
byte in Git (`.gitattributes`: `datasets/** -text`).

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

The package carries byte-for-byte copies of the `.csv` files, so the Windows executable has every
dataset of the folder except TCGA_LUAD (tested):

| Name | Type | Content |
|---|---|---|
| `heart-disease-7` | heterogeneous | Heart-Disease (7, 13, 2) — the default (copy of `default.csv`) |
| `heart-disease-270` | heterogeneous | Heart-Disease (270, 13, 2) — Statlog (Heart), UCI, CC BY 4.0 |
| `guide-example` | heterogeneous | ERDR-Guide (7, 4, 2) — the worked example of the step-by-step guide |
| `cancer-589`, `hypertension-147`, `spambase-4204` | quantitative | the datasets of `Quantitative/` |
| `molecular-biology-106`, `molecular-biology-100-50`, `molecular-biology-100-10`, `uzb-kor-100` | nominal | the datasets of `Nominal/` |
| `german-1000`, `ionosfera-350` | heterogeneous | the datasets of `Heterogeneous/` |

Use them as `erdr run heart-disease-270` or `dataset.path: builtin:guide-example`; the GUI lists
them by type.

## Writing the result

Every run folder holds `training.dat|csv` and `validation.dat|csv` (`output.dataset_formats`),
and the `datasets` export writes the same — the two samples in the extended layout with the
original values, ready for the next experiment of the ensemble.
