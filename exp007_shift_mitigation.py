"""
exp007: can the 2017 -> 2018 matched-family collapse (exp003) be reduced without 2018 labels,
and how does it compare with a model trained on 2018?

Populations, split, families and scoring are identical to exp003 (asserted; scoring reuses
exp003_cross_family.score). Feature transforms (none of them use target labels):
  none            raw aligned features (= exp003)
  slog            sign(x)*log1p(|x|), same for both datasets (scale compression, not adaptive)
  robust_domain   per-dataset (x - median) / IQR; 2017 stats from the 2017 TRAIN partition,
                  2018 stats from all 2018 rows (unlabeled -> transductive)
  quantile_domain per-dataset QuantileTransformer to uniform; fitted as robust_domain
  drop_k10/k25    drop the k features with the largest KS statistic between 2017-train and 2018
                  (unlabeled, transductive)
Controls
  upper_2018      train AND test on 2018 (row-order split within label, as exp001-003): what is
                  achievable on 2018 with these features and this model
  reverse         train on all 2018, test on the 2017 reference test partition restricted to the raw
                  labels present in 2018 (BENIGN, DoS Hulk, DoS Slowhttptest, Web Attacks)
Models: RF (seeds 42,1,2) for every transform; XGBoost (seed 42) for every transform and upper bound.

Usage: python exp007_shift_mitigation.py
"""
import json
import os
import time

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.preprocessing import QuantileTransformer
from xgboost import XGBClassifier

import ids_common as C
import exp003_cross_family as E3

EXP = os.path.join(C.HERE, "experiments", "exp007_shift_mitigation")
RUNS = os.path.join(EXP, "runs")
EXP003 = os.path.join(C.HERE, "experiments", "exp003_cross_family", "data_prep.json")
RF_SEEDS = [42, 1, 2]
TRANSFORMS = ["none", "slog", "robust_domain", "quantile_domain", "drop_k10", "drop_k25"]
META = ["binary", "family", "label_raw"]


class XGBStage:
    """XGBoost with the notebook's hyperparameters; maps string labels <-> 0/1, balances classes
    with scale_pos_weight (binary problems only: Stage 1 and the 2-family Stage 2)."""

    def __init__(self, seed):
        self.seed = seed

    def fit(self, X, y):
        self.classes_ = np.array(sorted(np.unique(y)))
        assert len(self.classes_) == 2
        yi = (y == self.classes_[1]).astype(int)
        spw = float((yi == 0).sum() / max((yi == 1).sum(), 1))
        self.m = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, tree_method="hist",
                               device="cpu", eval_metric="logloss", scale_pos_weight=spw,
                               random_state=self.seed, n_jobs=-1).fit(X, yi)
        return self

    def predict(self, X):
        return self.classes_[self.m.predict(X)]


def make_model(kind, seed):
    return C.rf(seed) if kind == "rf" else XGBStage(seed)


def slog(X):
    return (np.sign(X) * np.log1p(np.abs(X))).astype("float32")


def robust_fit(X):
    med = np.median(X, axis=0)
    iqr = np.quantile(X, 0.75, axis=0) - np.quantile(X, 0.25, axis=0)
    iqr[iqr == 0] = 1.0
    return lambda Z: ((Z - med) / iqr).astype("float32")


def quantile_fit(X):
    qt = QuantileTransformer(n_quantiles=1000, output_distribution="uniform", subsample=200_000,
                             random_state=0).fit(X)
    return lambda Z: qt.transform(Z).astype("float32")


def ks_rank(Xa, Xb, feats, n=100_000, seed=0):
    rng = np.random.default_rng(seed)
    a = Xa[rng.choice(len(Xa), min(n, len(Xa)), replace=False)]
    b = Xb[rng.choice(len(Xb), min(n, len(Xb)), replace=False)]
    ks = [float(ks_2samp(a[:, j], b[:, j]).statistic) for j in range(len(feats))]
    return sorted(zip(feats, ks), key=lambda t: -t[1])


def frame(X, meta, feats):
    df = pd.DataFrame(X, columns=feats)
    for c in META:
        df[c] = meta[c].values
    return df


def fit_score(kind, seed, Xtr, ytr_b, ytr_f, tests, feats):
    s1 = make_model(kind, seed).fit(Xtr, ytr_b)
    mal = ytr_b == 1
    s2 = make_model(kind, seed).fit(Xtr[mal], ytr_f[mal])
    out = {name: E3.score(frame(X, meta, feats), feats, s1, s2) for name, (X, meta) in tests.items()}
    del s1, s2
    return out


def main():
    os.makedirs(RUNS, exist_ok=True)
    t0 = time.time()
    ref = json.load(open(EXP003, encoding="utf-8"))

    print("Loading (identical to exp003) ...", flush=True)
    d17, feats17, _ = C.load_2017()
    d17 = C.apply_dedup(d17, "drop_conflicts")
    C.add_taxonomies(d17, min_support=500)
    d17 = d17.sort_values("_pos").reset_index(drop=True)
    tr_mask, te_mask = C.make_split(d17, "temporal")
    d18, aligned, _ = C.load_2018(feats17)
    d18 = C.apply_dedup(d18, "drop_conflicts")
    d18["family"] = d18["label_raw"].map(C.FAMILY)
    d18["binary"] = (d18["label_raw"] != "BENIGN").astype(int)
    shared = d17["family"].isin(E3.SHARED).values
    tr17 = d17.loc[tr_mask & shared, aligned + META].reset_index(drop=True)
    te17 = d17.loc[te_mask & shared, aligned + META].reset_index(drop=True)
    d18 = d18.sort_values("_pos").reset_index(drop=True)
    tr18_mask, te18_mask = C.make_split(d18, "temporal")
    all18 = d18[aligned + META + ["_pos"]].reset_index(drop=True)
    del d17, d18
    assert tr17["label_raw"].value_counts().to_dict() == ref["train_support"]
    assert te17["label_raw"].value_counts().to_dict() == ref["ref_test_support"]
    assert all18["label_raw"].value_counts().to_dict() == ref["cross_test_support"]
    print("  populations identical to exp003: OK", flush=True)

    X_tr17, X_te17, X_18 = (tr17[aligned].values, te17[aligned].values, all18[aligned].values)
    M_tr17, M_te17, M_18 = tr17[META], te17[META], all18[META]
    del tr17, te17
    ks = ks_rank(X_tr17, X_18, aligned)
    json.dump({"ks_rank_2017train_vs_2018": ks}, open(os.path.join(EXP, "ks_rank.json"), "w"), indent=2)

    def transformed(name):
        """Return (feats, Xtr17, Xte17, X18) for transform `name`."""
        if name == "none":
            return aligned, X_tr17, X_te17, X_18
        if name == "slog":
            return aligned, slog(X_tr17), slog(X_te17), slog(X_18)
        if name in ("robust_domain", "quantile_domain"):
            fit = robust_fit if name == "robust_domain" else quantile_fit
            f17, f18 = fit(X_tr17), fit(X_18)
            return aligned, f17(X_tr17), f17(X_te17), f18(X_18)
        k = int(name.split("_k")[1])
        drop = {f for f, _ in ks[:k]}
        keep = [j for j, f in enumerate(aligned) if f not in drop]
        return [aligned[j] for j in keep], X_tr17[:, keep], X_te17[:, keep], X_18[:, keep]

    def save(rid, rec):
        json.dump(rec, open(os.path.join(RUNS, rid + ".json"), "w", encoding="utf-8"), indent=2)

    def log(rid, rec):
        c = rec["results"].get("cross") or rec["results"].get("test")
        print(f"{rid}: e2e={c['end_to_end']['macro_f1']:.4f} DoS={c['per_family']['DoS/DDoS']['e2e_recall']:.4f} "
              f"Web={c['per_family']['Web Attack']['e2e_recall']:.4f} FPR={c['stage1']['benign_fpr']:.5f} "
              f"({rec['runtime_sec']}s)", flush=True)

    # ---- forward 2017 -> 2018, all transforms
    for tname in TRANSFORMS:
        jobs = [("rf", s) for s in RF_SEEDS] + [("xgb", 42)]
        todo = [(k, s) for k, s in jobs if not os.path.exists(os.path.join(RUNS, f"fwd_{tname}_{k}{s}.json"))]
        if not todo:
            continue
        feats, Xa, Xb, Xc = transformed(tname)
        for kind, seed in todo:
            rid = f"fwd_{tname}_{kind}{seed}"
            t1 = time.time()
            res = fit_score(kind, seed, Xa, M_tr17["binary"].values, M_tr17["family"].values,
                            {"reference": (Xb, M_te17), "cross": (Xc, M_18)}, feats)
            rec = {"run_id": rid, "direction": "2017->2018", "transform": tname, "model": kind, "seed": seed,
                   "n_features": len(feats), "dropped_features": sorted(set(aligned) - set(feats)),
                   "results": res, "runtime_sec": round(time.time() - t1, 1)}
            save(rid, rec)
            log(rid, rec)
        del Xa, Xb, Xc

    # ---- upper bound: 2018 -> 2018 (row-order split within label)
    Xu_tr, Xu_te = X_18[tr18_mask], X_18[te18_mask]
    Mu_tr, Mu_te = M_18[tr18_mask].reset_index(drop=True), M_18[te18_mask].reset_index(drop=True)
    for kind, seed in [("rf", s) for s in RF_SEEDS] + [("xgb", 42)]:
        rid = f"upper2018_none_{kind}{seed}"
        if os.path.exists(os.path.join(RUNS, rid + ".json")):
            continue
        t1 = time.time()
        res = fit_score(kind, seed, Xu_tr, Mu_tr["binary"].values, Mu_tr["family"].values,
                        {"test": (Xu_te, Mu_te)}, aligned)
        rec = {"run_id": rid, "direction": "2018->2018", "transform": "none", "model": kind, "seed": seed,
               "train_support": Mu_tr["label_raw"].value_counts().to_dict(),
               "test_support": Mu_te["label_raw"].value_counts().to_dict(),
               "results": res, "runtime_sec": round(time.time() - t1, 1)}
        save(rid, rec)
        log(rid, rec)
    del Xu_tr, Xu_te

    # ---- reverse: 2018 -> 2017 reference test restricted to raw labels present in 2018
    keep_r = M_te17["label_raw"].isin(set(M_18["label_raw"])).values
    Xr_te, Mr_te = X_te17[keep_r], M_te17[keep_r].reset_index(drop=True)
    for tname in ("none", "quantile_domain"):
        rid = f"rev_{tname}_rf42"
        if os.path.exists(os.path.join(RUNS, rid + ".json")):
            continue
        t1 = time.time()
        if tname == "none":
            Xs, Xt = X_18, Xr_te
        else:
            Xs, Xt = quantile_fit(X_18)(X_18), quantile_fit(Xr_te)(Xr_te)
        res = fit_score("rf", 42, Xs, M_18["binary"].values, M_18["family"].values,
                        {"cross": (Xt, Mr_te)}, aligned)
        rec = {"run_id": rid, "direction": "2018->2017", "transform": tname, "model": "rf", "seed": 42,
               "test_support": Mr_te["label_raw"].value_counts().to_dict(), "results": res,
               "runtime_sec": round(time.time() - t1, 1)}
        save(rid, rec)
        log(rid, rec)

    # ---- summary
    runs = [json.load(open(os.path.join(RUNS, f), encoding="utf-8")) for f in sorted(os.listdir(RUNS))]

    def agg(rs, side, get):
        v = np.array([get(r["results"][side]) for r in rs], dtype=float)
        return (v.mean(), v.std(ddof=1) if len(v) > 1 else np.nan, len(v))

    e2e = lambda s: s["end_to_end"]["macro_f1"]
    base = {k: agg([r for r in runs if r["run_id"].startswith(f"fwd_none_{k}")], "cross", e2e)[0] for k in ("rf", "xgb")}
    refb = {k: agg([r for r in runs if r["run_id"].startswith(f"fwd_none_{k}")], "reference", e2e)[0] for k in ("rf", "xgb")}
    f = lambda t: f"{t[0]:.4f}" + (f" ± {t[1]:.4f}" if t[2] > 1 else "")
    lines = ["| Direction | Transform | Model | n | Ref E2E F1 | Cross E2E F1 | Gap recovered | DoS recall | Web recall | Benign FPR | Stage2 GT F1 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    groups = {}
    for r in runs:
        groups.setdefault((r["direction"], r["transform"], r["model"]), []).append(r)
    for (dirn, tname, kind), rs in groups.items():
        side = "cross" if "cross" in rs[0]["results"] else "test"
        c = agg(rs, side, e2e)
        refc = agg(rs, "reference", e2e) if "reference" in rs[0]["results"] else None
        rec = (f"{100 * (c[0] - base[kind]) / (refb[kind] - base[kind]):.1f}%"
               if dirn == "2017->2018" and refb[kind] != base[kind] else "-")
        lines.append(
            f"| {dirn} | {tname} | {kind} | {c[2]} | {f(refc) if refc else '-'} | {f(c)} | {rec} | "
            f"{f(agg(rs, side, lambda s: s['per_family']['DoS/DDoS']['e2e_recall']))} | "
            f"{f(agg(rs, side, lambda s: s['per_family']['Web Attack']['e2e_recall']))} | "
            f"{f(agg(rs, side, lambda s: 100 * s['stage1']['benign_fpr']))}% | "
            f"{f(agg(rs, side, lambda s: s['stage2_gt']['macro_f1']))} |")
    table = "\n".join(lines)
    open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8").write(
        "Gap recovered = (cross E2E − cross E2E with no transform) / (reference E2E − cross E2E), same model.\n\n"
        + table + "\n")
    print(table, flush=True)

    code = C.snapshot_code(EXP, ["exp007_shift_mitigation.py", "exp003_cross_family.py", "ids_common.py"])
    C.write_manifest(EXP, experiment_id="exp007_shift_mitigation", depends_on=["exp003_cross_family", "exp006_shift_diagnosis"],
                     description="Label-free (transductive) mitigation of 2017->2018 shift; 2018 upper bound; reverse direction; XGBoost",
                     scripts=code, cmd="python exp007_shift_mitigation.py", rf_seeds=RF_SEEDS, xgb_seed=42,
                     transforms=TRANSFORMS, target_label_use="none (target feature statistics only)",
                     population="identical to exp003 (asserted)", runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
