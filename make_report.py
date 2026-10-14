"""
Read-only: consolidate saved experiment outputs into experiments/REPORT_tables.md.
Never trains or modifies experiment outputs.

Effect rule (applied to differences between configurations, same metric):
  NOISE = 0.013 (model-seed SD of family GT macro-F1, exp002 row-order split, n=5)
  - "exceeds floor"  : |delta| > NOISE AND, when both sides have >=2 seeds, |delta| > 2*sqrt(sd1^2+sd2^2)
  - "within noise"   : otherwise
  - single-seed comparisons are flagged "1 seed - provisional" even when |delta| > NOISE
"""
import glob
import json
import os

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
EXPD = os.path.join(HERE, "experiments")
NOISE = 0.013
L = []


def j(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def msd(v):
    v = np.asarray([x for x in v if x is not None and not np.isnan(x)], dtype=float)
    if len(v) == 0:
        return {"n": 0, "mean": np.nan, "sd": np.nan, "ci": [np.nan, np.nan]}
    if len(v) == 1:
        return {"n": 1, "mean": float(v[0]), "sd": np.nan, "ci": [np.nan, np.nan]}
    sd = float(v.std(ddof=1))
    h = float(stats.t.ppf(0.975, len(v) - 1) * sd / np.sqrt(len(v)))
    return {"n": len(v), "mean": float(v.mean()), "sd": sd, "ci": [float(v.mean() - h), float(v.mean() + h)]}


def fmt(s, pct=False):
    k = 100 if pct else 1
    if s["n"] == 0:
        return "-"
    if s["n"] == 1:
        return f"{k*s['mean']:.4f} (1 seed)"
    return f"{k*s['mean']:.4f} ± {k*s['sd']:.4f} [95% CI {k*s['ci'][0]:.4f}, {k*s['ci'][1]:.4f}]"


def effect(a, b):
    d = b["mean"] - a["mean"]
    if a["n"] < 2 or b["n"] < 2:
        verdict = ("exceeds floor (1 seed - provisional)" if abs(d) > NOISE else "within noise (1 seed)")
    else:
        thr = max(NOISE, 2 * np.sqrt(a["sd"] ** 2 + b["sd"] ** 2))
        verdict = "EXCEEDS noise floor" if abs(d) > thr else "within noise"
    return f"{d:+.4f}", verdict


def h(t):
    L.append("")
    L.append(t)
    L.append("")


# ------------------------------------------------------------------ queue
qs = j(os.path.join(EXPD, "queue_status.json")) if os.path.exists(os.path.join(EXPD, "queue_status.json")) else None
h("## Queue execution")
if qs:
    L.append(f"Started {qs['queue_started']}, finished {qs.get('queue_finished')}; stop reason: {qs.get('stop_reason')}; "
             f"not run: {qs.get('not_run')}")
    L.append(f"Integrity: datasets unchanged = {qs.get('datasets_unchanged')}, sources unchanged = "
             f"{qs.get('sources_unchanged')}, exp001 artifacts unchanged = {qs.get('exp001_unchanged')}")
    L.append("")
    L.append("| Step | Status | Elapsed | Peak working set | Min system RAM available | Exit | Failure |")
    L.append("|---|---|---|---|---|---|---|")
    for s in qs["steps"]:
        L.append(f"| {s['id']} | {s['status']} | {s.get('elapsed_sec', 0)/60:.1f} min | {s.get('peak_working_set_gb')} GB | "
                 f"{s.get('min_system_available_gb')} GB | {s.get('exit_code')} | {s.get('failure_reason', '')} |")

# ------------------------------------------------------------------ exp002
p = os.path.join(EXPD, "exp002_seeds", "runs")
if os.path.isdir(p):
    runs = [j(f) for f in glob.glob(os.path.join(p, "*.json"))]
    groups = {"row-order / model seed": [r for r in runs if r["scheme"] == "temporal"],
              "random / split seed": [r for r in runs if r["group"] == "random/split"],
              "random / model seed": [r for r in runs if r["scheme"] == "random" and r["split_seed"] == 42]}
    metrics = {"Stage1 malicious F1": lambda r: r["stage1"]["malicious_f1"],
               "Stage1 benign FPR (%)": lambda r: 100 * r["stage1"]["benign_fpr"],
               "Family GT macro-F1": lambda r: r["stage2_family"]["gt_malicious"]["macro_f1"],
               "Family E2E macro-F1": lambda r: r["stage2_family"]["end_to_end"]["macro_f1"],
               "Fine GT macro-F1": lambda r: r["stage2_fine"]["gt_malicious"]["macro_f1"],
               "Fine E2E macro-F1": lambda r: r["stage2_fine"]["end_to_end"]["macro_f1"]}
    h("## exp002 - seed variability (mean ± SD, t-based 95% CI over seeds)")
    L.append("| Metric | " + " | ".join(f"{g} (n={len(v)})" for g, v in groups.items()) + " |")
    L.append("|---|" + "---|" * len(groups))
    S = {}
    for m, f in metrics.items():
        S[m] = {g: msd([f(r) for r in v]) for g, v in groups.items()}
        L.append(f"| {m} | " + " | ".join(fmt(S[m][g]) for g in groups) + " |")
    h("exp002 effect: row-order vs random split (random/model group as comparator, both n=5)")
    L.append("| Metric | Δ (row-order − random) | Verdict |")
    L.append("|---|---|---|")
    for m in metrics:
        if "FPR" in m:
            continue
        d, v = effect(S[m]["random / model seed"], S[m]["row-order / model seed"])
        L.append(f"| {m} | {d} | {v} |")
    h("exp002 per-class recall (family GT), mean ± SD")
    for g, v in groups.items():
        cls = v[0]["stage2_family"]["gt_malicious"]["per_class"].keys()
        L.append(f"- {g}: " + "; ".join(
            f"{c} {fmt(msd([r['stage2_family']['gt_malicious']['per_class'][c]['recall'] for r in v]))}"
            for c in cls))

# ------------------------------------------------------------------ exp003
p = os.path.join(EXPD, "exp003_cross_family")
rs = sorted(glob.glob(os.path.join(p, "run_seed*.json")))
if rs:
    runs = [j(f) for f in rs]
    h(f"## exp003 - matched-family cross-dataset (RF seeds n={len(runs)})")
    m3 = {"Stage1 malicious F1": lambda s: s["stage1"]["malicious_f1"],
          "Stage1 benign FPR (%)": lambda s: 100 * s["stage1"]["benign_fpr"],
          "Stage2 family macro-F1 (GT)": lambda s: s["stage2_gt"]["macro_f1"],
          "E2E 3-class macro-F1": lambda s: s["end_to_end"]["macro_f1"]}
    for fam in ("Benign", "DoS/DDoS", "Web Attack"):
        m3[f"{fam} E2E recall"] = (lambda fam: lambda s: s["per_family"][fam]["e2e_recall"])(fam)
        m3[f"{fam} Stage1 recall"] = (lambda fam: lambda s: s["per_family"][fam]["stage1_recall"])(fam)
    L.append("| Metric | 2017→2017 reference | 2017→2018 cross | Δ (cross − ref) | Verdict |")
    L.append("|---|---|---|---|---|")
    for m, f in m3.items():
        a, b = msd([f(r["reference"]) for r in runs]), msd([f(r["cross"]) for r in runs])
        d, v = effect(a, b)
        L.append(f"| {m} | {fmt(a)} | {fmt(b)} | {d} | {'(rate in %)' if 'FPR' in m else v} |")
    r0 = runs[0]
    h(f"exp003 Wilson 95% CIs (seed {r0['seed']}) and supports")
    for side in ("reference", "cross"):
        for fam, v in r0[side]["per_family"].items():
            L.append(f"- {side} {fam}: n={v['n']:,}, E2E recall {v['e2e_recall']:.4f} "
                     f"[{v['e2e_recall_ci95'][0]:.4f}, {v['e2e_recall_ci95'][1]:.4f}], Stage1 recall "
                     f"{v['stage1_recall']:.4f} [{v['stage1_recall_ci95'][0]:.4f}, {v['stage1_recall_ci95'][1]:.4f}]")
        for lab, v in r0[side]["per_raw_label"].items():
            L.append(f"  - {side} raw label {lab}: n={v['n']:,}, E2E recall {v['e2e_recall']:.4f} "
                     f"[{v['e2e_recall_ci95'][0]:.4f}, {v['e2e_recall_ci95'][1]:.4f}]")

# ------------------------------------------------------------------ exp005
p = os.path.join(EXPD, "exp005_dedup_sensitivity", "runs")
if os.path.isdir(p):
    runs = {os.path.basename(f)[:-5]: j(f) for f in glob.glob(os.path.join(p, "*.json"))}
    h("## exp005 - dedup / label-conflict policy sensitivity (RF seed 42; single seed per config)")
    L.append("| Split | Policy | Test set | n test | Mal-F1 | Benign FPR [95% CI] | Family GT | Fine GT | PortScan fam-GT recall [95% CI] |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for rid, r in sorted(runs.items()):
        for view in ("own_test", "common_test"):
            if view not in r:
                continue
            v = r[view]
            ps = v["stage2_family"]["gt_malicious"]["per_class"].get("PortScan")
            ci = v["stage1"].get("benign_fpr_ci95", [np.nan, np.nan])
            L.append(f"| {r['split']} ({r['split_unit']}) | {r['policy']} | {view} | {v['n_test']:,} | "
                     f"{v['stage1']['malicious_f1']:.4f} | {100*v['stage1']['benign_fpr']:.3f}% "
                     f"[{100*ci[0]:.3f}, {100*ci[1]:.3f}] | {v['stage2_family']['gt_malicious']['macro_f1']:.4f} | "
                     f"{v['stage2_fine']['gt_malicious']['macro_f1']:.4f} | "
                     + (f"{ps['recall']:.3f} (n={ps['support']}) [{ps['recall_ci95'][0]:.3f}, {ps['recall_ci95'][1]:.3f}]"
                        if ps else "-") + " |")
    h("exp005 effects vs drop_conflicts on the COMMON test set (isolates training-side policy effect)")
    L.append("| Split | Policy | Δ Family GT | verdict | Δ Mal-F1 | verdict |")
    L.append("|---|---|---|---|---|---|")
    for sp in ("temporal", "random"):
        base = runs.get(f"{sp}_drop_conflicts_model42")
        if not base:
            continue
        for pol in ("keep_first", "majority", "none"):
            r = runs.get(f"{sp}_{pol}_model42")
            if not r:
                continue
            one = lambda x: {"n": 1, "mean": x, "sd": np.nan}
            d1, v1 = effect(one(base["common_test"]["stage2_family"]["gt_malicious"]["macro_f1"]),
                            one(r["common_test"]["stage2_family"]["gt_malicious"]["macro_f1"]))
            d2, v2 = effect(one(base["common_test"]["stage1"]["malicious_f1"]), one(r["common_test"]["stage1"]["malicious_f1"]))
            L.append(f"| {sp} | {pol} | {d1} | {v1} | {d2} | {v2} |")
    a, b = runs.get("random_none_model42"), runs.get("random_none_rowsplit_model42")
    if a and b:
        h("exp005 exact-duplicate leakage: no dedup, group-level random split vs row-level random split")
        L.append(f"- test rows with an exact duplicate in train (row split): "
                 f"{100*b.get('test_rows_with_exact_duplicate_in_train', np.nan):.2f}%")
        for k, f in {"Mal-F1": lambda v: v["stage1"]["malicious_f1"],
                     "Family GT": lambda v: v["stage2_family"]["gt_malicious"]["macro_f1"],
                     "Fine GT": lambda v: v["stage2_fine"]["gt_malicious"]["macro_f1"]}.items():
            one = lambda x: {"n": 1, "mean": x, "sd": np.nan}
            d, v = effect(one(f(a["own_test"])), one(f(b["own_test"])))
            L.append(f"- {k}: group split {f(a['own_test']):.4f} -> row split {f(b['own_test']):.4f} (Δ {d}, {v})")

# ------------------------------------------------------------------ exp004
p = os.path.join(EXPD, "exp004_leakage_vs_drift")
if os.path.isdir(os.path.join(p, "runs")):
    runs = [j(f) for f in glob.glob(os.path.join(p, "runs", "*.json"))]
    prep = j(os.path.join(p, "data_prep.json")) if os.path.exists(os.path.join(p, "data_prep.json")) else {}
    h("## exp004 - leakage vs drift (seeds: split+RF seed for random/grouped splits; RF seed only for forward/roworder)")
    if prep:
        L.append(f"Row alignment (labelled vs ML release): " + ", ".join(
            f"{k.split('.')[0]}={v['row_match_rate']}" for k, v in prep["alignment_checks"].items()))
        L.append(f"Row-order vs true-time split overlap: {prep['proxy_overlap']}")
        L.append("Row-order validity per file (Spearman row position vs timestamp; share of rows >60s / >600s behind running max):")
        for k, v in prep["row_order_validity"].items():
            L.append(f"  - {k}: rho={v['spearman_pos_vs_time']:.4f}, >60s={100*v['frac_rows_more_than_60s_behind_running_max']:.2f}%, "
                     f">600s={100*v['frac_rows_more_than_600s_behind_running_max']:.2f}%")
    names = sorted({r["split"] for r in runs}, key=lambda s: ["random", "flowid", "block1", "block5", "block15", "forward", "roworder"].index(s)
                   if s in ["random", "flowid", "block1", "block5", "block15", "forward", "roworder"] else 99)
    m4 = {"Mal-F1": lambda r: r["stage1"]["malicious_f1"],
          "Family GT": lambda r: r["stage2_family"]["gt_malicious"]["macro_f1"],
          "Family E2E": lambda r: r["stage2_family"]["end_to_end"]["macro_f1"],
          "Fine GT": lambda r: r["stage2_fine"]["gt_malicious"]["macro_f1"]}
    S4 = {n: {m: msd([f(r) for r in runs if r["split"] == n]) for m, f in m4.items()} for n in names}
    L.append("")
    L.append("| Split | " + " | ".join(m4) + " | Benign FPR (%) |")
    L.append("|---|" + "---|" * (len(m4) + 1))
    for n in names:
        fpr = msd([100 * r["stage1"]["benign_fpr"] for r in runs if r["split"] == n])
        L.append(f"| {n} | " + " | ".join(fmt(S4[n][m]) for m in m4) + f" | {fmt(fpr)} |")
    h("exp004 decomposition")
    L.append("| Comparison | Metric | Δ | Verdict |")
    L.append("|---|---|---|---|")
    pairs = [("random", "flowid", "session leakage (Flow ID grouping)")]
    pairs += [("random", f"block{w}", f"adjacency leakage ({w}-min blocks)") for w in (1, 5, 15)]
    pairs += [(f"block{w}", "forward", f"temporal drift (vs {w}-min blocks)") for w in (1, 5, 15)]
    pairs += [("forward", "roworder", "row-order proxy vs true time")]
    for a, b, label in pairs:
        if a in S4 and b in S4:
            for m in m4:
                d, v = effect(S4[a][m], S4[b][m])
                L.append(f"| {label}: {a} → {b} | {m} | {d} | {v} |")

out = os.path.join(EXPD, "REPORT_tables.md")
with open(out, "w", encoding="utf-8") as f:
    f.write("# Consolidated experiment tables (auto-generated by make_report.py)\n"
            f"\nNoise floor used for verdicts: {NOISE} (exp002 row-order model-seed SD of family GT macro-F1).\n"
            + "\n".join(L) + "\n")
print(open(out, encoding="utf-8").read())
