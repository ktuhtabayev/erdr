"""Pure numerical core of ERDR: no I/O, no GUI, deterministic.

Every public function names the article step it implements:

* Step 0 — :mod:`.normalizers` (scale unification), :mod:`.metrics` (ρ) and
  :mod:`.distances` (the pipeline from values to the distance matrix);
* Step 1 — :mod:`.characteristics` (r, g, z, d) on :mod:`.neighbours`; the k rule in
  :mod:`.k_rule`;
* Steps 2–6 — :mod:`.algorithm` (queue, L, blocking, counters, D and F) with the readings of the
  open points in :mod:`.readings`;
* :mod:`.hyperspheres` — Steps 1–5 as hyperspheres: the enemy sphere and the k-sphere of every
  object, the spheres around the selected object of every iteration, the diagrams' layout;
* :mod:`.cases` — the 17 cases of the workbook's checklist.

:mod:`.registry` provides the plug-in mechanism.
"""
