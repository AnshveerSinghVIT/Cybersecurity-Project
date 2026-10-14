"""
exp004: separate correlated-flow leakage from temporal drift.

The MachineLearningCSV files (used everywhere else) have no timestamps / Flow IDs. The official
GeneratedLabelledFlows release has them. This script:
  1. attaches Timestamp + Flow ID to the MachineLearningCSV rows by position, but ONLY after
     verifying row-by-row that both releases hold the same flows in the same order (Flow Duration,
     Total Fwd Packets and label must match); aborts otherwise
  2. checks whether the row-order "temporal" split used in exp001/002 is a valid time proxy
  3. compares, on the identical deduplicated population (drop_conflicts, as exp002):
       A  random      - stratified random rows (exp002 'random')
       B  flowid      - random, grouped by Flow ID (sub-flows of one connection stay together)
       C  block{W}    - random, grouped by W-minute time blocks within label (W = 1, 5, 15)
       D  forward     - within label, earliest 80% by TRUE timestamp train, latest 20% test,
                        1% purge gap (same rule as the row-order split)
       E  roworder    - exp001/002 row-order split (reference; compared with D)
     A->C estimates adjacency/session leakage with no time extrapolation; C->D estimates drift.

Data: cicids2017_labelled/*.pcap_ISCX.csv.zip (Kaggle mirror pshikk/cicids2017-untampered,
whose MachineLearningCSV files are byte-identical in size to ours).

Usage: python exp004_leakage_vs_drift.py [--seeds 42] [--blocks 1 5 15]
"""
import argparse
import glob
import json
import os
import time
import zipfile

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

import ids_common as C

EXP = os.path.join(C.HERE, "experiments", "exp004_leakage_vs_drift")
RUNS = os.path.join(EXP, "runs")
LAB_DIR = os.path.join(C.HERE, "cicids2017_labelled")
META_COLS = ["Flow ID", "Timestamp", "Flow Duration", "Total Fwd Packets", "Label"]


def load_meta(ml_info):
    """Read Flow ID / Timestamp from the labelled release in the same file order as load_2017,
    verify row alignment against the ML release, return a frame indexed by raw _pos."""
    ml_paths = sorted(glob.glob(os.path.join(C.HERE, "cicids2017", "*.csv")), key=C.day_rank)
    frames, checks, offset = [], {}, 0
    for p in ml_paths:
        name = os.path.basename(p)
        zp = os.path.join(LAB_DIR, name + ".zip")
        assert os.path.exists(zp), f"missing {zp}"
        with zipfile.ZipFile(zp) as z:
            with z.open(z.namelist()[0]) as f:
                lab = pd.read_csv(f, encoding="latin-1", low_memory=False,
                                  usecols=lambda c: c.strip() in META_COLS)
        lab.columns = lab.columns.str.strip()
        n_raw = len(lab)
        lab = lab.dropna(how="all").reset_index(drop=True)  # some labelled files have blank tail rows
        ml = pd.read_csv(p, usecols=lambda c: c.strip() in ("Flow Duration", "Total Fwd Packets", "Label"),
                         low_memory=False)
        ml.columns = ml.columns.str.strip()
        same_len = len(ml) == len(lab)
        match = None
        if same_len:
            match = float(((ml["Flow Duration"].values == pd.to_numeric(lab["Flow Duration"], errors="coerce").values)
                           & (ml["Total Fwd Packets"].values == pd.to_numeric(lab["Total Fwd Packets"], errors="coerce").values)
                           & (ml["Label"].map(C.canon_label).values == lab["Label"].map(C.canon_label).values)).mean())
        checks[name] = {"ml_rows": len(ml), "labelled_rows_raw": n_raw, "labelled_rows_nonblank": len(lab),
                        "same_length": same_len, "row_match_rate": match}
        print(f"  {name}: ml={len(ml):,} labelled={len(lab):,} (raw {n_raw:,}) match={match}")
        if not same_len or match < 0.999:
            raise SystemExit(f"row alignment failed for {name}: {checks[name]} - cannot attach timestamps")
        ts = pd.to_datetime(lab["Timestamp"].str.strip(), format="mixed", dayfirst=True, errors="coerce")
        # CICIDS2017 afternoon timestamps are 12-hour without AM/PM (e.g. '1:30' = 13:30).
        # Capture ran ~08:00-17:00, so any hour < 8 is an afternoon hour.
        pm = ts.dt.hour < 8
        ts = ts.where(~pm, ts + pd.Timedelta(hours=12))
        checks[name].update({"timestamps_unparsed": int(ts.isna().sum()), "pm_corrected": int(pm.sum()),
                             "time_min": str(ts.min()), "time_max": str(ts.max())})
        frames.append(pd.DataFrame({
            "_pos": np.arange(offset, offset + len(lab)),
            "ts": ts.values,
            "flow_id": pd.util.hash_array(lab["Flow ID"].astype(str).values),
        }))
        offset += len(lab)
        del lab, ml
    assert offset == ml_info["rows_raw"], (offset, ml_info["rows_raw"])
    return pd.concat(frames, ignore_index=True).set_index("_pos"), checks


def row_order_validity(df):
    """Is capture-file row order a valid proxy for time? Per source file."""
    out = {}
    for src, g in df.groupby("_src"):
        t = g["ts"].astype("int64").values / 1e9
        pos = g["_pos"].values
        rho = float(spearmanr(pos, t).statistic)
        runmax = np.maximum.accumulate(t)
        out[src] = {"spearman_pos_vs_time": rho,
                    "frac_rows_more_than_60s_behind_running_max": float(((runmax - t) > 60).mean()),
                    "frac_rows_more_than_600s_behind_running_max": float(((runmax - t) > 600).mean())}
    return out


def split_random_groups(df, key, seed, test_frac=0.2):
    """Within each raw label: shuffle groups, assign whole groups to test until >= test_frac of rows."""
    rng = np.random.default_rng(seed)
    is_test = np.zeros(len(df), dtype=bool)
    for _, idx in df.groupby("label_raw").indices.items():
        grp = df[key].values[idx]
        uniq, inv, counts = np.unique(grp, return_inverse=True, return_counts=True)
        if len(uniq) == 1:
            continue  # a single group can't be split: keep the class in train (absent from test)
        order = rng.permutation(len(uniq))
        cum = np.cumsum(counts[order])
        n_test_groups = int(np.searchsorted(cum, test_frac * len(idx)) + 1)
        test_groups = np.zeros(len(uniq), dtype=bool)
        test_groups[order[:min(n_test_groups, len(uniq) - 1)]] = True  # always leave >=1 group in train
        is_test[idx] = test_groups[inv]
    return ~is_test, is_test


def split_forward(df, test_frac=0.2, purge_frac=0.01):
    """Within label, sort by true timestamp (ties by row order); latest test_frac tests, purge gap."""
    is_test = np.zeros(len(df), dtype=bool)
    is_gap = np.zeros(len(df), dtype=bool)
    for _, idx in df.groupby("label_raw").indices.items():
        idx = idx[np.lexsort((df["_pos"].values[idx], df["ts"].values[idx]))]
        m = len(idx)
        cut = int(m * (1 - test_frac))
        gap = max(1, int(m * purge_frac)) if m >= 100 else 0
        is_gap[idx[cut - gap:cut]] = True
        is_test[idx[cut:]] = True
    return ~is_test & ~is_gap, is_test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--blocks", type=int, nargs="+", default=[1, 5, 15])
    ap.add_argument("--trees", type=int, default=100)
    args = ap.parse_args()
    os.makedirs(RUNS, exist_ok=True)
    t0 = time.time()

    print("Loading MachineLearningCSV ...")
    df, feats, info = C.load_2017()
    print("Loading + verifying GeneratedLabelledFlows metadata ...")
    meta, align = load_meta(info)
    df = C.apply_dedup(df, "drop_conflicts")
    C.add_taxonomies(df, min_support=500)
    df = df.sort_values("_pos").reset_index(drop=True)
    df["ts"] = meta.loc[df["_pos"].values, "ts"].values
    df["flow_id"] = meta.loc[df["_pos"].values, "flow_id"].values
    del meta
    df = df.drop(columns=["Label"])  # memory: unused text column (_src kept for validity check)
    keep_cols = feats + ["label_raw", "fine", "family", "binary"]
    n_bad_ts = int(df["ts"].isna().sum())
    if n_bad_ts:
        print(f"  dropping {n_bad_ts} rows with unparseable timestamps")
        df = df[df["ts"].notna()].reset_index(drop=True)
    tsec = df["ts"].astype("int64") // 10**9
    for w in args.blocks:
        df[f"block{w}"] = tsec // (60 * w)

    validity = row_order_validity(df)
    print(json.dumps(validity, indent=1))

    splits = {"roworder": C.make_split(df, "temporal"), "forward": split_forward(df)}
    tr_e, te_e = splits["roworder"]
    tr_d, te_d = splits["forward"]
    proxy = {"test_jaccard_roworder_vs_forward": float((te_e & te_d).sum() / (te_e | te_d).sum()),
             "train_jaccard_roworder_vs_forward": float((tr_e & tr_d).sum() / (tr_e | tr_d).sum())}
    print("row-order vs forward-time split:", proxy)

    results = {}
    for seed in args.seeds:
        cfgs = dict(splits)
        cfgs["random"] = C.make_split(df, "random", seed=seed)
        cfgs["flowid"] = split_random_groups(df, "flow_id", seed)
        for w in args.blocks:
            cfgs[f"block{w}"] = split_random_groups(df, f"block{w}", seed)
        for name, (tr, te) in cfgs.items():
            rid = f"{name}_seed{seed}"
            path = os.path.join(RUNS, rid + ".json")
            if os.path.exists(path):
                results[rid] = json.load(open(path, encoding="utf-8"))
                print(f"skip {rid}")
                continue
            t1 = time.time()
            train, test = df.loc[tr, keep_cols], df.loc[te, keep_cols]
            models = C.fit_hierarchy(train, feats, seed, args.trees)
            r = {"run_id": rid, "split": name, "seed": seed,
                 "seed_meaning": "split seed and RF seed (deterministic splits: RF seed only)",
                 "train_rows": int(tr.sum()), "test_rows": int(te.sum()),
                 "test_support": test["label_raw"].value_counts().to_dict(),
                 **C.score_hierarchy(models, test, feats)}
            del models, train, test
            r["runtime_sec"] = round(time.time() - t1, 1)
            json.dump(r, open(path, "w", encoding="utf-8"), indent=2)
            results[rid] = r
            print(f"{rid}: mal-F1={r['stage1']['malicious_f1']:.4f} FPR={r['stage1']['benign_fpr']:.4f} "
                  f"famGT={r['stage2_family']['gt_malicious']['macro_f1']:.4f} "
                  f"fineGT={r['stage2_fine']['gt_malicious']['macro_f1']:.4f} ({r['runtime_sec']}s)", flush=True)

    json.dump({"alignment_checks": align, "row_order_validity": validity, "proxy_overlap": proxy,
               "rows": len(df), "dropped_unparseable_ts": n_bad_ts},
              open(os.path.join(EXP, "data_prep.json"), "w", encoding="utf-8"), indent=2, default=str)

    order = ["random", "flowid"] + [f"block{w}" for w in args.blocks] + ["forward", "roworder"]
    lines = ["| Split | Stage1 mal-F1 | Benign FPR | Family GT | Family E2E | Fine GT | Fine E2E | "
             "PortScan fam-GT F1 | slowloris fine-GT F1 |", "|---|---|---|---|---|---|---|---|---|"]
    for name in order:
        rs = [r for r in results.values() if r["split"] == name]
        if not rs:
            continue

        def ms(get):
            v = np.array([get(r) for r in rs], dtype=float)
            return f"{v.mean():.4f}" + (f" ± {v.std(ddof=1):.4f}" if len(v) > 1 else "")
        lines.append(
            f"| {name} | {ms(lambda r: r['stage1']['malicious_f1'])} | "
            f"{ms(lambda r: 100 * r['stage1']['benign_fpr'])}% | "
            f"{ms(lambda r: r['stage2_family']['gt_malicious']['macro_f1'])} | "
            f"{ms(lambda r: r['stage2_family']['end_to_end']['macro_f1'])} | "
            f"{ms(lambda r: r['stage2_fine']['gt_malicious']['macro_f1'])} | "
            f"{ms(lambda r: r['stage2_fine']['end_to_end']['macro_f1'])} | "
            f"{ms(lambda r: r['stage2_family']['gt_malicious']['per_class'].get('PortScan', {}).get('f1', np.nan))} | "
            f"{ms(lambda r: r['stage2_fine']['gt_malicious']['per_class'].get('DoS slowloris', {}).get('f1', np.nan))} |")
    table = "\n".join(lines)
    open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8").write(table + "\n")
    print(table)

    code = C.snapshot_code(EXP, ["exp004_leakage_vs_drift.py", "ids_common.py"])
    C.write_manifest(
        EXP, experiment_id="exp004_leakage_vs_drift", depends_on=["exp002_seeds"],
        description="Random vs Flow-ID-grouped vs time-block-grouped vs forward-time vs row-order splits",
        scripts=code, cmd=f"python exp004_leakage_vs_drift.py --seeds {' '.join(map(str, args.seeds))} "
                          f"--blocks {' '.join(map(str, args.blocks))} --trees {args.trees}",
        seeds=args.seeds, dedup_policy="drop_conflicts", class_mapping="as exp002",
        metadata_source="Kaggle pshikk/cicids2017-untampered GeneratedLabelledFlows/TrafficLabelling",
        timestamp_fix="hour<8 -> +12h (12-hour clock without AM/PM in afternoon files)",
        runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
