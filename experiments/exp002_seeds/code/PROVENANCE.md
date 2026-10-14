# exp002 code provenance

- `exp002_seeds.py` in this folder is byte-identical to the script that ran (it was not edited after launch).
- `ids_common.py` was imported at process start (2026-10-14 ~16:55 local). It was edited on disk WHILE
  exp002 was running (an already-imported module is not reloaded, so the run was unaffected):
    1. CICIDS2018 loader appended (new functions only)
    2. fit_hierarchy / score_hierarchy / snapshot_code added; add_taxonomies gained an optional
       keep_fine argument (default behaviour unchanged); make_split docstring note
    3. load_2017 made memory-lean (per-file cleaning before concat), per_class gained recall_ci95,
       confusion counts added to score_hierarchy
  Therefore the `ids_common.py` sha256 recorded in MANIFEST.json is the post-edit file, NOT the
  exact revision executed. The exact imported revision was not snapshotted (oversight, fixed for
  exp003+ via ids_common.snapshot_code).
- Functional equivalence evidence: exp002's own sanity gate reproduced exp001 (an independent,
  frozen script) to 1e-9 on both splits. The lean loader is separately gated by
  experiments/gate_loader_equivalence before any later experiment runs.
- exp002 saved per-run per-class metrics but not confusion matrices or per-class CIs; it was not
  re-run to add them.
