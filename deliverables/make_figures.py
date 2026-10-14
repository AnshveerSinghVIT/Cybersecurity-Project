"""
Builds every figure used in the report, the slide deck and the paper, and writes numbers.json, the
single source of truth for every number quoted in those documents. Reads saved experiment outputs
only (../experiments); trains nothing.

Output: figures/<name>.pdf (vector, for LaTeX) and figures/<name>.png (300 dpi, for Word/PowerPoint).
"""
import csv
import glob
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, "..", "experiments")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

# ---- palette (dataviz reference palette, light mode; validated: 3 slots all-pairs PASS)
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE_RAMP = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
MARKERS = ["o", "s", "^"]

plt.rcParams.update({
    "font.family": "Arial", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "savefig.dpi": 300, "pdf.fonttype": 42,
})

N = {}  # numbers.json


def j(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(os.path.join(FIG, name + ".png"), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def ms(v):
    v = np.asarray(v, dtype=float)
    return {"mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else None,
            "min": float(v.min()), "max": float(v.max()), "n": int(len(v))}


# =========================================================================== data
e2 = [j(f) for f in glob.glob(os.path.join(EXP, "exp002_seeds", "runs", "*.json"))]
e2_row = [r for r in e2 if r["scheme"] == "temporal"]
e2_rnd = [r for r in e2 if r["scheme"] == "random" and r["split_seed"] == 42]
prep2 = j(os.path.join(EXP, "exp002_seeds", "data_prep.json"))
e1 = j(os.path.join(EXP, "exp001_baseline", "multiclass_baseline_temporal.json"))

N["data_2017"] = {
    "rows_raw": e1["rows_raw"], "rows_after_nan_inf": e1["rows_after_nan_inf_drop"],
    "n_features": e1["n_features"], "unique_vectors": e1["duplicates"]["unique_feature_rows"],
    "duplicate_rate": e1["duplicates"]["duplicate_rate"],
    "conflicting_groups": e1["duplicates"]["conflicting_groups"],
    "rows_in_conflicting_groups": e1["duplicates"]["rows_in_conflicting_groups"],
    "conflict_rows_by_label": e1["duplicates"]["conflict_rows_by_raw_label"],
    "conflict_groups_by_label": prep2["conflicts_before_dedup"]["conflict_groups_by_label"],
    "largest_conflict_group_rows": prep2["conflicts_before_dedup"]["largest_conflict_group_rows"],
    "rows_after_dedup": e1["rows_after_dedup_and_conflict_drop"],
    "label_support_after_dedup": e1["label_support_after_dedup"],
    "fine_classes": e1["fine_classes"], "family_classes": e1["family_classes"],
    "split_rows": e1["split"],
}


def grp(runs):
    g = lambda f: ms([f(r) for r in runs])
    return {
        "mal_f1": g(lambda r: r["stage1"]["malicious_f1"]),
        "mal_precision": g(lambda r: r["stage1"]["malicious_precision"]),
        "mal_recall": g(lambda r: r["stage1"]["malicious_recall"]),
        "benign_fpr_pct": g(lambda r: 100 * r["stage1"]["benign_fpr"]),
        "fam_gt": g(lambda r: r["stage2_family"]["gt_malicious"]["macro_f1"]),
        "fam_e2e": g(lambda r: r["stage2_family"]["end_to_end"]["macro_f1"]),
        "fine_gt": g(lambda r: r["stage2_fine"]["gt_malicious"]["macro_f1"]),
        "fine_e2e": g(lambda r: r["stage2_fine"]["end_to_end"]["macro_f1"]),
    }


N["exp002"] = {"roworder_modelseed": grp(e2_row), "random_modelseed": grp(e2_rnd),
               "random_splitseed": grp([r for r in e2 if r["group"] == "random/split"])}
fams = ["DoS/DDoS", "PortScan", "Brute Force", "Web Attack", "Bot"]
N["exp002"]["hierarchy"] = {
    name: {c: {"gt_f1": ms([r["stage2_family"]["gt_malicious"]["per_class"][c]["f1"] for r in g])["mean"],
               "e2e_f1": ms([r["stage2_family"]["end_to_end"]["per_class"][c]["f1"] for r in g])["mean"],
               "e2e_precision": ms([r["stage2_family"]["end_to_end"]["per_class"][c]["precision"] for r in g])["mean"]}
           for c in fams}
    for name, g in (("roworder", e2_row), ("random", e2_rnd))}
fine_cls = ["Web Attack - Brute Force", "Web Attack - XSS", "DoS slowloris", "DoS Slowhttptest", "PortScan"]
N["exp002"]["fine_f1"] = {name: {c: ms([r["stage2_fine"]["gt_malicious"]["per_class"][c]["f1"] for r in g])
                                 for c in fine_cls} for name, g in (("roworder", e2_row), ("random", e2_rnd))}

# exp004
e4 = [j(f) for f in glob.glob(os.path.join(EXP, "exp004_leakage_vs_drift", "runs", "*.json"))]
prep4 = j(os.path.join(EXP, "exp004_leakage_vs_drift", "data_prep.json"))
SPLITS = ["random", "flowid", "block1", "block5", "block15", "forward", "roworder"]
SPLIT_LABEL = {"random": "Random", "flowid": "Flow-ID\ngrouped", "block1": "1-min\nblocks",
               "block5": "5-min\nblocks", "block15": "15-min\nblocks", "forward": "Chronological\n(timestamps)",
               "roworder": "Chronological\n(row order)"}
N["exp004"] = {s: grp([r for r in e4 if r["split"] == s]) for s in SPLITS}
cls4 = ["DoS Hulk", "DDoS", "DoS slowloris", "PortScan", "SSH-Patator", "FTP-Patator", "BENIGN"]
for s in SPLITS:
    N["exp004"][s]["recall_by_label"] = {c: ms([r["stage1"]["recall_by_raw_label"][c] for r in e4
                                                if r["split"] == s]) for c in cls4}
N["exp004"]["row_order_validity"] = prep4["row_order_validity"]
N["exp004"]["proxy_overlap"] = prep4["proxy_overlap"]
N["exp004"]["alignment"] = {k: v["row_match_rate"] for k, v in prep4["alignment_checks"].items()}
N["exp004"]["pm_corrected_rows"] = sum(v["pm_corrected"] for v in prep4["alignment_checks"].values())

# exp005
e5 = {os.path.basename(f)[:-5]: j(f) for f in glob.glob(os.path.join(EXP, "exp005_dedup_sensitivity", "runs", "*.json"))}
N["exp005"] = {}
for rid, r in e5.items():
    rec = {}
    for view in ("own_test", "common_test"):
        if view in r:
            v = r[view]
            rec[view] = {"n_test": v["n_test"], "mal_f1": v["stage1"]["malicious_f1"],
                         "benign_fpr_pct": 100 * v["stage1"]["benign_fpr"],
                         "fam_gt": v["stage2_family"]["gt_malicious"]["macro_f1"],
                         "fine_gt": v["stage2_fine"]["gt_malicious"]["macro_f1"],
                         "portscan_support": v["stage2_family"]["gt_malicious"]["per_class"].get("PortScan", {}).get("support")}
    rec["straddle"] = r.get("test_rows_with_exact_duplicate_in_train")
    N["exp005"][rid] = rec

# exp003 / exp007 / exp008
e3 = [j(f) for f in sorted(glob.glob(os.path.join(EXP, "exp003_cross_family", "run_seed*.json")))]
prep3 = j(os.path.join(EXP, "exp003_cross_family", "data_prep.json"))
N["exp003"] = {side: {
    "e2e": ms([r[side]["end_to_end"]["macro_f1"] for r in e3]),
    "mal_f1": ms([r[side]["stage1"]["malicious_f1"] for r in e3]),
    "stage2_gt": ms([r[side]["stage2_gt"]["macro_f1"] for r in e3]),
    "benign_fpr_pct": ms([100 * r[side]["stage1"]["benign_fpr"] for r in e3]),
    **{f"recall_{f}": ms([r[side]["per_family"][f]["e2e_recall"] for r in e3]) for f in ("DoS/DDoS", "Web Attack", "Benign")},
    **{f"s2gt_recall_{f}": ms([r[side]["per_family"][f]["stage2_gt_recall"] for r in e3]) for f in ("DoS/DDoS", "Web Attack")},
    "support": e3[0][side]["support"]} for side in ("reference", "cross")}
N["exp003"]["supports"] = {k: prep3[k] for k in ("train_support", "ref_test_support", "cross_test_support")}
N["exp003"]["conflicts_2018"] = prep3["conflicts_2018_before_dedup"]
N["exp003"]["load_2018"] = prep3["load_2018"]
cm42 = next(r for r in e3 if r["seed"] == 42)

e7 = [j(f) for f in glob.glob(os.path.join(EXP, "exp007_shift_mitigation", "runs", "*.json"))]
TR = ["none", "slog", "robust_domain", "quantile_domain", "drop_k10", "drop_k25"]
TR_LABEL = {"none": "None", "slog": "Signed\nlog", "robust_domain": "Robust\nscaling",
            "quantile_domain": "Quantile\nmapping", "drop_k10": "Drop 10\nfeatures", "drop_k25": "Drop 25\nfeatures"}
N["exp007"] = {}
for t in TR:
    for k in ("rf", "xgb"):
        rs = [r for r in e7 if r["direction"] == "2017->2018" and r["transform"] == t and r["model"] == k]
        N["exp007"][f"{t}_{k}"] = {"cross_e2e": ms([r["results"]["cross"]["end_to_end"]["macro_f1"] for r in rs]),
                                    "ref_e2e": ms([r["results"]["reference"]["end_to_end"]["macro_f1"] for r in rs]),
                                    "dos": ms([r["results"]["cross"]["per_family"]["DoS/DDoS"]["e2e_recall"] for r in rs]),
                                    "web": ms([r["results"]["cross"]["per_family"]["Web Attack"]["e2e_recall"] for r in rs]),
                                    "fpr_pct": ms([100 * r["results"]["cross"]["stage1"]["benign_fpr"] for r in rs])}
for k in ("rf", "xgb"):
    b, ref = N["exp007"][f"none_{k}"]["cross_e2e"]["mean"], N["exp007"][f"none_{k}"]["ref_e2e"]["mean"]
    for t in TR:
        N["exp007"][f"{t}_{k}"]["gap_recovered_pct"] = 100 * (N["exp007"][f"{t}_{k}"]["cross_e2e"]["mean"] - b) / (ref - b)
for name, cond in (("upper2018_rf", lambda r: r["direction"] == "2018->2018" and r["model"] == "rf"),
                   ("upper2018_xgb", lambda r: r["direction"] == "2018->2018" and r["model"] == "xgb"),
                   ("reverse_none_rf", lambda r: r["direction"] == "2018->2017" and r["transform"] == "none"),
                   ("reverse_quantile_rf", lambda r: r["direction"] == "2018->2017" and r["transform"] == "quantile_domain")):
    rs = [r for r in e7 if cond(r)]
    side = "test" if "test" in rs[0]["results"] else "cross"
    N["exp007"][name] = {"e2e": ms([r["results"][side]["end_to_end"]["macro_f1"] for r in rs]),
                         "dos": ms([r["results"][side]["per_family"]["DoS/DDoS"]["e2e_recall"] for r in rs]),
                         "web": ms([r["results"][side]["per_family"]["Web Attack"]["e2e_recall"] for r in rs]),
                         "fpr_pct": ms([100 * r["results"][side]["stage1"]["benign_fpr"] for r in rs]),
                         "test_support": rs[0].get("test_support")}
ks = j(os.path.join(EXP, "exp007_shift_mitigation", "ks_rank.json"))["ks_rank_2017train_vs_2018"]
N["exp007"]["ks_top10"] = ks[:10]
N["exp007"]["ks_rank_of_hulk_features"] = {f: [i + 1 for i, (n, _) in enumerate(ks) if n == f][0]
                                           for f in ("Init_Win_bytes_backward", "Bwd Packet Length Mean",
                                                     "Total Length of Bwd Packets", "Subflow Bwd Bytes")}

e8 = [j(f) for f in sorted(glob.glob(os.path.join(EXP, "exp008_cross_test_dedup", "runs", "*.json")))]
N["exp008"] = {p: {"n_test": e8[0]["results"][p]["n_test"],
                   "mal_f1": ms([r["results"][p]["stage1"]["malicious_f1"] for r in e8]),
                   "e2e": ms([r["results"][p]["end_to_end"]["macro_f1"] for r in e8]),
                   "dos": ms([r["results"][p]["per_family"]["DoS/DDoS"]["e2e_recall"] for r in e8]),
                   "slowhttp_recall_seed42": e8[0]["results"][p]["per_raw_label"]["DoS Slowhttptest"]["e2e_recall"],
                   "slowhttp_n": e8[0]["results"][p]["per_raw_label"]["DoS Slowhttptest"]["n"]}
               for p in ("drop_conflicts", "keep_first", "none")}

# exp006
s6 = j(os.path.join(EXP, "exp006_shift_diagnosis", "summary.json"))
N["exp006"] = {"unit_identities": s6["unit_identities"],
               "adversarial_auc": {k: v["holdout_auc"] for k, v in s6["adversarial_validation"].items()},
               "adversarial_top": {k: v["top_importances"][:5] for k, v in s6["adversarial_validation"].items()},
               "n_ks_gt_05": s6["n_features_ks_gt_0.5"], "top_hulk": s6["feature_shift_top10_dos_hulk"],
               "top_benign": s6["feature_shift_top10_benign"],
               "dup2018": {k: {kk: v[kk] for kk in ("rows", "unique_vectors", "duplicate_share")} | {
                   "top_share": v["top_vectors"][0]["share_of_label"]} for k, v in s6["duplication_2018"].items()},
               "dup2017": {k: {kk: v[kk] for kk in ("rows", "unique_vectors", "duplicate_share")}
                           for k, v in s6["duplication_2017"].items()}}


def read_csv(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


shift_h = read_csv(os.path.join(EXP, "exp006_shift_diagnosis", "feature_shift_dos_hulk.csv"))
shift_b = {r["feature"]: r for r in read_csv(os.path.join(EXP, "exp006_shift_diagnosis", "feature_shift_benign.csv"))}
N["exp006"]["hulk_bwd_zero_share"] = {r["feature"]: [float(r["zero_share_2017"]), float(r["zero_share_2018"])]
                                      for r in shift_h if r["feature"] in ("Total Length of Bwd Packets", "Bwd Packet Length Max")}

# exp002: share of benign false positives that Stage 2 assigns to DDoS, recovered from per-class
# precision (predicted-DDoS flows that are not DDoS = TP/precision - TP)
def ddos_fp_share(r):
    d = r["stage2_fine"]["end_to_end"]["per_class"]["DDoS"]
    tp = d["recall"] * d["support"]
    return (tp / d["precision"] - tp) / r["stage1"]["benign_false_positives"]


N["exp002"]["ddos_fp_share"] = {"roworder": ms([ddos_fp_share(r) for r in e2_row]),
                                "random": ms([ddos_fp_share(r) for r in e2 if r["scheme"] == "random"])}

# exp004: which attacks the chronological split misses
N["exp004"]["forward_missed"] = {}
for r in e4:
    if r["split"] != "forward":
        continue
    miss = {k: int(round((1 - v) * r["test_support"][k])) for k, v in r["stage1"]["recall_by_raw_label"].items()
            if k != "BENIGN"}
    N["exp004"]["forward_missed"][f"seed{r['seed']}"] = {"total": sum(miss.values()), "by_label": miss,
                                                         "hulk_share": miss["DoS Hulk"] / sum(miss.values())}

# exp009: time composition of the per-class chronological split; global-cutoff feasibility
s9 = j(os.path.join(EXP, "exp009_split_composition", "summary.json"))
o9 = s9["ordering"]
N["exp009"] = {
    "train_rows": s9["train_rows"], "test_rows": s9["test_rows"],
    "test_with_later_train_frac": o9["test_flows_with_any_later_training_flow_frac"],
    "mean_frac_train_later": o9["mean_frac_of_training_flows_later_than_test_flow"],
    "benign_test_window": o9["benign_test_window"],
    "attack_train_in_benign_test_window": o9["attack_training_flows_at_or_after_benign_test_start"],
    "attack_train_total": o9["attack_training_flows_total"],
    "attack_train_in_window_by_class": o9["attack_training_flows_after_benign_test_start_by_class"],
    "windows": {c: {"train": [v["train"]["t_min"], v["train"]["t_max"]], "test": [v["test"]["t_min"], v["test"]["t_max"]]}
                for c, v in s9["per_class"].items()},
    "global_cutoff": {k: {"cutoff": v["cutoff"], "train_frac": v["train_frac"],
                          "both": len(v["attack_classes_both_sides"]), "both_names": v["attack_classes_both_sides"],
                          "train_only": len(v["attack_classes_train_only"]),
                          "test_only": len(v["attack_classes_test_only"]),
                          "test_only_names": v["attack_classes_test_only"]} for k, v in s9["global_cutoff"].items()},
}

# exp010: endpoint audit of benign false positives (seed 42; both protocols reproduce exp004 exactly)
s10 = j(os.path.join(EXP, "exp010_forward_fp_forensics", "summary.json"))
N["exp010"] = {"ddos_interval": s10["ddos_label_interval"], "ddos_rows_src_dst": s10["all_ddos_rows_src_dst"]}
for side in ("forward", "random"):
    o = s10[side]
    N["exp010"][side] = {k: o[k] for k in (
        "benign_test_flows", "benign_fp", "fp_by_predicted_fine", "benign_on_ddos_pair", "benign_on_bot_cc",
        "fp_on_ddos_pair", "fp_on_ddos_pair_pred_ddos", "fp_on_bot_cc", "fp_on_bot_cc_pred_bot",
        "stage1_all", "stage1_excl_ddos_pair_benign", "stage1_excl_both_benign")}
    N["exp010"][side]["fp_other"] = o["benign_fp"] - o["fp_on_ddos_pair"] - o["fp_on_bot_cc"]
f10 = s10["forward"]
N["exp010"]["forward"].update({k: f10[k] for k in (
    "benign_on_ddos_pair_in_ddos_interval", "fp_to_ddos_in_ddos_interval", "benign_fpr_inside_ddos_interval",
    "benign_fpr_outside_ddos_interval", "fp_to_ddos_dst_port_ge_1024_frac", "true_ddos_test_dst_port_eq_80_frac",
    "fp_to_bot_by_hour", "true_bot_test_window", "fp_to_ddos_top_src_dst", "fp_to_bot_top_src_dst")})
fw, rn = N["exp010"]["forward"], N["exp010"]["random"]
N["exp010"]["endpoint_fp_share_forward"] = (fw["fp_on_ddos_pair"] + fw["fp_on_bot_cc"]) / fw["benign_fp"]
N["exp010"]["f1_gap_all"] = rn["stage1_all"]["f1"] - fw["stage1_all"]["f1"]
N["exp010"]["f1_gap_excl"] = rn["stage1_excl_both_benign"]["f1"] - fw["stage1_excl_both_benign"]["f1"]

with open(os.path.join(HERE, "numbers.json"), "w", encoding="utf-8") as f:
    json.dump(N, f, indent=2)

# =========================================================================== figures
COL = 3.5   # IEEE single column (in)
DCOL = 7.16


def dotplot(ax, cats, series, ylim, ylabel, offsets=None):
    x = np.arange(len(cats))
    k = len(series)
    offsets = offsets or np.linspace(-0.16, 0.16, k) if k > 1 else [0]
    for i, (lab, vals, lo, hi) in enumerate(series):
        xi = x + offsets[i]
        ax.vlines(xi, lo, hi, color=[S1, S2, S3][i], lw=1.4)
        ax.plot(xi, vals, MARKERS[i], color=[S1, S2, S3][i], ms=5, mec="white", mew=0.8, label=lab, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)


# F1: split comparison (exp004)
fig, ax = plt.subplots(figsize=(DCOL, 2.3))
cats = [SPLIT_LABEL[s] for s in SPLITS]
ser = []
for lab, key in (("Stage-1 malicious F1", "mal_f1"), ("Stage-2 family macro-F1 (true attacks)", "fam_gt"),
                 ("End-to-end family macro-F1", "fam_e2e")):
    v = [N["exp004"][s][key] for s in SPLITS]
    ser.append((lab, [d["mean"] for d in v], [d["min"] for d in v], [d["max"] for d in v]))
dotplot(ax, cats, ser, (0.74, 1.005), "Score")
ax.axvspan(4.5, 6.5, color="#f0efec", zorder=0, lw=0)
ax.text(1.95, 0.755, "random and grouped splits (training and test periods interleaved)", ha="center",
        color=INK2, fontsize=7.5)
ax.text(5.5, 0.755, "per-class chronological", ha="center", color=INK2, fontsize=7.5)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3)
save(fig, "fig_splits")

# F2: precision / recall / FPR decomposition (exp004)
fig, axes = plt.subplots(1, 2, figsize=(COL, 2.0), gridspec_kw={"width_ratios": [1.15, 1]})
sp = ["random", "block5", "forward"]
labs = ["Random", "5-min\nblocks", "Chrono-\nlogical"]
ser = [(lab, [N["exp004"][s][key]["mean"] for s in sp], [N["exp004"][s][key]["min"] for s in sp],
        [N["exp004"][s][key]["max"] for s in sp]) for lab, key in (("Precision", "mal_precision"), ("Recall", "mal_recall"))]
dotplot(axes[0], labs, ser, (0.84, 1.005), "Stage-1 (malicious)")
axes[0].legend(loc="lower left")
fpr = [N["exp004"][s]["benign_fpr_pct"]["mean"] for s in sp]
axes[1].bar(np.arange(3), fpr, width=0.45, color=S1)
for i, v in enumerate(fpr):
    axes[1].text(i, v + 0.06, f"{v:.2f}%", ha="center", fontsize=7.5, color=INK)
axes[1].set_xticks(np.arange(3))
axes[1].set_xticklabels(labs, fontsize=6.8)
axes[1].set_ylabel("Benign false-positive rate (%)")
axes[1].set_ylim(0, 3.4)
axes[1].grid(axis="x", visible=False)
fig.tight_layout(w_pad=1.2)
save(fig, "fig_decomp")

# F2b: composition of benign false positives and FPR after the endpoint exclusion (exp010)
fig, axes = plt.subplots(1, 2, figsize=(COL, 2.25), gridspec_kw={"width_ratios": [1.25, 1]})
E10 = N["exp010"]
sides = (("random", "Random"), ("forward", "Chrono-\nlogical"))
segs = (("fp_other", "Other benign flows", S1), ("fp_on_bot_cc", "Bot C&C channel", S3),
        ("fp_on_ddos_pair", "DDoS attacker–victim pair", S2))
ax = axes[0]
for i, (side, _) in enumerate(sides):
    n = E10[side]["benign_test_flows"]
    bottom = 0.0
    for key, lab, col in segs:
        v = 100 * E10[side][key] / n
        ax.bar(i, v, bottom=bottom, width=0.5, color=col, edgecolor="white", linewidth=0.6,
               label=lab if i == 1 else None)
        bottom += v
    ax.text(i, bottom + 0.06, f"{bottom:.3f}%" if bottom < 0.1 else f"{bottom:.2f}%", ha="center", fontsize=7.2)
ax.set_xticks([0, 1])
ax.set_xticklabels([l for _, l in sides])
ax.set_xlim(-0.6, 1.6)
ax.set_ylim(0, 3.3)
ax.set_ylabel("Benign false-positive rate (%)")
ax.set_title("(a) All benign test flows", loc="left", fontsize=7.5)
ax.grid(axis="x", visible=False)
ax = axes[1]
for i, (side, _) in enumerate(sides):
    d = E10[side]["stage1_excl_both_benign"]
    lo, hi = 100 * d["fpr_ci95"][0], 100 * d["fpr_ci95"][1]
    ax.vlines(i, lo, hi, color=INK2, lw=1.4)
    ax.plot(i, 100 * d["fpr"], "o", color=INK, ms=5, mec="white", mew=0.8, zorder=3)
    ax.text(i, hi + 0.003, f"{100 * d['fpr']:.3f}%", ha="center", fontsize=7.2)
ax.set_xticks([0, 1])
ax.set_xticklabels([l for _, l in sides])
ax.set_xlim(-0.6, 1.6)
ax.set_ylim(0, 0.06)
ax.set_yticks([0, 0.02, 0.04, 0.06])
ax.set_title("(b) Endpoint sets excluded", loc="left", fontsize=7.5)
ax.set_ylabel("Benign FPR (%)")
ax.grid(axis="x", visible=False)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h[::-1], l[::-1], loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=3, fontsize=6.5,
           handlelength=1.0, columnspacing=0.9)
fig.tight_layout(w_pad=1.0, rect=(0, 0.07, 1, 1))
save(fig, "fig_fp")

# F3: per-class recall (exp004)
fig, ax = plt.subplots(figsize=(COL, 2.1))
cl = ["DoS Hulk", "DDoS", "DoS slowloris", "PortScan", "SSH-Patator", "FTP-Patator"]
cl_lab = ["DoS\nHulk", "DDoS", "DoS\nslowloris", "PortScan", "SSH-\nPatator", "FTP-\nPatator"]
ser = [(lab, [N["exp004"][s]["recall_by_label"][c]["mean"] for c in cl],
        [N["exp004"][s]["recall_by_label"][c]["min"] for c in cl],
        [N["exp004"][s]["recall_by_label"][c]["max"] for c in cl]) for lab, s in
       (("Random", "random"), ("5-min blocks", "block5"), ("Chronological", "forward"))]
dotplot(ax, cl_lab, ser, (0.7, 1.01), "Stage-1 recall", offsets=[-0.22, 0, 0.22])
ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
save(fig, "fig_class_recall")

# F4: duplication by label (exp006)
fig, axes = plt.subplots(1, 2, figsize=(DCOL, 2.2), gridspec_kw={"width_ratios": [1.35, 1]})
for ax, key, title in ((axes[0], "dup2017", "CICIDS2017"), (axes[1], "dup2018", "CSE-CIC-IDS2018 (two days)")):
    d = sorted(N["exp006"][key].items(), key=lambda t: t[1]["duplicate_share"])
    y = np.arange(len(d))
    ax.barh(y, [100 * v["duplicate_share"] for _, v in d], height=0.55, color=S1)
    ax.set_yticks(y)
    ax.set_yticklabels([k.replace("Web Attack - ", "Web ").replace("Sql Injection", "SQLi") for k, _ in d], fontsize=7)
    for yi, (_, v) in zip(y, d):
        ax.text(100 * v["duplicate_share"] + 1.5, yi, f"{100 * v['duplicate_share']:.1f}%  ({v['rows']:,} rows)",
                va="center", fontsize=6.5, color=INK2)
    ax.set_xlim(0, 135)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Exact-duplicate share of rows (%)")
    ax.set_title(title, loc="left", color=INK)
    ax.grid(axis="y", visible=False)
fig.tight_layout(w_pad=2)
save(fig, "fig_duplication")

# F5: hierarchy error propagation (exp002)
fig, axes = plt.subplots(1, 2, figsize=(COL, 2.25), sharey=True)
order = ["DoS/DDoS", "Brute Force", "Web Attack", "PortScan", "Bot"]
for ax, name, title in ((axes[0], "random", "Random split"), (axes[1], "roworder", "Chronological split")):
    h = N["exp002"]["hierarchy"][name]
    y = np.arange(len(order))
    for yi, c in zip(y, order):
        ax.plot([h[c]["e2e_f1"], h[c]["gt_f1"]], [yi, yi], color=AXIS, lw=1.6, zorder=1)
    ax.plot([h[c]["gt_f1"] for c in order], y, "o", color=S1, ms=5, mec="white", label="True attacks only", zorder=3)
    ax.plot([h[c]["e2e_f1"] for c in order], y, "s", color=S2, ms=5, mec="white", label="End-to-end", zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(order)
    ax.set_xlim(0.2, 1.06)
    ax.set_xticks([0.25, 0.5, 0.75, 1.0])
    ax.set_title(title, loc="left")
    ax.set_xlabel("Family F1")
    ax.grid(axis="y", visible=False)
axes[0].invert_yaxis()
fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(0.55, -0.04), ncol=2)
fig.tight_layout(w_pad=0.8, rect=(0, 0.07, 1, 1))
save(fig, "fig_hierarchy")

# F6: cross-dataset recall (exp003 + exp007)
fig, ax = plt.subplots(figsize=(COL, 2.1))
groups = ["DoS/DDoS recall", "Web Attack recall", "End-to-end\nmacro-F1"]
vals = {
    "Train 2017, test 2017": [N["exp003"]["reference"]["recall_DoS/DDoS"]["mean"],
                              N["exp003"]["reference"]["recall_Web Attack"]["mean"], N["exp003"]["reference"]["e2e"]["mean"]],
    "Train 2017, test 2018": [N["exp003"]["cross"]["recall_DoS/DDoS"]["mean"],
                              N["exp003"]["cross"]["recall_Web Attack"]["mean"], N["exp003"]["cross"]["e2e"]["mean"]],
    "Train 2018, test 2018": [N["exp007"]["upper2018_rf"]["dos"]["mean"], N["exp007"]["upper2018_rf"]["web"]["mean"],
                              N["exp007"]["upper2018_rf"]["e2e"]["mean"]],
}
x = np.arange(len(groups))
w = 0.24
for i, (lab, v) in enumerate(vals.items()):
    ax.bar(x + (i - 1) * (w + 0.02), v, width=w, color=[S1, S2, S3][i], label=lab)
    for xi, vi in zip(x + (i - 1) * (w + 0.02), v):
        ax.text(xi, vi + 0.02, f"{vi:.2f}" if vi >= 0.005 else f"{vi:.3f}", ha="center", fontsize=6.3, color=INK)
ax.set_xticks(x)
ax.set_xticklabels(groups)
ax.set_ylim(0, 1.18)
ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.grid(axis="x", visible=False)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=3, fontsize=6.6, handlelength=1.2, columnspacing=0.8)
save(fig, "fig_cross")

# F7: confusion matrices reference vs cross (exp003, seed 42)
fig, axes = plt.subplots(1, 2, figsize=(COL, 1.75))
labs = ["Benign", "DoS", "Web"]
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
for ax, side, title in ((axes[0], "reference", "Train 2017, test 2017"), (axes[1], "cross", "Train 2017, test 2018")):
    cm = np.asarray(cm42[side]["confusion_e2e"]["counts"], dtype=float)
    nm = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(nm, cmap=cmap, vmin=0, vmax=1)
    for i in range(3):
        for k in range(3):
            ax.text(k, i, f"{nm[i, k]:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if nm[i, k] > 0.55 else INK)
    ax.set_xticks(range(3))
    ax.set_xticklabels(labs, fontsize=6.8)
    ax.set_yticks(range(3))
    ax.set_yticklabels(labs, fontsize=6.8)
    ax.set_xlabel("Predicted", fontsize=7)
    ax.set_title(title, fontsize=7.5)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
axes[0].set_ylabel("True family", fontsize=7)
fig.tight_layout(w_pad=1.0)
save(fig, "fig_confusion")

# F8: feature shift KS (exp006)
fig, ax = plt.subplots(figsize=(COL, 2.9))
rows = shift_h[:14]
y = np.arange(len(rows))
ax.plot([float(r["ks"]) for r in rows], y, "o", color=S1, ms=4.5, mec="white", label="DoS Hulk, 2017 vs 2018")
ax.plot([float(shift_b[r["feature"]]["ks"]) for r in rows], y, "s", color=S2, ms=4.5, mec="white",
        label="Benign, 2017 vs 2018")
ax.set_yticks(y)
ax.set_yticklabels([r["feature"] for r in rows], fontsize=6.8)
ax.invert_yaxis()
ax.set_xlim(0, 1)
ax.set_xlabel("Two-sample Kolmogorov-Smirnov statistic")
ax.axvline(0.5, color=AXIS, lw=0.8)
ax.grid(axis="y", visible=False)
ax.legend(loc="lower center", bbox_to_anchor=(0.35, 1.0), ncol=2, fontsize=7)
save(fig, "fig_shift")

# F9: mitigation (exp007)
fig, ax = plt.subplots(figsize=(COL, 2.2))
x = np.arange(len(TR))
rf = [N["exp007"][f"{t}_rf"]["cross_e2e"] for t in TR]
xg = [N["exp007"][f"{t}_xgb"]["cross_e2e"]["mean"] for t in TR]
ax.vlines(x - 0.1, [d["min"] for d in rf], [d["max"] for d in rf], color=S1, lw=1.4)
ax.plot(x - 0.1, [d["mean"] for d in rf], "o", color=S1, ms=5, mec="white", label="Random forest (3 seeds)")
ax.plot(x + 0.1, xg, "s", color=S2, ms=5, mec="white", label="XGBoost (1 seed)")
ref = N["exp003"]["reference"]["e2e"]["mean"]
up = N["exp007"]["upper2018_rf"]["e2e"]["mean"]
ax.axhline(ref, color=INK2, lw=0.8)
ax.text(5.45, ref - 0.06, f"same-year reference: 2017 {ref:.3f}, 2018 {up:.3f}", ha="right", fontsize=6.6, color=INK2)
ax.set_xticks(x)
ax.set_xticklabels([TR_LABEL[t] for t in TR], fontsize=6.8)
ax.set_ylim(0, 1.02)
ax.set_ylabel("End-to-end macro-F1 on 2018")
ax.grid(axis="x", visible=False)
ax.legend(loc="center left", bbox_to_anchor=(0, 0.62))
save(fig, "fig_mitigation")

# F10: architecture (layered, not a flowchart)
fig, ax = plt.subplots(figsize=(DCOL, 3.75))
ax.set_xlim(0, 100)
ax.set_ylim(4, 99)
ax.axis("off")
layers = [
    ("Data layer", ["CICIDS2017 flow records\n(8 capture files, 2.83 M flows)",
                    "CICIDS2017 labelled flows\n(timestamps, Flow ID)",
                    "CSE-CIC-IDS2018 flow records\n(2 capture days, 2.10 M flows)"]),
    ("Canonicalisation", ["Label canonicalisation\n& family taxonomy",
                          "Feature alignment\n(75 shared statistics)",
                          "Invalid-value removal\n(NaN, ±Inf)"]),
    ("Integrity audit", ["Feature-vector hashing\n& duplicate census",
                         "Label-conflict detection\n& resolution policies",
                         "Endpoint and timing audit\nof false positives"]),
    ("Evaluation protocols", ["Random &\nFlow-ID grouped splits",
                              "Time-block grouped splits\n(1, 5, 15 min)",
                              "Per-class chronological split\n& cross-dataset transfer"]),
    ("Hierarchical detector", ["Stage 1: benign vs malicious\n(random forest / XGBoost)",
                               "Stage 2: attack family\n& fine-grained type",
                               "Scoring views: true attacks,\nflagged flows, end-to-end"]),
    ("Statistical analysis", ["Seed noise floor &\nWilson intervals",
                              "Shift diagnosis: identities,\nKS, adversarial validation",
                              "Label-free shift\nmitigation"]),
]
ytop, h, gap = 97, 13.2, 3.0
for i, (name, boxes) in enumerate(layers):
    y = ytop - (i + 1) * h - i * gap + gap
    ax.add_patch(FancyBboxPatch((0.5, y), 99, h, boxstyle="round,pad=0,rounding_size=1.2",
                                fc="#f4f7fc" if i % 2 == 0 else "#fbfbfa", ec=GRID, lw=0.8))
    ax.text(2.0, y + h / 2, name, va="center", ha="left", fontsize=8, fontweight="bold", color=INK)
    for k, b in enumerate(boxes):
        bx = 25.5 + k * 24.8
        ax.add_patch(FancyBboxPatch((bx, y + 1.6), 23.4, h - 3.2, boxstyle="round,pad=0,rounding_size=1.0",
                                    fc="white", ec=S1 if i in (2, 3) else AXIS, lw=0.9))
        ax.text(bx + 11.7, y + h / 2, b, va="center", ha="center", fontsize=6.5, color=INK, linespacing=1.25)
save(fig, "fig_architecture")

# F11: Gantt (project plan)
import datetime as _dt
import matplotlib.dates as mdates
D = lambda m, d: _dt.date(2026, m, d)
tasks = [("Literature survey and problem definition", D(7, 13), D(8, 14)),
         ("Dataset acquisition and flow-feature baseline", D(8, 3), D(8, 21)),
         ("Cross-dataset transfer and evasion baseline (Review II)", D(8, 17), D(8, 28)),
         ("Leakage-aware evaluation framework design", D(9, 1), D(9, 30)),
         ("Split, duplication and label-conflict experiments", D(9, 21), D(10, 14)),
         ("Shift diagnosis and label-free mitigation", D(10, 5), D(10, 14)),
         ("Report, paper and final review", D(10, 7), D(10, 16))]
fig, ax = plt.subplots(figsize=(DCOL, 2.3))
for i, (t, a, b) in enumerate(tasks):
    ax.barh(i, (b - a).days, left=mdates.date2num(a), height=0.5, color=S1)
ax.set_yticks(range(len(tasks)))
ax.set_yticklabels([t for t, _, _ in tasks], fontsize=7)
ax.invert_yaxis()
ax.xaxis_date()
ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_xlim(mdates.date2num(D(7, 13)), mdates.date2num(D(10, 19)))
ax.tick_params(axis="x", labelsize=7)
ax.grid(axis="y", visible=False)
save(fig, "fig_gantt")

print("figures:", sorted(f for f in os.listdir(FIG) if f.endswith(".png")))
print("numbers.json written")
