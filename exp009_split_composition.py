"""
exp009: describe the time composition of the exp004 'forward' split (no models are trained).

The exp004 forward split is per class: each raw label is ordered by its own timestamps and its
latest 20% is tested. There is no single global cutoff, so training flows of one class can be
later than test flows of another. This script quantifies that, and checks whether a single
global cutoff would be feasible on CICIDS2017, i.e. which classes it would leave on one side only.

Reuses exp004's loader, timestamp attachment and split function unchanged, on the same
drop_conflicts population.

Usage: python exp009_split_composition.py
"""
import json
import os
import time

import numpy as np
import pandas as pd

import ids_common as C
from exp004_leakage_vs_drift import load_meta, split_forward

EXP = os.path.join(C.HERE, "experiments", "exp009_split_composition")


def window(ts):
    return {"n": int(len(ts)), "t_min": str(ts.min()) if len(ts) else None,
            "t_max": str(ts.max()) if len(ts) else None,
            "by_day": {str(k): int(v) for k, v in ts.dt.date.value_counts().sort_index().items()}}


def main():
    os.makedirs(EXP, exist_ok=True)
    t0 = time.time()
    df, feats, info = C.load_2017()
    meta, _ = load_meta(info)
    df = C.apply_dedup(df, "drop_conflicts")
    C.add_taxonomies(df, min_support=500)
    df = df[["_pos", "label_raw", "family", "binary"]].sort_values("_pos").reset_index(drop=True)
    df["ts"] = meta.loc[df["_pos"].values, "ts"].values
    del meta
    df = df[df["ts"].notna()].reset_index(drop=True)
    print(f"rows: {len(df):,}")

    tr, te = split_forward(df)
    ts = df["ts"]
    out = {"rows": int(len(df)), "train_rows": int(tr.sum()), "test_rows": int(te.sum())}

    # 1. per-class train / test windows
    per_class = {}
    for lab, idx in df.groupby("label_raw").indices.items():
        m_tr, m_te = tr[idx], te[idx]
        per_class[lab] = {"family": df["family"].values[idx[0]],
                          "train": window(ts.iloc[idx[m_tr]]), "test": window(ts.iloc[idx[m_te]])}
    out["per_class"] = per_class

    # 2. ordering violations relative to a strict global forward split
    t_tr = np.sort(ts[tr].values.astype("int64"))
    t_te = ts[te].values.astype("int64")
    later = len(t_tr) - np.searchsorted(t_tr, t_te, side="right")  # training flows strictly later
    ben_te = te & (df["binary"].values == 0)
    t_ben_te_min = ts[ben_te].min()
    atk_tr = tr & (df["binary"].values == 1)
    atk_tr_after = atk_tr & (ts >= t_ben_te_min).values
    out["ordering"] = {
        "test_flows_with_any_later_training_flow_frac": float((later > 0).mean()),
        "mean_frac_of_training_flows_later_than_test_flow": float((later / len(t_tr)).mean()),
        "latest_training_flow": str(ts[tr].max()), "earliest_test_flow": str(ts[te].min()),
        "benign_test_window": window(ts[ben_te]),
        "attack_training_flows_at_or_after_benign_test_start": int(atk_tr_after.sum()),
        "attack_training_flows_total": int(atk_tr.sum()),
        "attack_training_flows_after_benign_test_start_by_class":
            df.loc[atk_tr_after, "label_raw"].value_counts().to_dict(),
    }

    # 3. single global cutoff feasibility (no purge): which classes keep both sides?
    glob_cut = {}
    cuts = {f"q{int(q * 100)}": ts.quantile(q) for q in (0.5, 0.6, 0.7, 0.8, 0.9)}
    cuts["friday_start"] = pd.Timestamp("2017-07-07 00:00:00")
    labels = sorted(df["label_raw"].unique())
    attacks = [l for l in labels if l != "BENIGN"]
    for name, cut in cuts.items():
        before = (ts < cut).values
        rows = {}
        for lab in labels:
            msk = (df["label_raw"] == lab).values
            rows[lab] = {"train": int((msk & before).sum()), "test": int((msk & ~before).sum())}
        glob_cut[name] = {
            "cutoff": str(cut), "train_frac": float(before.mean()), "per_class": rows,
            "attack_classes_both_sides": [l for l in attacks if rows[l]["train"] and rows[l]["test"]],
            "attack_classes_train_only": [l for l in attacks if rows[l]["train"] and not rows[l]["test"]],
            "attack_classes_test_only": [l for l in attacks if rows[l]["test"] and not rows[l]["train"]],
        }
    out["global_cutoff"] = glob_cut

    json.dump(out, open(os.path.join(EXP, "summary.json"), "w", encoding="utf-8"), indent=2, default=str)
    o = out["ordering"]
    print(json.dumps({k: v for k, v in o.items() if k != "benign_test_window"}, indent=1, default=str))
    print("benign test window:", o["benign_test_window"])
    for name, g in glob_cut.items():
        print(f"{name} {g['cutoff']} train_frac={g['train_frac']:.3f} both={len(g['attack_classes_both_sides'])} "
              f"train_only={len(g['attack_classes_train_only'])} test_only={len(g['attack_classes_test_only'])} "
              f"both: {g['attack_classes_both_sides']}")
    code = C.snapshot_code(EXP, ["exp009_split_composition.py", "exp004_leakage_vs_drift.py", "ids_common.py"])
    C.write_manifest(EXP, experiment_id="exp009_split_composition", depends_on=["exp004_leakage_vs_drift"],
                     description="Time composition of the per-class forward split; global-cutoff feasibility "
                                 "(descriptive, no models)",
                     scripts=code, cmd="python exp009_split_composition.py", dedup_policy="drop_conflicts",
                     runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
