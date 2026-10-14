"""
exp006: diagnose the CICIDS2017 -> CICIDS2018 detection collapse (exp003, provisional finding P1)
and the 2018 duplication anomaly (P3). Diagnostic only: no detector is trained or evaluated here.

Populations are identical to exp003 (same loaders, same drop_conflicts dedup); this is asserted.

Questions
  Q1 unit/semantic consistency: do the CICFlowMeter identities hold in both datasets?
       Flow Duration * Flow Bytes/s   / (TotLen Fwd + TotLen Bwd)   -> 1e6 if duration is in us
       Flow Duration * Flow Packets/s / (Tot Fwd + Tot Bwd pkts)     -> 1e6
       Flow IAT Mean * (pkts - 1)     / Flow Duration                -> 1
     A ratio that differs between years points at a unit/definition change, not behaviour.
  Q2 which features shifted, per matched class (Benign, DoS Hulk): KS statistic, medians, p95,
     share of zeros, single-feature domain AUC
  Q3 how separable are the two years (adversarial validation: RF classifier 2017 vs 2018, holdout AUC)
     and where does 2018 DoS Hulk sit: closer to 2017 Hulk or to 2017 Benign?
  Q4 2018 duplication forensics: per label rows vs unique vectors, most repeated vectors

Usage: python exp006_shift_diagnosis.py
"""
import json
import os
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

import ids_common as C

EXP = os.path.join(C.HERE, "experiments", "exp006_shift_diagnosis")
EXP003 = os.path.join(C.HERE, "experiments", "exp003_cross_family", "data_prep.json")
SEED = 0
N_SUB = 100_000

ID_COLS = ["Flow Duration", "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Flow Bytes/s",
           "Flow Packets/s", "Total Fwd Packets", "Total Backward Packets", "Flow IAT Mean"]


def load_2018_with_duration(feats17):
    """Same procedure and row set as ids_common.load_2018, additionally keeping Flow Duration
    (excluded from the aligned features, needed only for the unit identities)."""
    import glob
    paths = sorted(glob.glob(os.path.join(C.HERE, "cicids2018", "*.csv")))
    header = pd.read_csv(paths[0], nrows=0).columns.str.strip()
    aligned, rename = C.aligned_features(feats17, header)
    src_cols = [c for c in header if c in rename] + ["Label", "Flow Duration"]
    frames = []
    for p in paths:
        parts = []
        for d in pd.read_csv(p, usecols=lambda c: c.strip() in src_cols, dtype=str, chunksize=100_000):
            d.columns = d.columns.str.strip()
            d = d.loc[d["Label"].str.strip() != "Label"].rename(columns=rename)
            for c in aligned + ["Flow Duration"]:
                d[c] = pd.to_numeric(d[c], errors="coerce").astype("float64" if c == "Flow Duration" else "float32")
            parts.append(d)
        frames.append(pd.concat(parts, ignore_index=True))
        del parts
    df = pd.concat(frames, ignore_index=True)
    df["_pos"] = np.arange(len(df))
    raw = df["Label"].str.strip()
    df["label_raw"] = raw.map(C.LABEL_2018_TO_2017)
    df[aligned] = df[aligned].replace([np.inf, -np.inf], np.nan)
    df = df.dropna(subset=aligned).reset_index(drop=True)
    df["_h"] = pd.util.hash_pandas_object(df[aligned], index=False).values
    return df, aligned


def identities(df):
    out = {}
    dur = df["Flow Duration"].astype("float64")
    byts = df["Total Length of Fwd Packets"].astype("float64") + df["Total Length of Bwd Packets"].astype("float64")
    pkts = df["Total Fwd Packets"].astype("float64") + df["Total Backward Packets"].astype("float64")
    ok = (dur > 0) & (byts > 0) & (df["Flow Bytes/s"] > 0)
    r = (dur * df["Flow Bytes/s"].astype("float64") / byts)[ok]
    out["duration_x_bytes_rate_over_bytes"] = r
    ok = (dur > 0) & (pkts > 0) & (df["Flow Packets/s"] > 0)
    out["duration_x_pkt_rate_over_pkts"] = (dur * df["Flow Packets/s"].astype("float64") / pkts)[ok]
    ok = (dur > 0) & (pkts >= 2)
    out["iat_mean_x_(pkts-1)_over_duration"] = (df["Flow IAT Mean"].astype("float64") * (pkts - 1) / dur)[ok]
    res = {}
    for k, v in out.items():
        v = v.replace([np.inf, -np.inf], np.nan).dropna()
        res[k] = {"n": int(len(v)), "median": float(v.median()) if len(v) else None,
                  "p05": float(v.quantile(0.05)) if len(v) else None,
                  "p95": float(v.quantile(0.95)) if len(v) else None}
    res["flow_duration_median"] = float(dur.median())
    res["flow_duration_p95"] = float(dur.quantile(0.95))
    return res


def sub(a, n, rng):
    return a[rng.choice(len(a), size=min(n, len(a)), replace=False)]


def domain_auc(Xa, Xb, feats, rng, top=15):
    Xa, Xb = sub(Xa, N_SUB, rng), sub(Xb, N_SUB, rng)
    X = np.vstack([Xa, Xb])
    y = np.r_[np.zeros(len(Xa)), np.ones(len(Xb))]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=SEED)
    m = RandomForestClassifier(n_estimators=100, max_depth=16, n_jobs=-1, random_state=SEED).fit(Xtr, ytr)
    auc = float(roc_auc_score(yte, m.predict_proba(Xte)[:, 1]))
    imp = sorted(zip(feats, m.feature_importances_), key=lambda t: -t[1])[:top]
    return {"n_per_domain": [int(len(Xa)), int(len(Xb))], "holdout_auc": auc,
            "top_importances": [[f, float(v)] for f, v in imp]}


def feature_shift(A, B, feats, rng):
    """A, B: 2017 and 2018 arrays for one class."""
    As, Bs = sub(A, N_SUB, rng), sub(B, N_SUB, rng)
    y = np.r_[np.zeros(len(As)), np.ones(len(Bs))]
    rows = []
    for j, f in enumerate(feats):
        a, b = As[:, j].astype("float64"), Bs[:, j].astype("float64")
        ks = ks_2samp(a, b)
        try:
            auc = roc_auc_score(y, np.r_[a, b])
        except ValueError:
            auc = 0.5
        rows.append({"feature": f, "ks": float(ks.statistic),
                     "median_2017": float(np.median(a)), "median_2018": float(np.median(b)),
                     "p95_2017": float(np.quantile(a, 0.95)), "p95_2018": float(np.quantile(b, 0.95)),
                     "zero_share_2017": float((a == 0).mean()), "zero_share_2018": float((b == 0).mean()),
                     "single_feature_domain_auc": float(max(auc, 1 - auc))})
    return sorted(rows, key=lambda r: -r["ks"])


def dup_forensics(df, feats, top=5):
    out = {}
    for lab, g in df.groupby("label_raw"):
        vc = g["_h"].value_counts()
        tops = []
        for h, n in vc.head(top).items():
            row = g.loc[g["_h"] == h, feats].iloc[0]
            nz = {f: float(v) for f, v in row.items() if v != 0}
            tops.append({"rows": int(n), "share_of_label": float(n / len(g)), "n_nonzero_features": len(nz),
                         "nonzero_values": nz})
        out[lab] = {"rows": int(len(g)), "unique_vectors": int(len(vc)),
                    "duplicate_share": float(1 - len(vc) / len(g)), "top_vectors": tops}
    return out


def plot_shift(shift_hulk, shift_ben, A17, B18, feats, fname):
    top = [r["feature"] for r in shift_hulk[:6]]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.5))
    for ax, f in zip(axes.ravel(), top):
        j = feats.index(f)
        for arr, lab, ls in [(A17[:, j], "DoS Hulk 2017", "-"), (B18[:, j], "DoS Hulk 2018", "--")]:
            v = np.sort(arr.astype("float64"))
            ax.plot(v, np.linspace(0, 1, len(v)), ls, label=lab)
        ax.set_xscale("symlog")
        ks = next(r["ks"] for r in shift_hulk if r["feature"] == f)
        ax.set_title(f"{f} (KS={ks:.2f})", fontsize=9)
        ax.set_ylabel("ECDF")
        ax.legend(fontsize=7)
    fig.suptitle("Most shifted features, DoS Hulk 2017 vs 2018 (empirical CDF, symlog x)")
    fig.tight_layout()
    fig.savefig(os.path.join(EXP, fname), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 7))
    k = {r["feature"]: r["ks"] for r in shift_ben}
    rows = shift_hulk[:20]
    y = np.arange(len(rows))
    ax.barh(y - 0.2, [r["ks"] for r in rows], 0.4, label="DoS Hulk")
    ax.barh(y + 0.2, [k[r["feature"]] for r in rows], 0.4, label="Benign")
    ax.set_yticks(y)
    ax.set_yticklabels([r["feature"] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("KS statistic, 2017 vs 2018")
    ax.set_title("Top-20 shifted features (ranked by DoS Hulk KS)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(EXP, "ks_top20.png"), dpi=150)
    plt.close(fig)


def main():
    os.makedirs(EXP, exist_ok=True)
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ref = json.load(open(EXP003, encoding="utf-8"))

    print("Loading 2017 ...", flush=True)
    d17, feats17, _ = C.load_2017()
    dup17 = None
    print("Loading 2018 (with Flow Duration) ...", flush=True)
    d18, aligned = load_2018_with_duration(feats17)

    print("Q4 duplication forensics (before dedup) ...", flush=True)
    dup18 = dup_forensics(d18, aligned)
    dup17 = {k: {kk: vv for kk, vv in v.items() if kk != "top_vectors"} | {"top_vectors": v["top_vectors"][:2]}
             for k, v in dup_forensics(d17, feats17, top=2).items()}

    d17 = C.apply_dedup(d17, "drop_conflicts")
    d18 = C.apply_dedup(d18, "drop_conflicts")
    cross_support = d18["label_raw"].value_counts().to_dict()
    assert cross_support == ref["cross_test_support"], (cross_support, ref["cross_test_support"])
    print("  2018 population identical to exp003: OK", flush=True)

    print("Q1 unit identities ...", flush=True)
    ident = {}
    for name, d in (("2017", d17), ("2018", d18)):
        for lab in ("BENIGN", "DoS Hulk"):
            ident[f"{name}/{lab}"] = identities(d[d["label_raw"] == lab])
    print(json.dumps(ident, indent=1), flush=True)

    A_b = d17.loc[d17["label_raw"] == "BENIGN", aligned].values
    A_h = d17.loc[d17["label_raw"] == "DoS Hulk", aligned].values
    B_b = d18.loc[d18["label_raw"] == "BENIGN", aligned].values
    B_h = d18.loc[d18["label_raw"] == "DoS Hulk", aligned].values
    A_all = d17[aligned].values
    B_all = d18[aligned].values
    del d17, d18

    print("Q2 per-feature shift ...", flush=True)
    shift_hulk = feature_shift(A_h, B_h, aligned, rng)
    shift_ben = feature_shift(A_b, B_b, aligned, rng)
    pd.DataFrame(shift_hulk).to_csv(os.path.join(EXP, "feature_shift_dos_hulk.csv"), index=False)
    pd.DataFrame(shift_ben).to_csv(os.path.join(EXP, "feature_shift_benign.csv"), index=False)

    print("Q3 adversarial validation ...", flush=True)
    adv = {
        "all_2017_vs_all_2018 (label-free)": domain_auc(A_all, B_all, aligned, rng),
        "benign_2017_vs_benign_2018": domain_auc(A_b, B_b, aligned, rng),
        "hulk_2017_vs_hulk_2018": domain_auc(A_h, B_h, aligned, rng),
        "hulk_2018_vs_benign_2017": domain_auc(A_b, B_h, aligned, rng),
        "hulk_2017_vs_benign_2017 (in-domain reference)": domain_auc(A_b, A_h, aligned, rng),
    }
    for k, v in adv.items():
        print(f"  {k}: AUC={v['holdout_auc']:.4f}", flush=True)
    plot_shift(shift_hulk, shift_ben, A_h, B_h, aligned, "ecdf_top6_dos_hulk.png")

    summary = {"population_matches_exp003": True, "unit_identities": ident, "adversarial_validation": adv,
               "feature_shift_top10_dos_hulk": shift_hulk[:10], "feature_shift_top10_benign": shift_ben[:10],
               "n_features_ks_gt_0.5": {"dos_hulk": sum(r["ks"] > 0.5 for r in shift_hulk),
                                        "benign": sum(r["ks"] > 0.5 for r in shift_ben)},
               "duplication_2018": dup18, "duplication_2017": dup17,
               "subsample_per_domain": N_SUB, "seed": SEED, "runtime_sec": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(EXP, "summary.json"), "w", encoding="utf-8"), indent=2)

    lines = ["## Q1 unit identities (median [p05, p95])", "",
             "| Dataset/class | dur×bytes_rate/bytes (1e6 = µs) | dur×pkt_rate/pkts (1e6) | IAT_mean×(pkts−1)/dur (1) | Flow Duration median |",
             "|---|---|---|---|---|"]
    for k, v in ident.items():
        c = lambda key: (f"{v[key]['median']:.4g} [{v[key]['p05']:.3g}, {v[key]['p95']:.3g}]"
                         if v[key]["median"] is not None else "-")
        lines.append(f"| {k} | {c('duration_x_bytes_rate_over_bytes')} | {c('duration_x_pkt_rate_over_pkts')} | "
                     f"{c('iat_mean_x_(pkts-1)_over_duration')} | {v['flow_duration_median']:.4g} |")
    lines += ["", "## Q3 adversarial validation (RF holdout AUC; 0.5 = indistinguishable)", ""]
    lines += [f"- {k}: **{v['holdout_auc']:.4f}** (n={v['n_per_domain']}); top features: "
              + ", ".join(f"{f} ({w:.3f})" for f, w in v["top_importances"][:5]) for k, v in adv.items()]
    lines += ["", "## Q2 top-10 shifted features, DoS Hulk (KS; medians 2017 → 2018)", "",
              "| Feature | KS | single-feature AUC | median 2017 | median 2018 | zero share 2017 | zero share 2018 |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['feature']} | {r['ks']:.3f} | {r['single_feature_domain_auc']:.3f} | {r['median_2017']:.4g} | "
              f"{r['median_2018']:.4g} | {r['zero_share_2017']:.2f} | {r['zero_share_2018']:.2f} |" for r in shift_hulk[:10]]
    lines += ["", f"Features with KS > 0.5: DoS Hulk {summary['n_features_ks_gt_0.5']['dos_hulk']}/75, "
              f"Benign {summary['n_features_ks_gt_0.5']['benign']}/75", "",
              "## Q4 duplication (before dedup)", "", "| Dataset | Label | Rows | Unique vectors | Duplicate share | Top vector share | Top vector non-zero features |",
              "|---|---|---|---|---|---|---|"]
    for ds, dd in (("2018", dup18), ("2017", dup17)):
        for lab, v in sorted(dd.items(), key=lambda t: -t[1]["rows"]):
            t = v["top_vectors"][0]
            lines.append(f"| {ds} | {lab} | {v['rows']:,} | {v['unique_vectors']:,} | {100*v['duplicate_share']:.1f}% | "
                         f"{100*t['share_of_label']:.1f}% | {t['n_nonzero_features']} |")
    open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)

    code = C.snapshot_code(EXP, ["exp006_shift_diagnosis.py", "ids_common.py"])
    C.write_manifest(EXP, experiment_id="exp006_shift_diagnosis", depends_on=["exp003_cross_family"],
                     description="Diagnosis of 2017->2018 collapse: unit identities, per-feature shift, "
                                 "adversarial validation, 2018 duplication forensics. No detector evaluated.",
                     scripts=code, cmd="python exp006_shift_diagnosis.py", seed=SEED, subsample_per_domain=N_SUB,
                     population="identical to exp003 (asserted)", runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
