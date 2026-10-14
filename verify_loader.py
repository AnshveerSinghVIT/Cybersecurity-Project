"""
Gate: the memory-lean ids_common.load_2017 must reproduce exp001 EXACTLY before any queued
experiment uses it. Checks data-level statistics and re-runs the exp001 row-order config
(RF seed 42), requiring every headline metric to match the frozen exp001 JSON to 1e-9.

Exit code 0 = pass, 1 = mismatch. Writes experiments/gate_loader_equivalence/result.json.
"""
import json
import os
import sys
import time

import numpy as np

import ids_common as C

OUT = os.path.join(C.HERE, "experiments", "gate_loader_equivalence")
EXP001 = os.path.join(C.HERE, "experiments", "exp001_baseline", "multiclass_baseline_temporal.json")


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ref = json.load(open(EXP001, encoding="utf-8"))
    checks = {}

    def check(name, expected, got):
        ok = (abs(expected - got) < 1e-9) if isinstance(expected, float) else (expected == got)
        checks[name] = {"expected": expected, "got": got, "ok": bool(ok)}
        print(f"  [{'OK' if ok else 'MISMATCH'}] {name}: expected={expected} got={got}", flush=True)

    df, feats, info = C.load_2017()
    check("rows_raw", ref["rows_raw"], info["rows_raw"])
    check("rows_after_nan_inf_drop", ref["rows_after_nan_inf_drop"], info["rows_after_nan_inf_drop"])
    check("n_features", ref["n_features"], info["n_features"])
    conf, _ = C.conflict_stats(df)
    check("unique_feature_rows", ref["duplicates"]["unique_feature_rows"], conf["unique_feature_rows"])
    check("conflicting_groups", ref["duplicates"]["conflicting_groups"], conf["conflicting_groups"])
    check("rows_in_conflicting_groups", ref["duplicates"]["rows_in_conflicting_groups"],
          conf["rows_in_conflicting_groups"])
    check("conflict_rows_by_label", ref["duplicates"]["conflict_rows_by_raw_label"], conf["conflict_rows_by_label"])
    df = C.apply_dedup(df, "drop_conflicts")
    check("rows_after_dedup", ref["rows_after_dedup_and_conflict_drop"], len(df))
    tax = C.add_taxonomies(df, min_support=500)
    check("label_support_after_dedup", ref["label_support_after_dedup"], tax["label_support"])
    df = df.sort_values("_pos").reset_index(drop=True)
    fingerprint = int(np.bitwise_xor.reduce(df["_h"].values))  # order-independent content fingerprint

    tr, te = C.make_split(df, "temporal")
    check("train_rows", ref["split"]["train_rows"], int(tr.sum()))
    check("test_rows", ref["split"]["test_rows"], int(te.sum()))
    res = C.evaluate_hierarchy(df.loc[tr], df.loc[te], feats, model_seed=42, trees=100)
    check("stage1_macro_f1", ref["stage1_binary"]["macro_f1"], res["stage1"]["macro_f1"])
    for level in ("family", "fine"):
        for view in ("gt_malicious", "end_to_end"):
            check(f"{level}_{view}_macro_f1", ref[f"stage2_{level}"][view]["macro_f1"],
                  res[f"stage2_{level}"][view]["macro_f1"])

    passed = all(c["ok"] for c in checks.values())
    out = {"gate": "loader_equivalence", "passed": passed, "checks": checks,
           "dedup_content_fingerprint_xor": fingerprint, "runtime_sec": round(time.time() - t0, 1),
           "code": C.snapshot_code(OUT, ["verify_loader.py", "ids_common.py"]), "env": C.env_info()}
    json.dump(out, open(os.path.join(OUT, "result.json"), "w", encoding="utf-8"), indent=2)
    print("GATE", "PASSED" if passed else "FAILED")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
