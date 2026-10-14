"""
exp002: seed variability of the exp001 baseline.

Sources of variation are kept SEPARATE:
  temporal/model   - temporal split is deterministic; only the RF seed varies (model randomness)
  random/split     - random split seed varies, RF seed fixed at 42 (split randomness)
  random/model     - random split fixed at seed 42, RF seed varies (model randomness)
Dedup policy, class mapping, features and hyperparameters are identical to exp001.

Sanity gate: the (seed 42, seed 42) runs must reproduce exp001's JSON numbers exactly.

Usage: python exp002_seeds.py [--seeds 42 1 2 3 4] [--aggregate-only]
Each run is saved as it finishes (runs/*.json); re-running skips finished runs.
"""
import argparse
import json
import os
import time

import numpy as np

import ids_common as C

EXP = os.path.join(C.HERE, "experiments", "exp002_seeds")
RUNS = os.path.join(EXP, "runs")
EXP001 = os.path.join(C.HERE, "experiments", "exp001_baseline")


def run_id(scheme, split_seed, model_seed):
    return f"{scheme}_split{split_seed}_model{model_seed}"


def configs(seeds):
    out = [("temporal/model", "temporal", None, s) for s in seeds]
    out += [("random/split", "random", s, 42) for s in seeds]
    out += [("random/model", "random", 42, s) for s in seeds if s != 42]
    return out


def headline(r):
    return {
        "stage1_malicious_f1": r["stage1"]["malicious_f1"],
        "stage1_macro_f1": r["stage1"]["macro_f1"],
        "stage1_benign_fpr": r["stage1"]["benign_fpr"],
        "family_gt_macro_f1": r["stage2_family"]["gt_malicious"]["macro_f1"],
        "family_e2e_macro_f1": r["stage2_family"]["end_to_end"]["macro_f1"],
        "fine_gt_macro_f1": r["stage2_fine"]["gt_malicious"]["macro_f1"],
        "fine_e2e_macro_f1": r["stage2_fine"]["end_to_end"]["macro_f1"],
    }


def aggregate(seeds):
    groups = {}
    for group, scheme, ss, ms in configs(seeds):
        p = os.path.join(RUNS, run_id(scheme, ss, ms) + ".json")
        if os.path.exists(p):
            groups.setdefault(group, []).append(json.load(open(p, encoding="utf-8")))
    # random/model also includes the shared (42,42) run
    shared = os.path.join(RUNS, run_id("random", 42, 42) + ".json")
    if "random/model" in groups and os.path.exists(shared):
        groups["random/model"].insert(0, json.load(open(shared, encoding="utf-8")))

    summary = {}
    for g, runs in groups.items():
        h = [headline(r) for r in runs]
        stat = {k: {"mean": float(np.mean([x[k] for x in h])),
                    "std": float(np.std([x[k] for x in h], ddof=1)) if len(h) > 1 else 0.0,
                    "min": float(np.min([x[k] for x in h])), "max": float(np.max([x[k] for x in h]))}
                for k in h[0]}
        pc = {}
        for level in ("family", "fine"):
            for view in ("gt_malicious", "end_to_end"):
                classes = runs[0][f"stage2_{level}"][view]["per_class"].keys()
                pc[f"{level}/{view}"] = {
                    c: {m: {"mean": float(np.mean([r[f"stage2_{level}"][view]["per_class"][c][m] for r in runs])),
                            "std": float(np.std([r[f"stage2_{level}"][view]["per_class"][c][m] for r in runs], ddof=1))
                            if len(runs) > 1 else 0.0}
                        for m in ("precision", "recall", "f1")}
                    | {"support": runs[0][f"stage2_{level}"][view]["per_class"][c]["support"]}
                    for c in classes}
        s1_recall = {l: {"mean": float(np.mean([r["stage1"]["recall_by_raw_label"][l] for r in runs])),
                         "std": float(np.std([r["stage1"]["recall_by_raw_label"][l] for r in runs], ddof=1))
                         if len(runs) > 1 else 0.0}
                     for l in runs[0]["stage1"]["recall_by_raw_label"]}
        summary[g] = {"n_runs": len(runs), "runs": [r["run_id"] for r in runs], "headline": stat,
                      "per_class": pc, "stage1_recall_by_raw_label": s1_recall,
                      "benign_test_flows": runs[0]["stage1"]["benign_test_flows"]}
    with open(os.path.join(EXP, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    lines = ["| Group | n | Stage1 mal-F1 | Benign FPR | Family GT | Family E2E | Fine GT | Fine E2E |",
             "|---|---|---|---|---|---|---|---|"]
    for g, s in summary.items():
        h = s["headline"]
        f = lambda k, pct=False: (f"{100*h[k]['mean']:.3f}% ± {100*h[k]['std']:.3f}" if pct
                                  else f"{h[k]['mean']:.4f} ± {h[k]['std']:.4f}")
        lines.append(f"| {g} | {s['n_runs']} | {f('stage1_malicious_f1')} | {f('stage1_benign_fpr', True)} | "
                     f"{f('family_gt_macro_f1')} | {f('family_e2e_macro_f1')} | {f('fine_gt_macro_f1')} | "
                     f"{f('fine_e2e_macro_f1')} |")
    table = "\n".join(lines)
    with open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(table)
    return summary


def sanity_check():
    """(42,42) runs must reproduce exp001 exactly."""
    out = {}
    for scheme in ("temporal", "random"):
        old = json.load(open(os.path.join(EXP001, f"multiclass_baseline_{scheme}.json"), encoding="utf-8"))
        rid = run_id(scheme, None if scheme == "temporal" else 42, 42)
        new = json.load(open(os.path.join(RUNS, rid + ".json"), encoding="utf-8"))
        pairs = {
            "stage1_macro_f1": (old["stage1_binary"]["macro_f1"], new["stage1"]["macro_f1"]),
            "family_gt": (old["stage2_family"]["gt_malicious"]["macro_f1"], new["stage2_family"]["gt_malicious"]["macro_f1"]),
            "family_e2e": (old["stage2_family"]["end_to_end"]["macro_f1"], new["stage2_family"]["end_to_end"]["macro_f1"]),
            "fine_gt": (old["stage2_fine"]["gt_malicious"]["macro_f1"], new["stage2_fine"]["gt_malicious"]["macro_f1"]),
            "fine_e2e": (old["stage2_fine"]["end_to_end"]["macro_f1"], new["stage2_fine"]["end_to_end"]["macro_f1"]),
        }
        ok = all(abs(a - b) < 1e-9 for a, b in pairs.values())
        out[scheme] = {"reproduces_exp001": ok, "pairs": pairs}
        print(f"sanity [{scheme}] reproduces exp001: {ok}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2, 3, 4])
    ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--aggregate-only", action="store_true")
    args = ap.parse_args()
    os.makedirs(RUNS, exist_ok=True)

    if not args.aggregate_only:
        t0 = time.time()
        print("Loading ...")
        df, feats, info = C.load_2017()
        conf, _ = C.conflict_stats(df)
        df = C.apply_dedup(df, "drop_conflicts")
        tax = C.add_taxonomies(df, min_support=500)
        df = df.sort_values("_pos").reset_index(drop=True)
        print(f"  ready: {len(df):,} rows, {len(feats)} features ({time.time()-t0:.0f}s)")

        split_cache = {}
        for group, scheme, ss, ms in configs(args.seeds):
            rid = run_id(scheme, ss, ms)
            path = os.path.join(RUNS, rid + ".json")
            if os.path.exists(path):
                print(f"skip {rid} (done)")
                continue
            t1 = time.time()
            key = (scheme, ss)
            if key not in split_cache:
                split_cache.clear()  # keep at most one split in memory
                split_cache[key] = C.make_split(df, scheme, seed=ss if ss is not None else 42)
            tr_mask, te_mask = split_cache[key]
            res = C.evaluate_hierarchy(df.loc[tr_mask], df.loc[te_mask], feats, model_seed=ms,
                                       trees=args.trees)
            res.update({"run_id": rid, "group": group, "scheme": scheme, "split_seed": ss,
                        "model_seed": ms, "train_rows": int(tr_mask.sum()), "test_rows": int(te_mask.sum()),
                        "runtime_sec": round(time.time() - t1, 1)})
            with open(path, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
            print(f"{rid}: mal-F1={res['stage1']['malicious_f1']:.4f} "
                  f"famGT={res['stage2_family']['gt_malicious']['macro_f1']:.4f} "
                  f"fineGT={res['stage2_fine']['gt_malicious']['macro_f1']:.4f} ({res['runtime_sec']}s)",
                  flush=True)
        with open(os.path.join(EXP, "data_prep.json"), "w", encoding="utf-8") as f:
            json.dump({"load": info, "conflicts_before_dedup": conf, "taxonomy": tax,
                       "rows_after_dedup": len(df)}, f, indent=2, default=str)

    sanity = sanity_check()
    aggregate(args.seeds)
    C.write_manifest(
        EXP, experiment_id="exp002_seeds", depends_on="exp001_baseline",
        description="Seed variability; split randomness and model randomness varied separately",
        scripts={"exp002_seeds.py": C.sha256(os.path.join(C.HERE, "exp002_seeds.py")),
                 "ids_common.py": C.sha256(os.path.join(C.HERE, "ids_common.py"))},
        cmd=f"python exp002_seeds.py --seeds {' '.join(map(str, args.seeds))} --trees {args.trees}",
        seeds=args.seeds, model="RandomForest(n_estimators=%d,max_depth=20,class_weight=balanced)" % args.trees,
        dedup_policy="drop_conflicts", class_mapping="fine: >=500 deduped samples else Other/Rare; family: ids_common.FAMILY",
        split_definitions={"temporal": "within raw label chronological 80/20, 1% purge gap (deterministic)",
                           "random": "stratified on raw label 80/20"},
        sanity_check=sanity)


if __name__ == "__main__":
    main()
