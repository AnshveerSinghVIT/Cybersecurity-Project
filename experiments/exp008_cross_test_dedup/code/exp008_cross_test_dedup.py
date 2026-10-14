"""
exp008: is the exp003 cross-dataset collapse an artifact of deduplicating the 2018 TEST set?

exp003 removed exact duplicates from 2018 (DoS Hulk 461,912 -> 145,199 rows; SlowHTTPTest
139,890 -> 55). Recall over unique vectors can differ from recall over all rows if the model
treats the heavily repeated vectors differently. Prior work (Cantone et al. 2024) does not
deduplicate and reports 2017->2018 F1 0.26-0.39, far above exp003's ~0.0006.

Training is identical to exp003 (2017 train partition, shared families, drop_conflicts).
Only the 2018 test population changes:
  drop_conflicts   = exp003 (asserted identical)
  keep_first       exact duplicates removed, conflicting groups kept (first occurrence)
  none             every 2018 row (no deduplication at all)
RF seeds 42, 1, 2.

Usage: python exp008_cross_test_dedup.py
"""
import json
import os
import time

import ids_common as C
import exp003_cross_family as E3

EXP = os.path.join(C.HERE, "experiments", "exp008_cross_test_dedup")
EXP003 = os.path.join(C.HERE, "experiments", "exp003_cross_family", "data_prep.json")
SEEDS = [42, 1, 2]
POLICIES = ["drop_conflicts", "keep_first", "none"]


def main():
    os.makedirs(os.path.join(EXP, "runs"), exist_ok=True)
    t0 = time.time()
    ref = json.load(open(EXP003, encoding="utf-8"))
    d17, feats17, _ = C.load_2017()
    d17 = C.apply_dedup(d17, "drop_conflicts")
    C.add_taxonomies(d17, min_support=500)
    d17 = d17.sort_values("_pos").reset_index(drop=True)
    tr, _ = C.make_split(d17, "temporal")
    d18_all, aligned, _ = C.load_2018(feats17)
    train = d17.loc[tr & d17["family"].isin(E3.SHARED).values, aligned + ["binary", "family", "label_raw"]]
    del d17
    assert train["label_raw"].value_counts().to_dict() == ref["train_support"]

    tests, supports = {}, {}
    for pol in POLICIES:
        d = C.apply_dedup(d18_all, pol)
        d["family"] = d["label_raw"].map(C.FAMILY)
        d["binary"] = (d["label_raw"] != "BENIGN").astype(int)
        tests[pol] = d[aligned + ["binary", "family", "label_raw"]].reset_index(drop=True)
        supports[pol] = tests[pol]["label_raw"].value_counts().to_dict()
        del d
    del d18_all
    assert supports["drop_conflicts"] == ref["cross_test_support"]
    print("supports:", json.dumps(supports, indent=1), flush=True)

    mal = train[train["binary"] == 1]
    runs = []
    for seed in SEEDS:
        t1 = time.time()
        s1 = C.rf(seed).fit(train[aligned].values, train["binary"].values)
        s2 = C.rf(seed).fit(mal[aligned].values, mal["family"].values)
        r = {"seed": seed, "results": {p: E3.score(tests[p], aligned, s1, s2) for p in POLICIES}}
        del s1, s2
        r["runtime_sec"] = round(time.time() - t1, 1)
        json.dump(r, open(os.path.join(EXP, "runs", f"seed{seed}.json"), "w", encoding="utf-8"), indent=2)
        runs.append(r)
        print(f"seed {seed}: " + " | ".join(
            f"{p}: e2e={r['results'][p]['end_to_end']['macro_f1']:.4f} "
            f"malF1={r['results'][p]['stage1']['malicious_f1']:.4f} "
            f"DoS={r['results'][p]['per_family']['DoS/DDoS']['e2e_recall']:.4f}" for p in POLICIES), flush=True)

    import numpy as np
    lines = ["| 2018 test policy | n test | Malicious F1 | E2E macro-F1 | DoS recall | Web recall | Benign FPR | per raw label recall (seed 42) |",
             "|---|---|---|---|---|---|---|---|"]
    for p in POLICIES:
        g = lambda f: f"{np.mean([f(r['results'][p]) for r in runs]):.4f} ± {np.std([f(r['results'][p]) for r in runs], ddof=1):.4f}"
        r42 = runs[0]["results"][p]["per_raw_label"]
        lines.append(f"| {p} | {runs[0]['results'][p]['n_test']:,} | {g(lambda s: s['stage1']['malicious_f1'])} | "
                     f"{g(lambda s: s['end_to_end']['macro_f1'])} | {g(lambda s: s['per_family']['DoS/DDoS']['e2e_recall'])} | "
                     f"{g(lambda s: s['per_family']['Web Attack']['e2e_recall'])} | "
                     f"{g(lambda s: 100 * s['stage1']['benign_fpr'])}% | "
                     + "; ".join(f"{k} {v['e2e_recall']:.3f} (n={v['n']:,})" for k, v in r42.items() if k != "BENIGN") + " |")
    open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)
    json.dump({"supports": supports}, open(os.path.join(EXP, "data_prep.json"), "w"), indent=2)
    code = C.snapshot_code(EXP, ["exp008_cross_test_dedup.py", "exp003_cross_family.py", "ids_common.py"])
    C.write_manifest(EXP, experiment_id="exp008_cross_test_dedup", depends_on=["exp003_cross_family"],
                     description="exp003 training unchanged; 2018 test population with/without deduplication",
                     scripts=code, cmd="python exp008_cross_test_dedup.py", seeds=SEEDS, policies=POLICIES,
                     runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
