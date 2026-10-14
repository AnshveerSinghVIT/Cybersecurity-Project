"""
Multi-class attack attribution baseline on CICIDS2017 (in-dataset, leakage-aware).

Order of work (see conversation notes):
  1. label distribution + count label CONFLICTS among duplicate feature rows (before any dedup)
  2. fine-grained and family-level label mappings built from the raw labels
  3. leakage-resistant split: within-class temporal split (files are chronological), duplicates
     resolved BEFORE splitting, no scaler (tree models) so nothing is fitted on test data
  4. report macro-F1, per-class precision/recall/support, confusion matrices
     - Stage 1 (binary), Stage 2 on ground-truth malicious, end-to-end through Stage 1

Usage:  python multiclass_baseline.py [--split temporal|random] [--trees 100] [--min-support 500]
Outputs: results/multiclass_baseline_<split>.json, results/*_<split>.png
"""
import argparse
import glob
import json
import os
import re
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix, f1_score,
                             precision_recall_fscore_support)

SEED = 42
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]

# Same exclusions as the notebook (network-specific artifacts).
DROP_COLS = ['Flow ID', 'Source IP', 'Src IP', 'Destination IP', 'Dst IP',
             'Source Port', 'Src Port', 'Destination Port', 'Dst Port',
             'Timestamp', 'Protocol', 'Flow Duration', 'Label']


def day_rank(path):
    name = os.path.basename(path).lower()
    for i, d in enumerate(DAY_ORDER):
        if name.startswith(d):
            # Friday has three files; keep Morning < Afternoon-PortScan < Afternoon-DDos stable by name
            return (i, name)
    return (99, name)


def canon_label(s):
    """Normalise raw 2017 labels (the 'Web Attack <garbled dash> X' labels contain a bad byte)."""
    t = re.sub(r"[^\x20-\x7E]", "-", str(s)).strip()
    low = t.lower()
    if low.startswith("web attack"):
        if "brute" in low:
            return "Web Attack - Brute Force"
        if "xss" in low:
            return "Web Attack - XSS"
        if "sql" in low:
            return "Web Attack - Sql Injection"
    return t


FAMILY = {
    "BENIGN": "Benign",
    "DoS Hulk": "DoS/DDoS", "DoS GoldenEye": "DoS/DDoS", "DoS slowloris": "DoS/DDoS",
    "DoS Slowhttptest": "DoS/DDoS", "DDoS": "DoS/DDoS",
    "PortScan": "PortScan",
    "FTP-Patator": "Brute Force", "SSH-Patator": "Brute Force",
    "Web Attack - Brute Force": "Web Attack", "Web Attack - XSS": "Web Attack",
    "Web Attack - Sql Injection": "Web Attack",
    "Bot": "Bot",
    "Infiltration": "Other/Rare", "Heartbleed": "Other/Rare",
}


def load_2017():
    paths = sorted(glob.glob(os.path.join(HERE, "cicids2017", "**", "*.csv"), recursive=True),
                   key=day_rank)
    assert paths, "no CICIDS2017 CSVs found"
    frames = []
    for p in paths:
        df = pd.read_csv(p, low_memory=False)
        df.columns = df.columns.str.strip()
        df["_src"] = os.path.basename(p)
        frames.append(df)
        print(f"  loaded {os.path.basename(p)}: {len(df):,}")
    df = pd.concat(frames, ignore_index=True)
    df["_pos"] = np.arange(len(df))  # chronological position proxy (files are in capture order)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trees", type=int, default=100)
    ap.add_argument("--min-support", type=int, default=500,
                    help="min deduplicated samples for a raw label to stay its own fine-grained class")
    ap.add_argument("--split", choices=["temporal", "random"], default="temporal",
                    help="temporal = within-label chronological 80/20 + purge gap (default); "
                         "random = stratified 80/20 on raw label (control, same data otherwise)")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    report = {"args": vars(args)}
    t0 = time.time()

    # ---------------------------------------------------------------- load + clean
    print("Loading CICIDS2017 ...")
    df = load_2017()
    feats = [c for c in df.columns
             if c not in DROP_COLS and not c.startswith("_") and df[c].dtype != "object"]
    report["n_features"] = len(feats)
    df["label_raw"] = df["Label"].map(canon_label)
    unknown = set(df["label_raw"].unique()) - set(FAMILY)
    assert not unknown, f"unmapped labels: {unknown}"

    df[feats] = df[feats].replace([np.inf, -np.inf], np.nan)
    n0 = len(df)
    df = df.dropna(subset=feats).reset_index(drop=True)
    report["rows_raw"] = n0
    report["rows_after_nan_inf_drop"] = len(df)
    df[feats] = df[feats].astype("float32")
    print(f"  {n0:,} -> {len(df):,} rows after NaN/Inf drop")

    # ---------------------------------------------------------------- 1. conflicts BEFORE dedup
    print("Counting duplicate / conflicting feature rows ...")
    df["_h"] = pd.util.hash_pandas_object(df[feats], index=False).values
    g = df.groupby("_h")["label_raw"].agg(["size", "nunique"])
    n_dup_groups = int((g["size"] > 1).sum())
    conflict_hashes = g.index[g["nunique"] > 1]
    conflict_rows = df["_h"].isin(conflict_hashes)
    report["duplicates"] = {
        "unique_feature_rows": int(len(g)),
        "rows_removed_if_keep_first": int(len(df) - len(g)),
        "duplicate_rate": float((len(df) - len(g)) / len(df)),
        "groups_with_duplicates": n_dup_groups,
        "conflicting_groups": int(len(conflict_hashes)),
        "rows_in_conflicting_groups": int(conflict_rows.sum()),
        "conflict_rows_by_raw_label": df.loc[conflict_rows, "label_raw"].value_counts().to_dict(),
    }
    # which label pairs conflict (benign-vs-attack is the dangerous one)
    pair_counts = (df.loc[conflict_rows].groupby("_h")["label_raw"]
                   .agg(lambda s: " | ".join(sorted(set(s)))).value_counts().head(15))
    report["duplicates"]["top_conflict_label_sets"] = pair_counts.to_dict()
    print(json.dumps(report["duplicates"], indent=2))

    # Policy: drop every conflicting group entirely (we can't know the true label), keep the first
    # of each consistent duplicate group. Counts above let the reader judge the effect.
    df = df.loc[~conflict_rows].drop_duplicates(subset="_h", keep="first").reset_index(drop=True)
    report["rows_after_dedup_and_conflict_drop"] = len(df)

    # ---------------------------------------------------------------- 2. taxonomies
    support = df["label_raw"].value_counts()
    report["label_support_after_dedup"] = support.to_dict()
    keep_fine = [l for l, n in support.items() if n >= args.min_support]
    df["fine"] = np.where(df["label_raw"].isin(keep_fine), df["label_raw"], "Other/Rare")
    df.loc[df["label_raw"] == "BENIGN", "fine"] = "Benign"
    df["family"] = df["label_raw"].map(FAMILY)
    df["binary"] = (df["label_raw"] != "BENIGN").astype(int)
    report["fine_classes"] = df["fine"].value_counts().to_dict()
    report["family_classes"] = df["family"].value_counts().to_dict()
    report["merged_into_other_rare_fine"] = sorted(
        set(df.loc[df["fine"] == "Other/Rare", "label_raw"]))
    print("Fine classes:", report["fine_classes"])
    print("Family classes:", report["family_classes"])

    # ---------------------------------------------------------------- 3. temporal split per raw label
    # Within each raw label, the earliest 80% (chronologically) trains, the latest 20% tests.
    # A purge gap of 1% between them removes flows adjacent in time (CICFlowMeter flows from one
    # session are highly correlated). Done per raw label so every class appears on both sides.
    df = df.sort_values("_pos").reset_index(drop=True)
    is_test = np.zeros(len(df), dtype=bool)
    is_gap = np.zeros(len(df), dtype=bool)
    if args.split == "temporal":
        for lab, idx in df.groupby("label_raw").indices.items():
            n = len(idx)
            cut = int(n * 0.8)
            gap = max(1, int(n * 0.01)) if n >= 100 else 0
            is_gap[idx[cut - gap:cut]] = True
            is_test[idx[cut:]] = True
        scheme = "within-label chronological 80/20 with 1% purge gap"
    else:
        from sklearn.model_selection import train_test_split
        _, te_idx = train_test_split(np.arange(len(df)), test_size=0.2,
                                     stratify=df["label_raw"], random_state=SEED)
        is_test[te_idx] = True
        scheme = "stratified random 80/20 on raw label (control)"
    train = df.loc[~is_test & ~is_gap]
    test = df.loc[is_test]
    report["split"] = {"scheme": scheme,
                       "train_rows": len(train), "test_rows": len(test),
                       "purged_rows": int(is_gap.sum())}
    print(f"Split: train={len(train):,} test={len(test):,} purged={int(is_gap.sum()):,}")

    Xtr, Xte = train[feats].values, test[feats].values

    def rf():
        return RandomForestClassifier(n_estimators=args.trees, max_depth=20, n_jobs=-1,
                                      class_weight="balanced", random_state=SEED)

    def per_class(y_true, y_pred, labels):
        p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
        return {l: {"precision": round(float(a), 4), "recall": round(float(b), 4),
                    "f1": round(float(c), 4), "support": int(d)}
                for l, a, b, c, d in zip(labels, p, r, f, s)}

    def plot_cm(y_true, y_pred, labels, title, fname):
        cm = confusion_matrix(y_true, y_pred, labels=labels, normalize="true")
        fig, ax = plt.subplots(figsize=(0.9 * len(labels) + 3, 0.8 * len(labels) + 2.5))
        im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticklabels(labels)
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center",
                        color="white" if cm[i, j] > 0.5 else "black", fontsize=8)
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True (row-normalised)")
        ax.set_title(title)
        fig.colorbar(im, ax=ax, fraction=0.046)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, fname), dpi=150)
        plt.close(fig)

    # ---------------------------------------------------------------- Stage 1: binary
    print("Training Stage 1 (binary) ...")
    s1 = rf().fit(Xtr, train["binary"].values)
    s1_pred = s1.predict(Xte)
    report["stage1_binary"] = {
        "macro_f1": float(f1_score(test["binary"], s1_pred, average="macro")),
        "malicious_f1": float(f1_score(test["binary"], s1_pred)),
        "per_class": per_class(test["binary"].values, s1_pred, [0, 1]),
    }
    print(" stage1 macro-F1 %.4f" % report["stage1_binary"]["macro_f1"])
    # recall of the detector per raw attack label: which attacks does Stage 1 miss?
    tmp = test.assign(_pred=s1_pred)
    report["stage1_recall_by_raw_label"] = {
        l: round(float((g_["_pred"] == (0 if l == "BENIGN" else 1)).mean()), 4)
        for l, g_ in tmp.groupby("label_raw")}

    # ---------------------------------------------------------------- Stage 2: attack attribution
    mal_tr = train[train["binary"] == 1]
    mal_te = test[test["binary"] == 1]
    flagged_te = test[s1_pred == 1]  # flows Stage 1 actually flags (includes false positives)
    for level in ("family", "fine"):
        print(f"Training Stage 2 [{level}] ...")
        m = rf().fit(mal_tr[feats].values, mal_tr[level].values)
        labels = sorted(mal_tr[level].unique())

        # (a) isolates the attribution model: ground-truth malicious flows only
        pred_gt = m.predict(mal_te[feats].values)
        # (b) realistic: flows Stage 1 flagged; benign false positives have no true attack type,
        #     so they are scored as an extra 'Benign' true label (can only be wrong)
        pred_fl = m.predict(flagged_te[feats].values)
        true_fl = flagged_te[level].values  # contains 'Benign' for false positives
        # (c) end-to-end over the whole test set: Stage-1 miss => predicted 'Benign'
        pred_all = np.where(s1_pred == 1, m.predict(Xte), "Benign")
        true_all = test[level].values
        e2e_labels = ["Benign"] + labels

        report[f"stage2_{level}"] = {
            "classes": labels,
            "gt_malicious": {
                "macro_f1": float(f1_score(mal_te[level], pred_gt, labels=labels, average="macro",
                                           zero_division=0)),
                "per_class": per_class(mal_te[level].values, pred_gt, labels)},
            "flagged_by_stage1": {
                "macro_f1": float(f1_score(true_fl, pred_fl, labels=e2e_labels, average="macro",
                                           zero_division=0)),
                "per_class": per_class(true_fl, pred_fl, e2e_labels),
                "n_false_positive_benign": int((true_fl == "Benign").sum())},
            "end_to_end": {
                "macro_f1": float(f1_score(true_all, pred_all, labels=e2e_labels, average="macro",
                                           zero_division=0)),
                "per_class": per_class(true_all, pred_all, e2e_labels)},
        }
        plot_cm(mal_te[level].values, pred_gt, labels,
                f"Stage 2 ({level}) - ground-truth malicious, {args.split} split",
                f"cm_stage2_{level}_gt_{args.split}.png")
        plot_cm(true_all, pred_all, e2e_labels, f"End-to-end ({level}) - {args.split} split",
                f"cm_end_to_end_{level}_{args.split}.png")
        print(f" {level}: stage2-GT macro-F1={report[f'stage2_{level}']['gt_malicious']['macro_f1']:.4f}"
              f"  end-to-end macro-F1={report[f'stage2_{level}']['end_to_end']['macro_f1']:.4f}")

    report["runtime_sec"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, f"multiclass_baseline_{args.split}.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Done in {report['runtime_sec']}s -> {OUT}")


if __name__ == "__main__":
    main()
