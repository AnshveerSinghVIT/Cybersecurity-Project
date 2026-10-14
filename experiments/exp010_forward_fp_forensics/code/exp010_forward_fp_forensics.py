"""
exp010: where do the benign false positives of the per-class forward split come from?

Re-fits the exp004 forward-split and random-split configurations (seed 42, 100 trees,
drop_conflicts) with the same code, checks that both reproduce exp004's stored counts exactly,
then keeps the predictions for benign test flows and reports their timing and endpoints. No
configuration is changed; this only recovers predictions that exp004 did not store.

Endpoint sets examined (identified from the forward-split false positives, then applied
identically to both splits):
  ddos_pair - flows between the DDoS victim 192.168.10.50 and the attacker address 172.16.0.1
  bot_cc    - flows to or from the Bot C&C address 205.174.165.73 on port 8080

Usage: python exp010_forward_fp_forensics.py
"""
import glob
import json
import os
import time
import zipfile

import numpy as np
import pandas as pd

import ids_common as C
from exp004_leakage_vs_drift import LAB_DIR, load_meta, split_forward

EXP = os.path.join(C.HERE, "experiments", "exp010_forward_fp_forensics")
REF = os.path.join(C.HERE, "experiments", "exp004_leakage_vs_drift", "runs", "{}_seed42.json")
SEED, TREES = 42, 100


def load_endpoints():
    """Source IP, Destination IP, Destination Port from the labelled release, same row positions
    as load_meta (row alignment was verified there)."""
    ml_paths = sorted(glob.glob(os.path.join(C.HERE, "cicids2017", "*.csv")), key=C.day_rank)
    frames = []
    for p in ml_paths:
        with zipfile.ZipFile(os.path.join(LAB_DIR, os.path.basename(p) + ".zip")) as z:
            with z.open(z.namelist()[0]) as f:
                lab = pd.read_csv(f, encoding="latin-1", low_memory=False,
                                  usecols=lambda c: c.strip() in ("Source IP", "Destination IP",
                                                                  "Destination Port", "Label"))
        lab.columns = lab.columns.str.strip()
        lab = lab.dropna(how="all").reset_index(drop=True)
        frames.append(lab[["Source IP", "Destination IP", "Destination Port"]].astype(str).astype("category"))
    return pd.concat(frames, ignore_index=True)


def top(e, mask, cols, k=8):
    vc = e.loc[mask, cols].astype(str).value_counts().head(k)
    return [{"key": list(i) if isinstance(i, tuple) else i, "n": int(n)} for i, n in vc.items()]


def stage1(yb, s1, mask):
    tp = int(((yb == 1) & (s1 == 1) & mask).sum())
    fp = int(((yb == 0) & (s1 == 1) & mask).sum())
    fn = int(((yb == 1) & (s1 == 0) & mask).sum())
    nb = int(((yb == 0) & mask).sum())
    p, r = tp / (tp + fp), tp / (tp + fn)
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r), "fpr": fp / nb,
            "benign_n": nb, "benign_fp": fp, "fpr_ci95": C.wilson_ci(fp, nb)}


def analyse(name, df, tr, te, feats, ep, ddos_iv):
    keep = feats + ["label_raw", "fine", "binary", "ts", "_pos"]
    train, test = df.loc[tr, keep], df.loc[te, keep].reset_index(drop=True)
    models = C.fit_hierarchy(train, feats, SEED, TREES, levels=("fine",))
    del train
    X = test[feats].values
    s1 = models["stage1"].predict(X)
    e2e = np.where(s1 == 1, models["fine"].predict(X), "Benign")
    del models, X

    yb = test["binary"].values
    ben = yb == 0
    fp = ben & (s1 == 1)
    ref = json.load(open(REF.format(name), encoding="utf-8"))
    cm = ref["stage2_fine"]["end_to_end"]["confusion"]
    ref_row = dict(zip(cm["labels"], cm["counts"][[l.lower() for l in cm["labels"]].index("benign")]))
    got_row = pd.Series(e2e[ben]).value_counts().to_dict()
    repro = {"benign_fp": [int(fp.sum()), ref["stage1"]["benign_false_positives"]],
             "benign_row_fine": [{k: int(v) for k, v in got_row.items() if k != "Benign"},
                                 {k: int(v) for k, v in ref_row.items() if v and k.lower() != "benign"}]}
    print(name, "reproduction (got, exp004):", repro, flush=True)
    if repro["benign_fp"][0] != repro["benign_fp"][1] or repro["benign_row_fine"][0] != repro["benign_row_fine"][1]:
        raise SystemExit(f"{name}: does not reproduce exp004 - stopping")

    e = ep.iloc[test["_pos"].values].reset_index(drop=True)
    src, dst = e["Source IP"].astype(str).values, e["Destination IP"].astype(str).values
    dport = pd.to_numeric(e["Destination Port"].astype(str), errors="coerce").values
    ddos_pair = (((src == "192.168.10.50") & (dst == "172.16.0.1"))
                 | ((src == "172.16.0.1") & (dst == "192.168.10.50")))
    bot_cc = ((src == "205.174.165.73") | (dst == "205.174.165.73")) & (dport == 8080)
    ts = test["ts"]
    in_iv = ((ts >= ddos_iv[0]) & (ts <= ddos_iv[1])).values

    out = {"reproduction": repro, "test_rows": int(len(test)), "benign_test_flows": int(ben.sum()),
           "benign_fp": int(fp.sum()),
           "fp_by_predicted_fine": {k: int(v) for k, v in pd.Series(e2e[fp]).value_counts().items()},
           "benign_on_ddos_pair": int((ben & ddos_pair).sum()),
           "benign_on_ddos_pair_in_ddos_interval": int((ben & ddos_pair & in_iv).sum()),
           "benign_on_bot_cc": int((ben & bot_cc).sum()),
           "fp_on_ddos_pair": int((fp & ddos_pair).sum()),
           "fp_on_ddos_pair_pred_ddos": int((fp & ddos_pair & (e2e == "DDoS")).sum()),
           "fp_on_bot_cc": int((fp & bot_cc).sum()),
           "fp_on_bot_cc_pred_bot": int((fp & bot_cc & (e2e == "Bot")).sum()),
           "malicious_on_ddos_pair_by_label": test.loc[(yb == 1) & ddos_pair, "label_raw"].value_counts().to_dict(),
           "malicious_on_bot_cc_by_label": test.loc[(yb == 1) & bot_cc, "label_raw"].value_counts().to_dict()}
    excl_ddos = ~(ben & ddos_pair)
    excl_both = ~(ben & (ddos_pair | bot_cc))
    out["stage1_all"] = stage1(yb, s1, np.ones(len(test), dtype=bool))
    out["stage1_excl_ddos_pair_benign"] = stage1(yb, s1, excl_ddos)
    out["stage1_excl_both_benign"] = stage1(yb, s1, excl_both)

    if name == "forward":
        fp_ddos = fp & (e2e == "DDoS")
        out["fp_to_ddos_by_hour"] = {str(k): int(v) for k, v in
                                     ts[fp_ddos].dt.floor("h").value_counts().sort_index().items()}
        out["fp_to_ddos_in_ddos_interval"] = int((fp_ddos & in_iv).sum())
        out["benign_fpr_inside_ddos_interval"] = float(fp[ben & in_iv].mean())
        out["benign_fpr_outside_ddos_interval"] = float(fp[ben & ~in_iv].mean())
        out["fp_to_ddos_top_src_dst"] = top(e, fp_ddos, ["Source IP", "Destination IP"])
        out["fp_to_ddos_dst_port_ge_1024_frac"] = float((dport[fp_ddos] >= 1024).mean())
        ddos_te = test["label_raw"].values == "DDoS"
        out["true_ddos_test_top_src_dst"] = top(e, ddos_te, ["Source IP", "Destination IP"])
        out["true_ddos_test_dst_port_eq_80_frac"] = float((dport[ddos_te] == 80).mean())
        fp_bot = fp & (e2e == "Bot")
        out["fp_to_bot_top_src_dst"] = top(e, fp_bot, ["Source IP", "Destination IP"], 6)
        out["fp_to_bot_top_dst_port"] = top(e, fp_bot, ["Destination Port"], 3)
        out["fp_to_bot_by_hour"] = {str(k): int(v) for k, v in
                                    ts[fp_bot].dt.floor("h").value_counts().sort_index().items()}
        bot_te = test["label_raw"].values == "Bot"
        out["true_bot_test_top_src_dst"] = top(e, bot_te, ["Source IP", "Destination IP"], 6)
        out["true_bot_test_top_dst_port"] = top(e, bot_te, ["Destination Port"], 3)
        out["true_bot_test_window"] = [str(ts[bot_te].min()), str(ts[bot_te].max())]
        out["benign_test_top_src_dst"] = top(e, ben, ["Source IP", "Destination IP"])
    return out


def main():
    os.makedirs(EXP, exist_ok=True)
    t0 = time.time()
    df, feats, info = C.load_2017()
    meta, _ = load_meta(info)
    df = C.apply_dedup(df, "drop_conflicts")
    C.add_taxonomies(df, min_support=500)
    df = df.sort_values("_pos").reset_index(drop=True)
    df["ts"] = meta.loc[df["_pos"].values, "ts"].values
    del meta
    df = df.drop(columns=["Label"])
    df = df[df["ts"].notna()].reset_index(drop=True)
    ep = load_endpoints()

    d = df["ts"][df["label_raw"] == "DDoS"]
    ddos_iv = (d.min(), d.max())
    all_ddos = df["label_raw"].values == "DDoS"
    src = ep["Source IP"].astype(str).values[df["_pos"].values]
    dst = ep["Destination IP"].astype(str).values[df["_pos"].values]
    out = {"ddos_label_interval": [str(ddos_iv[0]), str(ddos_iv[1])],
           "all_ddos_rows_src_dst": pd.Series(src[all_ddos] + ">" + dst[all_ddos]).value_counts().head(3).to_dict()}
    del src, dst

    splits = {"forward": split_forward(df), "random": C.make_split(df, "random", seed=SEED)}
    for name, (tr, te) in splits.items():
        out[name] = analyse(name, df, tr, te, feats, ep, ddos_iv)
        json.dump(out, open(os.path.join(EXP, "summary.json"), "w", encoding="utf-8"), indent=2, default=str)

    for name in splits:
        o = out[name]
        print(name, {k: o[k] for k in ("benign_fp", "benign_on_ddos_pair", "benign_on_bot_cc",
                                       "fp_on_ddos_pair", "fp_on_bot_cc")})
        for k in ("stage1_all", "stage1_excl_ddos_pair_benign", "stage1_excl_both_benign"):
            print("  ", k, {a: round(b, 5) if isinstance(b, float) else b for a, b in o[k].items()})
    code = C.snapshot_code(EXP, ["exp010_forward_fp_forensics.py", "exp004_leakage_vs_drift.py", "ids_common.py"])
    C.write_manifest(EXP, experiment_id="exp010_forward_fp_forensics", depends_on=["exp004_leakage_vs_drift"],
                     description="Timing and endpoints of benign false positives under the per-class forward and "
                                 "random splits (re-fits of exp004 seed 42, reproduction-checked)",
                     scripts=code, cmd="python exp010_forward_fp_forensics.py", seeds=[SEED],
                     dedup_policy="drop_conflicts", runtime_sec=round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
