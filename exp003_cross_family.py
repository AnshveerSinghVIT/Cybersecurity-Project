"""
exp003: matched-family cross-dataset test, CICIDS2017 -> CICIDS2018.

Scope: only the families present in BOTH datasets' available days: Benign, DoS/DDoS, Web Attack.
This is a two-family experiment and must not be read as generalisation to other attack families.

Design
  - identical rules on both datasets: same NaN/Inf drop, same dedup policy (drop_conflicts),
    same label canonicalisation -> same FAMILY map, same aligned feature list (2017 names/order)
  - training: 2017 temporal-split TRAIN partition (same split as exp001/002), restricted to the
    three shared families
  - reference (2017->2017): the same models scored on the 2017 temporal TEST partition restricted
    to the same families  => separates ordinary difficulty from distribution shift
  - cross (2017->2018): the same models scored on all deduplicated 2018 rows (zero-shot)
  - hierarchy: Stage 1 binary, Stage 2 family (DoS/DDoS vs Web Attack), scored on ground-truth
    malicious and end-to-end (3 classes)
  - variation: RF seed only (split is deterministic) -> this measures model randomness
  - prevalence differs between reference and cross test sets, so recall per family and benign FPR
    (prevalence-independent) are reported alongside F1/precision; recall gets a Wilson 95% CI

Usage: python exp003_cross_family.py [--seeds 42 1 2 3 4]
"""
import argparse
import json
import os
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, f1_score

import ids_common as C

EXP = os.path.join(C.HERE, "experiments", "exp003_cross_family")
SHARED = ["Benign", "DoS/DDoS", "Web Attack"]
ATTACKS = ["DoS/DDoS", "Web Attack"]


wilson = C.wilson_ci


def score(test, feats, s1, s2):
    X = test[feats].values
    yb = test["binary"].values
    p1 = s1.predict(X)
    p2 = s2.predict(X)
    e2e_pred = np.where(p1 == 1, p2, "Benign")
    y_fam = test["family"].values
    n_ben = int((yb == 0).sum())
    fp = int(((yb == 0) & (p1 == 1)).sum())
    mal = yb == 1

    res = {
        "n_test": int(len(test)),
        "support": {f: int((y_fam == f).sum()) for f in SHARED},
        "stage1": {
            "malicious_f1": float(f1_score(yb, p1, zero_division=0)),
            "macro_f1": float(f1_score(yb, p1, average="macro", zero_division=0)),
            "benign_test_flows": n_ben, "benign_false_positives": fp,
            "benign_fpr": fp / n_ben if n_ben else float("nan"),
        },
        "stage2_gt": {
            "macro_f1": float(f1_score(y_fam[mal], p2[mal], labels=ATTACKS, average="macro", zero_division=0)),
        },
        "end_to_end": {
            "macro_f1": float(f1_score(y_fam, e2e_pred, labels=SHARED, average="macro", zero_division=0)),
        },
        "per_family": {},
        "per_raw_label": {},
    }
    for f in SHARED:
        m = y_fam == f
        k_det = int((p1[m] == (0 if f == "Benign" else 1)).sum())
        k_e2e = int((e2e_pred[m] == f).sum())
        n = int(m.sum())
        pred_f = e2e_pred == f
        res["per_family"][f] = {
            "n": n,
            "stage1_recall": k_det / n if n else float("nan"),
            "stage1_recall_ci95": wilson(k_det, n),
            "e2e_recall": k_e2e / n if n else float("nan"),
            "e2e_recall_ci95": wilson(k_e2e, n),
            "e2e_precision": float((y_fam[pred_f] == f).mean()) if pred_f.any() else float("nan"),
            "stage2_gt_recall": (float((p2[m] == f).mean()) if (n and f != "Benign") else None),
        }
    for lab, idx in test.groupby("label_raw").indices.items():
        f = C.FAMILY[lab]
        n = len(idx)
        k_det = int((p1[idx] == (0 if f == "Benign" else 1)).sum())
        k_e2e = int((e2e_pred[idx] == f).sum())
        res["per_raw_label"][lab] = {"n": n, "family": f,
                                    "stage1_recall": k_det / n, "stage1_recall_ci95": wilson(k_det, n),
                                    "e2e_recall": k_e2e / n, "e2e_recall_ci95": wilson(k_e2e, n)}
    cm = confusion_matrix(y_fam, e2e_pred, labels=SHARED)
    res["confusion_e2e"] = {"labels": SHARED, "counts": cm.tolist()}
    return res


def plot_pair(ref_cm, cross_cm, fname, title):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, (name, cm) in zip(axes, [("2017 -> 2017 (reference)", ref_cm), ("2017 -> 2018 (cross)", cross_cm)]):
        cm = np.asarray(cm, dtype=float)
        norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
        ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
        for i in range(len(SHARED)):
            for j in range(len(SHARED)):
                ax.text(j, i, f"{norm[i, j]:.2f}\n(n={int(cm[i, j]):,})", ha="center", va="center",
                        fontsize=8, color="white" if norm[i, j] > 0.5 else "black")
        ax.set_xticks(range(len(SHARED)))
        ax.set_yticks(range(len(SHARED)))
        ax.set_xticklabels(SHARED)
        ax.set_yticklabels(SHARED)
        ax.set_xlabel("Predicted (end-to-end)")
        ax.set_ylabel("True family (row-normalised)")
        ax.set_title(name)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP, fname), dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 1, 2, 3, 4])
    ap.add_argument("--trees", type=int, default=100)
    args = ap.parse_args()
    os.makedirs(EXP, exist_ok=True)
    t0 = time.time()

    print("Loading 2017 ...")
    d17, feats17, info17 = C.load_2017()
    conf17, _ = C.conflict_stats(d17)
    d17 = C.apply_dedup(d17, "drop_conflicts")
    C.add_taxonomies(d17, min_support=500)
    d17 = d17.sort_values("_pos").reset_index(drop=True)
    tr_mask, te_mask = C.make_split(d17, "temporal")

    print("Loading 2018 ...")
    d18, aligned, info18 = C.load_2018(feats17)
    conf18, _ = C.conflict_stats(d18)
    d18 = C.apply_dedup(d18, "drop_conflicts")
    d18["family"] = d18["label_raw"].map(C.FAMILY)
    d18["binary"] = (d18["label_raw"] != "BENIGN").astype(int)
    assert set(d18["family"]) <= set(SHARED), set(d18["family"])
    print(f"  aligned features: {len(aligned)} (2017 had {len(feats17)}; "
          f"dropped: {sorted(set(feats17) - set(aligned))})")

    shared17 = d17["family"].isin(SHARED).values
    train = d17.loc[tr_mask & shared17, aligned + ["binary", "family", "label_raw"]]
    ref_test = d17.loc[te_mask & shared17, aligned + ["binary", "family", "label_raw"]]
    cross_test = d18[aligned + ["binary", "family", "label_raw", "label_2018"]]
    del d17, d18
    data = {
        "aligned_features": aligned,
        "dropped_from_2017": sorted(set(feats17) - set(aligned)),
        "load_2017": info17, "load_2018": info18,
        "conflicts_2017_before_dedup": conf17, "conflicts_2018_before_dedup": conf18,
        "train_support": train["label_raw"].value_counts().to_dict(),
        "ref_test_support": ref_test["label_raw"].value_counts().to_dict(),
        "cross_test_support": cross_test["label_raw"].value_counts().to_dict(),
        "cross_test_support_2018_names": cross_test["label_2018"].value_counts().to_dict(),
    }
    with open(os.path.join(EXP, "data_prep.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print("  train:", data["train_support"])
    print("  ref test:", data["ref_test_support"])
    print("  cross test:", data["cross_test_support"])
    print(f"  ready ({time.time()-t0:.0f}s)")

    mal_tr = train[train["binary"] == 1]
    runs = []
    for seed in args.seeds:
        t1 = time.time()
        s1 = C.rf(seed, args.trees).fit(train[aligned].values, train["binary"].values)
        s2 = C.rf(seed, args.trees).fit(mal_tr[aligned].values, mal_tr["family"].values)
        r = {"seed": seed, "reference": score(ref_test, aligned, s1, s2),
             "cross": score(cross_test, aligned, s1, s2)}
        del s1, s2
        r["runtime_sec"] = round(time.time() - t1, 1)
        runs.append(r)
        with open(os.path.join(EXP, f"run_seed{seed}.json"), "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)
        print(f"seed {seed}: ref e2e={r['reference']['end_to_end']['macro_f1']:.4f} "
              f"cross e2e={r['cross']['end_to_end']['macro_f1']:.4f} "
              f"| cross recall DoS={r['cross']['per_family']['DoS/DDoS']['e2e_recall']:.3f} "
              f"Web={r['cross']['per_family']['Web Attack']['e2e_recall']:.3f} "
              f"FPR={r['cross']['stage1']['benign_fpr']:.4f} ({r['runtime_sec']}s)", flush=True)
        if seed == args.seeds[0]:
            plot_pair(r["reference"]["confusion_e2e"]["counts"], r["cross"]["confusion_e2e"]["counts"],
                      f"cm_e2e_ref_vs_cross_seed{seed}.png",
                      f"Matched-family end-to-end confusion (RF seed {seed})")

    # ---- aggregate (mean ± std over model seeds)
    def ms(vals):
        v = [x for x in vals if x is not None and not np.isnan(x)]
        return {"mean": float(np.mean(v)), "std": float(np.std(v, ddof=1)) if len(v) > 1 else 0.0}

    summary = {}
    for side in ("reference", "cross"):
        s = {
            "stage1_malicious_f1": ms([r[side]["stage1"]["malicious_f1"] for r in runs]),
            "stage1_benign_fpr": ms([r[side]["stage1"]["benign_fpr"] for r in runs]),
            "stage2_gt_macro_f1": ms([r[side]["stage2_gt"]["macro_f1"] for r in runs]),
            "e2e_macro_f1": ms([r[side]["end_to_end"]["macro_f1"] for r in runs]),
            "per_family": {f: {k: ms([r[side]["per_family"][f][k] for r in runs])
                               for k in ("stage1_recall", "e2e_recall", "e2e_precision")}
                           | {"n": runs[0][side]["per_family"][f]["n"]} for f in SHARED},
            "per_raw_label": {l: {k: ms([r[side]["per_raw_label"][l][k] for r in runs])
                                  for k in ("stage1_recall", "e2e_recall")}
                              | {"n": runs[0][side]["per_raw_label"][l]["n"]}
                              for l in runs[0][side]["per_raw_label"]},
        }
        summary[side] = s
    with open(os.path.join(EXP, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    fmt = lambda d: f"{d['mean']:.4f} ± {d['std']:.4f}"
    lines = ["| Metric | 2017→2017 (reference) | 2017→2018 (cross) |", "|---|---|---|"]
    for k, name in [("stage1_malicious_f1", "Stage 1 malicious F1"), ("stage1_benign_fpr", "Stage 1 benign FPR"),
                    ("stage2_gt_macro_f1", "Stage 2 family macro-F1 (GT malicious)"),
                    ("e2e_macro_f1", "End-to-end 3-class macro-F1")]:
        lines.append(f"| {name} | {fmt(summary['reference'][k])} | {fmt(summary['cross'][k])} |")
    for f in SHARED:
        for k, name in [("stage1_recall", "Stage 1 recall"), ("e2e_recall", "E2E recall"),
                        ("e2e_precision", "E2E precision")]:
            lines.append(f"| {f}: {name} (n={summary['reference']['per_family'][f]['n']:,} / "
                         f"{summary['cross']['per_family'][f]['n']:,}) | {fmt(summary['reference']['per_family'][f][k])} | "
                         f"{fmt(summary['cross']['per_family'][f][k])} |")
    lines += ["", "Per raw label (end-to-end recall):", "",
              "| Raw label | n ref | ref E2E recall | n cross | cross E2E recall |", "|---|---|---|---|---|"]
    labs = sorted(set(summary["reference"]["per_raw_label"]) | set(summary["cross"]["per_raw_label"]))
    for l in labs:
        a = summary["reference"]["per_raw_label"].get(l)
        b = summary["cross"]["per_raw_label"].get(l)
        lines.append(f"| {l} | {a['n'] if a else '-'} | {fmt(a['e2e_recall']) if a else '-'} | "
                     f"{b['n'] if b else '-'} | {fmt(b['e2e_recall']) if b else '-'} |")
    table = "\n".join(lines)
    with open(os.path.join(EXP, "summary.md"), "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print(table)

    C.write_manifest(
        EXP, experiment_id="exp003_cross_family", depends_on=["exp001_baseline", "exp002_seeds"],
        description="Matched-family (Benign, DoS/DDoS, Web Attack) cross-dataset 2017->2018 vs 2017->2017 reference",
        scripts=C.snapshot_code(EXP, ["exp003_cross_family.py", "ids_common.py"]),
        cmd=f"python exp003_cross_family.py --seeds {' '.join(map(str, args.seeds))} --trees {args.trees}",
        seeds=args.seeds, seed_meaning="RF random_state only; temporal split is deterministic",
        model="RandomForest(n_estimators=%d,max_depth=20,class_weight=balanced)" % args.trees,
        dedup_policy="drop_conflicts on both datasets (2017 hash over its 76 features as in exp001/002; "
                     "2018 hash over the aligned features)",
        class_mapping="2018 labels -> 2017 raw labels via ids_common.LABEL_2018_TO_2017, then ids_common.FAMILY",
        feature_alignment="ids_common.ALIAS_2018_TO_2017 (same as notebook); 2017 names and order",
        runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
