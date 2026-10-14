"""
Shared pipeline for the leakage-aware evaluation experiments (exp002+).

Logic is identical to experiments/exp001_baseline/multiclass_baseline.py, factored into functions so
every experiment loads, deduplicates, maps labels, splits and scores in exactly the same way.
Any intentional behaviour change must be recorded in the experiment's MANIFEST.json.
"""
import glob
import hashlib
import json
import os
import platform
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

HERE = os.path.dirname(os.path.abspath(__file__))
DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday"]

DROP_COLS = ['Flow ID', 'Source IP', 'Src IP', 'Destination IP', 'Dst IP',
             'Source Port', 'Src Port', 'Destination Port', 'Dst Port',
             'Timestamp', 'Protocol', 'Flow Duration', 'Label']

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

DEDUP_POLICIES = ("drop_conflicts", "keep_first", "majority", "none")


def day_rank(path):
    name = os.path.basename(path).lower()
    for i, d in enumerate(DAY_ORDER):
        if name.startswith(d):
            return (i, name)
    return (99, name)


def canon_label(s):
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


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def env_info():
    import sklearn
    return {"python": platform.python_version(), "sklearn": sklearn.__version__,
            "pandas": pd.__version__, "numpy": np.__version__}


def load_2017(verbose=True):
    """Load + clean CICIDS2017. Returns (df, feats, info). df keeps _pos (chronological proxy),
    _src (file), _h (feature-row hash), label_raw."""
    paths = sorted(glob.glob(os.path.join(HERE, "cicids2017", "**", "*.csv"), recursive=True),
                   key=day_rank)
    assert paths, "no CICIDS2017 CSVs found"
    # Memory-lean but value-identical to the original (concat -> inf->NaN -> dropna -> float32):
    # the same elementwise operations are applied per file BEFORE concatenating, so only one
    # file is ever held in float64 (peak ~3 GB instead of ~8.6 GB). Row order and _pos (assigned
    # on raw rows, before the drop) are unchanged. int64->float32 is a single correctly-rounded
    # conversion either way for |x| < 2**53, so values match bit-for-bit. Equivalence is enforced
    # by verify_loader.py, which must reproduce exp001 exactly before any queued experiment runs.
    frames, feats, offset, n0 = [], None, 0, 0
    for p in paths:
        d = pd.read_csv(p, low_memory=False)
        d.columns = d.columns.str.strip()
        f_cols = [c for c in d.columns if c not in DROP_COLS and d[c].dtype != "object"]
        if feats is None:
            feats = f_cols
        assert f_cols == feats, f"feature columns differ in {os.path.basename(p)}"
        d["_src"] = os.path.basename(p)
        d["_pos"] = np.arange(offset, offset + len(d))
        offset += len(d)
        n0 += len(d)
        d[feats] = d[feats].replace([np.inf, -np.inf], np.nan)
        d = d.dropna(subset=feats)
        d[feats] = d[feats].astype("float32")
        frames.append(d)
        if verbose:
            print(f"  loaded {os.path.basename(p)}: {len(d):,} (after NaN/Inf drop)")
    df = pd.concat(frames, ignore_index=True)
    del frames
    df["label_raw"] = df["Label"].map(canon_label)
    unknown = set(df["label_raw"].unique()) - set(FAMILY)
    assert not unknown, f"unmapped labels: {unknown}"
    df["_h"] = pd.util.hash_pandas_object(df[feats], index=False).values
    info = {"rows_raw": n0, "rows_after_nan_inf_drop": len(df), "n_features": len(feats),
            "dataset_files": {os.path.basename(p): os.path.getsize(p) for p in paths}}
    return df, feats, info


def conflict_stats(df):
    g = df.groupby("_h")["label_raw"].agg(["size", "nunique"])
    conflict_hashes = g.index[g["nunique"] > 1]
    rows = df["_h"].isin(conflict_hashes)
    sub = df.loc[rows]
    # independent events, not rows: count distinct (group, label) pairs per label
    groups_by_label = sub.groupby("label_raw")["_h"].nunique().to_dict()
    return {
        "unique_feature_rows": int(len(g)),
        "duplicate_rate_keep_first": float((len(df) - len(g)) / len(df)),
        "conflicting_groups": int(len(conflict_hashes)),
        "rows_in_conflicting_groups": int(rows.sum()),
        "conflict_rows_by_label": sub["label_raw"].value_counts().to_dict(),
        "conflict_groups_by_label": {k: int(v) for k, v in groups_by_label.items()},
        "largest_conflict_group_rows": int(g.loc[conflict_hashes, "size"].max()) if len(conflict_hashes) else 0,
    }, rows.values


def apply_dedup(df, policy):
    """Resolve duplicate feature rows. Returns a new df.
    drop_conflicts: drop every group with >1 label, keep first of consistent groups (exp001 policy)
    keep_first:     keep the chronologically first row of every group, whatever its label (notebook policy)
    majority:       keep one row per group, labelled with the group's most frequent label
    none:           no deduplication at all
    """
    assert policy in DEDUP_POLICIES, policy
    if policy == "none":
        return df.reset_index(drop=True)
    if policy == "keep_first":
        return df.drop_duplicates(subset="_h", keep="first").reset_index(drop=True)
    if policy == "drop_conflicts":
        nun = df.groupby("_h")["label_raw"].transform("nunique")
        return df.loc[nun == 1].drop_duplicates(subset="_h", keep="first").reset_index(drop=True)
    # majority: most frequent label per group; ties broken by first occurrence
    maj = (df.groupby(["_h", "label_raw"], sort=False).size().reset_index(name="n")
           .sort_values("n", ascending=False, kind="stable").drop_duplicates("_h")
           .set_index("_h")["label_raw"])
    out = df.drop_duplicates(subset="_h", keep="first").copy()
    out["label_raw"] = out["_h"].map(maj).values
    return out.reset_index(drop=True)


def add_taxonomies(df, min_support=500, keep_fine=None):
    """keep_fine: fixed list of raw labels kept as fine classes (overrides min_support) - use it when
    comparing populations (e.g. dedup policies) so the class definition doesn't move with them."""
    support = df["label_raw"].value_counts()
    if keep_fine is None:
        keep_fine = [l for l, n in support.items() if n >= min_support]
    df["fine"] = np.where(df["label_raw"].isin(keep_fine), df["label_raw"], "Other/Rare")
    df.loc[df["label_raw"] == "BENIGN", "fine"] = "Benign"
    df["family"] = df["label_raw"].map(FAMILY)
    df["binary"] = (df["label_raw"] != "BENIGN").astype(int)
    return {"label_support": support.to_dict(),
            "fine_classes": df["fine"].value_counts().to_dict(),
            "family_classes": df["family"].value_counts().to_dict(),
            "merged_into_other_rare_fine": sorted(set(df.loc[df["fine"] == "Other/Rare", "label_raw"]))}


def make_split(df, scheme, seed=42, test_frac=0.2, purge_frac=0.01):
    """Returns (is_train, is_test) boolean arrays. df must be sorted by _pos.
    temporal: within each raw label, earliest (1-test_frac) trains, latest test_frac tests, with a
              purge gap of purge_frac*n rows (n>=100) before the cut. Deterministic: seed unused.
              NOTE: the MachineLearningCSV files have no timestamps, so "earliest" means capture-file
              row order (files sorted Mon..Fri). This is a ROW-ORDER split - a time proxy, not verified
              time; call it that in any write-up until checked against GeneratedLabelledFlows.
    random:   stratified on raw label; seed controls the split."""
    n = len(df)
    is_test = np.zeros(n, dtype=bool)
    is_gap = np.zeros(n, dtype=bool)
    if scheme == "temporal":
        for _, idx in df.groupby("label_raw").indices.items():
            m = len(idx)
            cut = int(m * (1 - test_frac))
            gap = max(1, int(m * purge_frac)) if m >= 100 else 0
            is_gap[idx[cut - gap:cut]] = True
            is_test[idx[cut:]] = True
    elif scheme == "random":
        _, te = train_test_split(np.arange(n), test_size=test_frac,
                                 stratify=df["label_raw"], random_state=seed)
        is_test[te] = True
    else:
        raise ValueError(scheme)
    return ~is_test & ~is_gap, is_test


def rf(seed, trees=100):
    return RandomForestClassifier(n_estimators=trees, max_depth=20, n_jobs=-1,
                                  class_weight="balanced", random_state=seed)


def wilson_ci(k, n, z=1.96):
    """Wilson score 95% interval for a binomial proportion k/n."""
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - h), float(c + h)]


def per_class(y_true, y_pred, labels):
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {str(l): {"precision": float(a), "recall": float(b), "f1": float(c), "support": int(d),
                     "recall_ci95": wilson_ci(int(round(b * d)), int(d))}
            for l, a, b, c, d in zip(labels, p, r, f, s)}


def confusion_counts(y_true, y_pred, labels):
    from sklearn.metrics import confusion_matrix
    return {"labels": [str(l) for l in labels],
            "counts": confusion_matrix(y_true, y_pred, labels=labels).tolist()}


def evaluate_hierarchy(train, test, feats, model_seed, trees=100, keep_preds=False):
    """Stage 1 binary + Stage 2 (family, fine), scored three ways. Returns metrics dict
    (and predictions if keep_preds)."""
    Xtr, Xte = train[feats].values, test[feats].values
    out, preds = {}, {}

    s1 = rf(model_seed, trees).fit(Xtr, train["binary"].values)
    s1_pred = s1.predict(Xte)
    yb = test["binary"].values
    n_ben = int((yb == 0).sum())
    fp = int(((yb == 0) & (s1_pred == 1)).sum())
    out["stage1"] = {
        "macro_f1": float(f1_score(yb, s1_pred, average="macro")),
        "malicious_f1": float(f1_score(yb, s1_pred)),
        "malicious_precision": float(precision_recall_fscore_support(yb, s1_pred, labels=[1], zero_division=0)[0][0]),
        "malicious_recall": float(precision_recall_fscore_support(yb, s1_pred, labels=[1], zero_division=0)[1][0]),
        "benign_test_flows": n_ben,
        "benign_false_positives": fp,
        "benign_fpr": fp / n_ben if n_ben else float("nan"),
        "recall_by_raw_label": {l: float((s1_pred[idx] == (0 if l == "BENIGN" else 1)).mean())
                                for l, idx in test.groupby("label_raw").indices.items()},
    }
    preds["stage1"] = s1_pred

    mal_tr = train[train["binary"] == 1]
    mal_te = test[test["binary"] == 1]
    flagged = s1_pred == 1
    for level in ("family", "fine"):
        m = rf(model_seed, trees).fit(mal_tr[feats].values, mal_tr[level].values)
        labels = sorted(mal_tr[level].unique())
        e2e_labels = ["Benign"] + labels
        pred_gt = m.predict(mal_te[feats].values)
        pred_all_s2 = m.predict(Xte)
        pred_fl = pred_all_s2[flagged]
        true_fl = test[level].values[flagged]
        pred_e2e = np.where(flagged, pred_all_s2, "Benign")
        true_e2e = test[level].values
        out[f"stage2_{level}"] = {
            "classes": labels,
            "gt_malicious": {"macro_f1": float(f1_score(mal_te[level], pred_gt, labels=labels,
                                                        average="macro", zero_division=0)),
                             "per_class": per_class(mal_te[level].values, pred_gt, labels)},
            "flagged_by_stage1": {"macro_f1": float(f1_score(true_fl, pred_fl, labels=e2e_labels,
                                                             average="macro", zero_division=0)),
                                  "n_flagged": int(flagged.sum()),
                                  "n_false_positive_benign": int((true_fl == "Benign").sum()),
                                  "per_class": per_class(true_fl, pred_fl, e2e_labels)},
            "end_to_end": {"macro_f1": float(f1_score(true_e2e, pred_e2e, labels=e2e_labels,
                                                      average="macro", zero_division=0)),
                           "per_class": per_class(true_e2e, pred_e2e, e2e_labels)},
        }
        preds[level] = {"gt": (mal_te[level].values, pred_gt), "e2e": (true_e2e, pred_e2e)}
    return (out, preds) if keep_preds else out


def fit_hierarchy(train, feats, model_seed, trees=100, levels=("family", "fine")):
    """Fit Stage 1 (binary) and one Stage 2 model per taxonomy level. Same models as evaluate_hierarchy."""
    models = {"stage1": rf(model_seed, trees).fit(train[feats].values, train["binary"].values)}
    mal = train[train["binary"] == 1]
    for level in levels:
        models[level] = rf(model_seed, trees).fit(mal[feats].values, mal[level].values)
        models[level + "_classes"] = sorted(mal[level].unique())
    return models


def score_hierarchy(models, test, feats, levels=("family", "fine")):
    """Score fitted models on a test frame. Metric definitions identical to evaluate_hierarchy."""
    X = test[feats].values
    yb = test["binary"].values
    s1_pred = models["stage1"].predict(X)
    n_ben = int((yb == 0).sum())
    fp = int(((yb == 0) & (s1_pred == 1)).sum())
    p, r, _, _ = precision_recall_fscore_support(yb, s1_pred, labels=[1], zero_division=0)
    out = {"n_test": int(len(test)), "stage1": {
        "macro_f1": float(f1_score(yb, s1_pred, average="macro")),
        "malicious_f1": float(f1_score(yb, s1_pred)),
        "malicious_precision": float(p[0]), "malicious_recall": float(r[0]),
        "benign_test_flows": n_ben, "benign_false_positives": fp,
        "benign_fpr": fp / n_ben if n_ben else float("nan"),
        "recall_by_raw_label": {l: float((s1_pred[idx] == (0 if l == "BENIGN" else 1)).mean())
                                for l, idx in test.groupby("label_raw").indices.items()}}}
    mal = yb == 1
    flagged = s1_pred == 1
    for level in levels:
        labels = models[level + "_classes"]
        e2e_labels = ["Benign"] + labels
        p2 = models[level].predict(X)
        y = test[level].values
        e2e = np.where(flagged, p2, "Benign")
        out[f"stage2_{level}"] = {
            "classes": labels,
            "gt_malicious": {"macro_f1": float(f1_score(y[mal], p2[mal], labels=labels, average="macro",
                                                        zero_division=0)),
                             "per_class": per_class(y[mal], p2[mal], labels),
                             "confusion": confusion_counts(y[mal], p2[mal], labels)},
            "end_to_end": {"macro_f1": float(f1_score(y, e2e, labels=e2e_labels, average="macro",
                                                      zero_division=0)),
                           "per_class": per_class(y, e2e, e2e_labels),
                           "confusion": confusion_counts(y, e2e, e2e_labels)},
        }
    out["stage1"]["confusion"] = confusion_counts(yb, s1_pred, [0, 1])
    out["stage1"]["benign_fpr_ci95"] = wilson_ci(fp, n_ben)
    return out


def snapshot_code(exp_dir, files):
    """Copy the exact script revisions used into <exp_dir>/code/ so results stay traceable."""
    import shutil
    dst = os.path.join(exp_dir, "code")
    os.makedirs(dst, exist_ok=True)
    for f in files:
        shutil.copy2(os.path.join(HERE, f), os.path.join(dst, f))
    return {f: sha256(os.path.join(dst, f)) for f in files}


def write_manifest(exp_dir, **fields):
    m = dict(fields)
    m["env"] = env_info()
    m["outputs"] = {f: sha256(os.path.join(exp_dir, f)) for f in sorted(os.listdir(exp_dir))
                    if f != "MANIFEST.json" and os.path.isfile(os.path.join(exp_dir, f))}
    with open(os.path.join(exp_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, default=str)


# ---------------------------------------------------------------------------- CICIDS2018
# Same alias map as the notebook (ids_implementation.ipynb, Step 2 of the 2018 section): 2018's
# CICFlowMeter abbreviates column names. Keys/values are normalised names (see norm_col).
ALIAS_2018_TO_2017 = {
    'ack_flag_cnt': 'ack_flag_count', 'fwd_act_data_pkts': 'act_data_pkt_fwd',
    'pkt_size_avg': 'average_packet_size', 'bwd_seg_size_avg': 'avg_bwd_segment_size',
    'fwd_seg_size_avg': 'avg_fwd_segment_size', 'bwd_blk_rate_avg': 'bwd_avg_bulk_rate',
    'bwd_byts_b_avg': 'bwd_avg_bytes_bulk', 'bwd_pkts_b_avg': 'bwd_avg_packets_bulk',
    'bwd_header_len': 'bwd_header_length', 'bwd_iat_tot': 'bwd_iat_total',
    'bwd_pkt_len_max': 'bwd_packet_length_max', 'bwd_pkt_len_mean': 'bwd_packet_length_mean',
    'bwd_pkt_len_min': 'bwd_packet_length_min', 'bwd_pkt_len_std': 'bwd_packet_length_std',
    'bwd_pkts_s': 'bwd_packets_s', 'dst_port': 'destination_port',
    'ece_flag_cnt': 'ece_flag_count', 'fin_flag_cnt': 'fin_flag_count',
    'flow_byts_s': 'flow_bytes_s', 'flow_pkts_s': 'flow_packets_s',
    'fwd_blk_rate_avg': 'fwd_avg_bulk_rate', 'fwd_byts_b_avg': 'fwd_avg_bytes_bulk',
    'fwd_pkts_b_avg': 'fwd_avg_packets_bulk', 'fwd_header_len': 'fwd_header_length',
    'fwd_iat_tot': 'fwd_iat_total', 'fwd_pkt_len_max': 'fwd_packet_length_max',
    'fwd_pkt_len_mean': 'fwd_packet_length_mean', 'fwd_pkt_len_min': 'fwd_packet_length_min',
    'fwd_pkt_len_std': 'fwd_packet_length_std', 'fwd_pkts_s': 'fwd_packets_s',
    'init_bwd_win_byts': 'init_win_bytes_backward', 'init_fwd_win_byts': 'init_win_bytes_forward',
    'pkt_len_max': 'max_packet_length', 'pkt_len_min': 'min_packet_length',
    'fwd_seg_size_min': 'min_seg_size_forward', 'pkt_len_mean': 'packet_length_mean',
    'pkt_len_std': 'packet_length_std', 'pkt_len_var': 'packet_length_variance',
    'psh_flag_cnt': 'psh_flag_count', 'rst_flag_cnt': 'rst_flag_count',
    'subflow_bwd_byts': 'subflow_bwd_bytes', 'subflow_bwd_pkts': 'subflow_bwd_packets',
    'subflow_fwd_byts': 'subflow_fwd_bytes', 'subflow_fwd_pkts': 'subflow_fwd_packets',
    'syn_flag_cnt': 'syn_flag_count', 'tot_bwd_pkts': 'total_backward_packets',
    'tot_fwd_pkts': 'total_fwd_packets', 'totlen_bwd_pkts': 'total_length_of_bwd_packets',
    'totlen_fwd_pkts': 'total_length_of_fwd_packets', 'urg_flag_cnt': 'urg_flag_count',
}

# 2018 label -> 2017 canonical raw label (so FAMILY applies unchanged). Covers all 2018 days,
# not only the two we have, so adding days later needs no code change.
LABEL_2018_TO_2017 = {
    "Benign": "BENIGN",
    "DoS attacks-Hulk": "DoS Hulk", "DoS attacks-SlowHTTPTest": "DoS Slowhttptest",
    "DoS attacks-GoldenEye": "DoS GoldenEye", "DoS attacks-Slowloris": "DoS slowloris",
    "DDoS attacks-LOIC-HTTP": "DDoS", "DDOS attack-HOIC": "DDoS", "DDOS attack-LOIC-UDP": "DDoS",
    "FTP-BruteForce": "FTP-Patator", "SSH-Bruteforce": "SSH-Patator",
    "Brute Force -Web": "Web Attack - Brute Force", "Brute Force -XSS": "Web Attack - XSS",
    "SQL Injection": "Web Attack - Sql Injection",
    "Bot": "Bot", "Infilteration": "Infiltration",
}


def norm_col(c):
    return c.strip().lower().replace(' ', '_').replace('/', '_')


def aligned_features(feats_2017, cols_2018):
    """Return (aligned 2017-named feature list in 2017 order, rename map for 2018 columns)."""
    n2017 = {norm_col(c): c for c in feats_2017}
    rename = {}
    for c in cols_2018:
        k = ALIAS_2018_TO_2017.get(norm_col(c), norm_col(c))
        if k in n2017:
            rename[c] = n2017[k]
    aligned = [c for c in feats_2017 if c in set(rename.values())]
    return aligned, rename


def load_2018(feats_2017, verbose=True):
    """Load + clean the CICIDS2018 days present, renamed to 2017 column names, restricted to the
    aligned feature set. Same NaN/Inf rule as 2017. Returns (df, aligned_feats, info)."""
    paths = sorted(glob.glob(os.path.join(HERE, "cicids2018", "*.csv")))
    assert paths, "no CICIDS2018 CSVs found"
    header = pd.read_csv(paths[0], nrows=0).columns.str.strip()
    aligned, rename = aligned_features(feats_2017, header)
    src_cols = [c for c in header if c in rename] + ["Label"]
    frames, stray = [], 0
    for p in paths:
        # Read as text (repeated header rows make dtype inference unreliable) but in bounded
        # chunks, converting each chunk to float32 at once: ~2M rows x 76 text columns read in one
        # go would need ~8 GB of Python string objects.
        parts = []
        for d in pd.read_csv(p, usecols=lambda c: c.strip() in src_cols, dtype=str, chunksize=100_000):
            d.columns = d.columns.str.strip()
            bad = d["Label"].str.strip() == "Label"  # repeated header rows inside the CSV
            stray += int(bad.sum())
            d = d.loc[~bad].rename(columns=rename)
            for c in aligned:
                d[c] = pd.to_numeric(d[c], errors="coerce").astype("float32")
            parts.append(d)
        d = pd.concat(parts, ignore_index=True)
        del parts
        d["_src"] = os.path.basename(p)
        frames.append(d)
        if verbose:
            print(f"  loaded {os.path.basename(p)}: {len(d):,}")
    df = pd.concat(frames, ignore_index=True)
    df["_pos"] = np.arange(len(df))
    raw = df["Label"].str.strip()
    unknown = set(raw.unique()) - set(LABEL_2018_TO_2017)
    assert not unknown, f"unmapped 2018 labels: {unknown}"
    df["label_raw"] = raw.map(LABEL_2018_TO_2017)
    df["label_2018"] = raw
    n0 = len(df)
    df[aligned] = df[aligned].replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=aligned).reset_index(drop=True)
    df["_h"] = pd.util.hash_pandas_object(df[aligned], index=False).values
    info = {"rows_raw": n0, "stray_header_rows_dropped": stray, "rows_after_nan_inf_drop": len(df),
            "n_aligned_features": len(aligned),
            "dataset_files": {os.path.basename(p): os.path.getsize(p) for p in paths}}
    return df, aligned, info
