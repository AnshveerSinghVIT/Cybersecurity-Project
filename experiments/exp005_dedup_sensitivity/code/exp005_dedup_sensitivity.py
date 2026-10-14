"""
exp005: sensitivity of results to the deduplication / label-conflict policy.

Concern addressed: dropping conflicting groups changes the evaluated population (e.g. PortScan
158,930 raw rows -> 1,850), so a reviewer can argue the policy, not the model, drives the numbers.

Design
  - The train/test split is assigned per UNIQUE FEATURE VECTOR (hash group) BEFORE any policy is
    applied, so every policy sees the same partition of groups and no exact duplicate crosses
    train/test under any policy. Group order key = first occurrence (row order); group label for
    stratification = label at first occurrence.
  - Policies (ids_common.apply_dedup): drop_conflicts | keep_first | majority | none
  - Each policy is scored on (a) its OWN test population and (b) a COMMON test set: conflict-free
    test groups, one row each - identical across policies. (b) isolates the training-side effect
    of the policy; (a) shows what a paper using that policy would report.
  - Extra config "none_rowsplit": no dedup + naive row-level stratified random split (the original
    pre-fix setup). Comparing it with none + group-level random split measures exact-duplicate
    leakage across the split directly.
  - Fine taxonomy is FIXED across policies (labels with >=500 rows under drop_conflicts), so class
    definitions don't move with the population.
  - Model seed: --seeds (default 42). exp002 gives the model-seed noise floor for comparison.

Usage: python exp005_dedup_sensitivity.py [--seeds 42] [--splits temporal random]
"""
import argparse
import json
import os
import time

import numpy as np
from sklearn.model_selection import train_test_split

import ids_common as C

EXP = os.path.join(C.HERE, "experiments", "exp005_dedup_sensitivity")
RUNS = os.path.join(EXP, "runs")


def group_split(first, scheme, seed=42, test_frac=0.2, purge_frac=0.01):
    """first: one row per hash group (sorted by _pos) with columns _h, label_raw.
    Returns (train_hashes, test_hashes) as sets."""
    n = len(first)
    is_test = np.zeros(n, dtype=bool)
    is_gap = np.zeros(n, dtype=bool)
    if scheme == "temporal":  # row-order proxy, see ids_common.make_split
        for _, idx in first.groupby("label_raw").indices.items():
            m = len(idx)
            cut = int(m * (1 - test_frac))
            gap = max(1, int(m * purge_frac)) if m >= 100 else 0
            is_gap[idx[cut - gap:cut]] = True
            is_test[idx[cut:]] = True
    else:
        _, te = train_test_split(np.arange(n), test_size=test_frac, stratify=first["label_raw"],
                                 random_state=seed)
        is_test[te] = True
    h = first["_h"].values
    return set(h[~is_test & ~is_gap]), set(h[is_test])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--splits", nargs="+", default=["temporal", "random"])
    ap.add_argument("--trees", type=int, default=100)
    args = ap.parse_args()
    os.makedirs(RUNS, exist_ok=True)
    t0 = time.time()

    print("Loading ...")
    df, feats, info = C.load_2017()
    df = df.drop(columns=["Label", "_src"])  # memory: unused text columns
    df = df.sort_values("_pos").reset_index(drop=True)
    keep_cols = feats + ["_h", "label_raw", "fine", "family", "binary"]
    conf, conflict_rows = C.conflict_stats(df)
    conflict_hashes = set(df.loc[conflict_rows, "_h"].unique())

    # fixed fine taxonomy from the drop_conflicts population
    ref = C.apply_dedup(df, "drop_conflicts")
    support_ref = ref["label_raw"].value_counts()
    keep_fine = sorted(l for l, n in support_ref.items() if n >= 500)
    del ref
    print("  fixed fine classes:", keep_fine)

    first = df.drop_duplicates("_h", keep="first")[["_h", "label_raw"]].reset_index(drop=True)
    results = {}
    populations = {}
    for scheme in args.splits:
        tr_h, te_h = group_split(first, scheme, seed=42)
        # common test set: conflict-free test groups, one row each (identical for every policy)
        common = df[df["_h"].isin(te_h) & ~df["_h"].isin(conflict_hashes)].drop_duplicates("_h")
        common = common.copy()
        C.add_taxonomies(common, keep_fine=keep_fine)
        populations[f"{scheme}/common_test"] = common["label_raw"].value_counts().to_dict()
        for policy in C.DEDUP_POLICIES:
            d = C.apply_dedup(df, policy)
            C.add_taxonomies(d, keep_fine=keep_fine)
            train = d.loc[d["_h"].isin(tr_h), keep_cols]
            test = d.loc[d["_h"].isin(te_h), keep_cols]
            del d  # memory: only the train/test slices are needed from here
            populations[f"{scheme}/{policy}/train"] = train["label_raw"].value_counts().to_dict()
            populations[f"{scheme}/{policy}/test"] = test["label_raw"].value_counts().to_dict()
            for seed in args.seeds:
                rid = f"{scheme}_{policy}_model{seed}"
                path = os.path.join(RUNS, rid + ".json")
                if os.path.exists(path):
                    results[rid] = json.load(open(path, encoding="utf-8"))
                    print(f"skip {rid}")
                    continue
                t1 = time.time()
                models = C.fit_hierarchy(train, feats, seed, args.trees)
                r = {"run_id": rid, "split": scheme, "split_unit": "hash group", "policy": policy,
                     "model_seed": seed, "train_rows": len(train),
                     "own_test": C.score_hierarchy(models, test, feats),
                     "common_test": C.score_hierarchy(models, common, feats)}
                del models
                r["runtime_sec"] = round(time.time() - t1, 1)
                json.dump(r, open(path, "w", encoding="utf-8"), indent=2)
                results[rid] = r
                print(f"{rid}: own mal-F1={r['own_test']['stage1']['malicious_f1']:.4f} "
                      f"famGT={r['own_test']['stage2_family']['gt_malicious']['macro_f1']:.4f} | common "
                      f"mal-F1={r['common_test']['stage1']['malicious_f1']:.4f} "
                      f"famGT={r['common_test']['stage2_family']['gt_malicious']['macro_f1']:.4f} "
                      f"({r['runtime_sec']}s)", flush=True)
            del train, test

    # naive baseline: no dedup, row-level random split (exact duplicates can straddle the split)
    if "random" in args.splits:
        d = df  # last use of df: no copy needed (memory)
        C.add_taxonomies(d, keep_fine=keep_fine)
        _, te = train_test_split(np.arange(len(d)), test_size=0.2, stratify=d["label_raw"], random_state=42)
        is_te = np.zeros(len(d), dtype=bool)
        is_te[te] = True
        train, test = d.loc[~is_te, keep_cols], d.loc[is_te, keep_cols]
        del d, df
        # fraction of test rows whose exact feature vector also occurs in train
        straddle = float(test["_h"].isin(set(train["_h"])).mean())
        populations["random/none_rowsplit/test_rows_with_exact_duplicate_in_train"] = straddle
        for seed in args.seeds:
            rid = f"random_none_rowsplit_model{seed}"
            path = os.path.join(RUNS, rid + ".json")
            if os.path.exists(path):
                results[rid] = json.load(open(path, encoding="utf-8"))
                continue
            t1 = time.time()
            models = C.fit_hierarchy(train, feats, seed, args.trees)
            r = {"run_id": rid, "split": "random", "split_unit": "row", "policy": "none",
                 "model_seed": seed, "train_rows": len(train),
                 "test_rows_with_exact_duplicate_in_train": straddle,
                 "own_test": C.score_hierarchy(models, test, feats)}
            del models
            r["runtime_sec"] = round(time.time() - t1, 1)
            json.dump(r, open(path, "w", encoding="utf-8"), indent=2)
            results[rid] = r
            print(f"{rid}: own mal-F1={r['own_test']['stage1']['malicious_f1']:.4f} "
                  f"famGT={r['own_test']['stage2_family']['gt_malicious']['macro_f1']:.4f} "
                  f"straddle={straddle:.3f} ({r['runtime_sec']}s)", flush=True)
        del train, test

    json.dump({"load": info, "conflicts_before_dedup": conf, "fixed_fine_classes": keep_fine,
               "populations": populations},
              open(os.path.join(EXP, "data_prep.json"), "w", encoding="utf-8"), indent=2, default=str)

    # summary table
    lines = ["| Split | Policy | Test set | n test | Mal-F1 | Benign FPR | Family GT | Family E2E | Fine GT | PortScan fam-GT F1 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for rid, r in sorted(results.items()):
        for view in ("own_test", "common_test"):
            if view not in r:
                continue
            v = r[view]
            ps = v["stage2_family"]["gt_malicious"]["per_class"].get("PortScan", {}).get("f1", float("nan"))
            lines.append(f"| {r['split']} ({r['split_unit']}) | {r['policy']} | {view} | {v['n_test']:,} | "
                         f"{v['stage1']['malicious_f1']:.4f} | {100*v['stage1']['benign_fpr']:.3f}% | "
                         f"{v['stage2_family']['gt_malicious']['macro_f1']:.4f} | "
                         f"{v['stage2_family']['end_to_end']['macro_f1']:.4f} | "
                         f"{v['stage2_fine']['gt_malicious']['macro_f1']:.4f} | {ps:.4f} |")
    table = "\n".join(lines)
    open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8").write(table + "\n")
    print(table)

    code = C.snapshot_code(EXP, ["exp005_dedup_sensitivity.py", "ids_common.py"])
    C.write_manifest(
        EXP, experiment_id="exp005_dedup_sensitivity", depends_on=["exp001_baseline", "exp002_seeds"],
        description="Dedup/label-conflict policy sensitivity with group-level split and a common test set",
        scripts=code, cmd=f"python exp005_dedup_sensitivity.py --seeds {' '.join(map(str, args.seeds))} "
                          f"--splits {' '.join(args.splits)} --trees {args.trees}",
        seeds=args.seeds, seed_meaning="RF random_state; split seed fixed at 42",
        split_definitions={"temporal": "row-order proxy per first-occurrence label, 80/20, 1% purge, over hash groups",
                           "random": "stratified on first-occurrence label, 80/20, seed 42, over hash groups",
                           "none_rowsplit": "row-level stratified random 80/20 seed 42, no dedup"},
        dedup_policies=list(C.DEDUP_POLICIES), fixed_fine_classes=keep_fine,
        runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
