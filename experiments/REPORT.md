# Consolidated experiment report — 2026-10-14 (v2, all queued experiments complete)

Basis: saved artifacts only (run JSONs, data_prep.json, MANIFEST.json, queue_status*.json, logs).
Generated tables: `REPORT_tables.md` (`make_report.py`). Per-experiment tables: `exp00*/summary.md`.
Labels: **Confirmed** (≥2 seeds on both sides, effect exceeds the noise floor, no open validity
question) · **Provisional** (exceeds the floor but single-seed or a validity question is open) ·
**No effect detected** (within noise; weaker when single-seed) · **Not tested**.
Noise floors (exp002, row-order split, RF-seed SD, n=5): malicious F1 0.0033, family GT macro-F1
0.0127 (the "0.013" floor), family E2E 0.0041, fine GT 0.0065, fine E2E 0.0051. exp004/exp005 effects
are judged against these metric-specific floors because their own n=1–2 SDs are unstable.
No multiple-comparison correction; verdicts are thresholds, not significance tests.

## 1. Execution

| Step | Status | Runs | Elapsed | Peak memory | Notes |
|---|---|---|---|---|---|
| exp001_baseline | frozen | 2 | — | — | unchanged throughout (sha256 verified twice) |
| exp002_seeds | completed | 14/14 | ~35 min | **8.63 GB** (over budget; before loader fix) | reproduces exp001; no CMs / per-class CIs; see `code/PROVENANCE.md` |
| gate_loader_equivalence | passed | 1 | 4.1 min | 4.13 GB | lean loader bit-identical to exp001 |
| exp003_cross_family | completed | 5/5 | 17.0 min | ≥5.57 GB | last ~12 min unmonitored (runner crash, run 1); exit code not recorded; outputs complete |
| exp006_shift_diagnosis | completed | 1/1 | 4.8 min | 5.66 GB | 2018 population asserted identical to exp003 |
| exp007_shift_mitigation | completed | 30/30 | 57.2 min | 5.51 GB | reproduces exp003 (seeds 42/1/2) exactly |
| exp004_leakage_vs_drift | completed | 14/14 | 26.8 min | 4.40 GB | 100% row alignment between releases |
| exp005_dedup_sensitivity | completed | 9/9 | 20.9 min | 5.45 GB | single RF seed |
| exp008_cross_test_dedup | completed | 3/3 seeds | 7.7 min | not measured (run outside the queue runner) | added after the queue; reproduces exp003 under drop_conflicts |

Run 1 of the queue crashed (status-file lock; reproduced and fixed; `INCIDENT_2026-10-14_runner_crash.md`).
Run 2: no failures; datasets, sources and exp001 artifacts unchanged (runner integrity check).

## 2. Evaluation protocol on CICIDS2017 (RandomForest, deduplicated, conflicting groups removed)

**C1. Time-ordered evaluation lowers every metric far beyond seed noise — Confirmed.**
exp002 (n=5 each): malicious F1 0.9029 ± 0.0033 (row-order) vs 0.9966 ± 0.0000 (random); family
GT −0.136, family E2E −0.146, fine GT −0.124, fine E2E −0.132 (7–11× the 0.013 floor).
exp004 repeats it with **true timestamps**: forward split malicious F1 0.9033 ± 0.0024, family GT
0.8397 ± 0.0038, benign FPR 2.90%.

**C2. Row order is a usable proxy for time, although the files are not chronological — Confirmed.**
Row position vs timestamp: Spearman ≈ 1.00 in the five Thursday/Friday files, but 0.48 / 0.47 / 0.66
in Monday / Tuesday / Wednesday (65–91% of rows more than 60 s behind the running maximum). Even so,
the row-order and true-time splits share 86% of their test flows and no headline metric differs
beyond noise (Δ malicious F1 −0.0007, family GT −0.0038, family E2E +0.0108 [n=2], fine GT +0.0025).
Per-class recall can differ (SSH-Patator 0.781 true-time vs 0.912 row-order).
The paper should use the true-time split as primary.

**C3. The gap is dominated by temporal extrapolation, not by correlated-flow leakage — Confirmed
for the ordering of magnitudes (n=2 per split).**

| Step (exp004) | Malicious F1 Δ | Family GT Δ | Family E2E Δ | Fine GT Δ |
|---|---|---|---|---|
| random → grouped by Flow ID (session leakage) | −0.0002 | +0.0033 | +0.0045 | −0.0030 |
| random → random 1 / 5 / 15-min time blocks (adjacency leakage) | −0.004 / −0.001 / −0.001 | +0.006 / +0.001 / −0.011 | +0.001 / −0.008 / −0.039 | −0.025 / −0.017 / −0.060 |
| blocks → forward true-time split (extrapolation / drift) | −0.089 to −0.092 | −0.116 to −0.133 | −0.113 to −0.153 | −0.072 to −0.115 |

Session and adjacency grouping move binary detection by ≤ 0.004 and family attribution mostly within
noise; only fine-grained attribution loses up to 0.06. Moving from interleaved blocks to forward
extrapolation costs 0.09 malicious F1 and 0.12–0.13 family GT.

**C4. The time-ordered drop is mainly benign false positives — Confirmed (n=2).**
Stage-1 precision 0.996 → 0.856 (random → forward), recall 0.997 → 0.956; benign FPR 0.07% → 2.90%.
By construction the forward split tests on the latest 20% of benign flows by time, i.e. traffic from the
end of the capture week, after training on earlier days (exact day composition not recorded).
"Drift" here therefore means later benign traffic looks unlike earlier benign traffic to the model,
plus later phases of each attack (Hulk recall 0.997 → 0.927, slowloris 0.997 → 0.899).

**C5. PortScan's random-split score is an adjacency effect — Provisional (n=2).**
PortScan recall 0.993 (random) → 0.830 (5-min blocks) → 0.826 (forward): grouping alone removes it.

**C6. Exact-duplicate leakage barely moves headline metrics — No effect detected (1 seed).**
A naive row-level split leaves an exact duplicate in train for 24.85% of test rows, yet versus a
hash-group split malicious F1 changes +0.0014 and family GT −0.012. What changes is the evaluated
population: PortScan test support 370 → 31,761 rows; benign FPR 0.08% → 0.12–0.15%.

**C7. Dedup / conflict policy — binary detection: no effect detected; attribution: inconclusive (1 seed).**
On a common test set, all four policies agree within ±0.001 (random split) and within ±0.003 malicious F1
(time-ordered split). Under the time-ordered split family GT moves −0.014 to +0.025 versus
drop_conflicts — 1–2× the seed SD, single seed, so not interpretable.

## 3. Data artifacts and attribution (CICIDS2017)

**C8. Label conflicts — Confirmed (deterministic; reproduced by the gate).** 309 distinct feature
vectors carry more than one label (82,704 rows; largest group 6,654 rows); every one includes BENIGN.
Distinct conflicting vectors per label: DoS Hulk 158, PortScan 106, Bot 40, DDoS 3, slowloris 2.

**C9. Duplication is attack-specific — Confirmed (deterministic).** Duplicate share before dedup:
PortScan 98.8% (158,804 → 1,956 unique), SSH-Patator 45.4%, Bot 26.5%, FTP-Patator 25.3%,
DoS Hulk 24.9%, DDoS 0.0%. Deduplication therefore reshapes the class mix rather than removing noise uniformly.

**C10. Hierarchical attribution propagates detection errors — Confirmed (n=5).**
Family F1 on ground-truth attacks vs end-to-end: Bot 0.996 → 0.729 (random) / 1.000 → 0.411
(row-order, E2E precision 0.259); DoS/DDoS 0.990 → 0.898 (row-order). Attribution quality cannot be
reported from ground-truth-only evaluation.

**C11. Web Brute Force vs XSS are poorly separable from flow features — Confirmed (n=5).**
Fine GT F1 0.723 ± 0.003 / 0.459 ± 0.014 (random), 0.624 ± 0.049 / 0.336 ± 0.023 (row-order).

## 4. Cross-dataset (CICIDS2017 → CSE-CIC-IDS2018, matched families: Benign, DoS/DDoS, Web Attack)

**X1. Zero-shot detection collapses — Confirmed on the deduplicated 2018 test set (exp003, n=5;
reproduced in exp007).** E2E macro-F1 0.9491 (2017 reference) → 0.3223; DoS recall 0.0003, Web
0.0107; almost all 2018 flows predicted benign.
**Robust to test-side deduplication — Confirmed (exp008, n=3):** scoring all 2,091,539 2018 rows
(no deduplication) gives malicious F1 0.0087 ± 0.0078, DoS recall 0.0044 ± 0.0039, Web 0.0000, and SlowHTTPTest
recall 0.000 over its 139,890 rows. The gap to Cantone et al. (F1 0.26–0.39, grouped binary) is therefore **not** explained
by deduplication; their 2018 test covers all attack days (DDoS LOIC/HOIC, brute force, bots, …) while ours covers
DoS Hulk / SlowHTTPTest / web attacks only — the attack-subset explanation is plausible but **not tested**.

**X2. Not a unit or alignment artifact — Confirmed (exp006).** Duration × byte-rate / bytes = 1e6,
duration × packet-rate / packets = 1e6, IAT-mean × (packets−1) / duration = 1, with p05 = p95, in both
datasets for Benign and DoS Hulk. 75 aligned features (= notebook), every 2018 label mapped.

**X3. What changed is the attack, not the benign marginals — Confirmed as description; causal role
Provisional (exp006).** DoS Hulk: 50/75 features with KS > 0.5 (max 0.91); zero backward bytes in
82% of 2018 flows vs 10% in 2017; median Init_Win_bytes_backward 235 → −1; median flow duration
86 s → 0.05 s. Benign: 0/75 features with KS > 0.5 (max 0.45), yet the years are jointly separable
(adversarial AUC 0.9997 on benign alone; top features header lengths, min_seg_size_forward, IAT minima).

**X4. Simple label-free fixes do not help — Confirmed for these transforms (exp007, RF n=3).**
Gap recovered: log-compression 0.0%, per-dataset robust scaling −0.0%, per-dataset quantile −0.2%,
dropping the 10 / 25 globally most-shifted features 0.5% / 0.1%. XGBoost (1 seed): 0–15.5%
(drop-10: Web recall 0.29, DoS 0.00). Caveat: the globally most-shifted features are benign-driven
(forward/timing features); the Hulk-specific backward-byte features rank 35th–46th and were never
dropped, so the "remove the attack-specific shift" hypothesis is **not tested**.

**X5. The features suffice within 2018; the failure is symmetric.** 2018→2018 (RF n=3): DoS recall
1.000, Web 0.765 ± 0.029 (68 test flows), benign FPR 0.0016%, E2E 0.949 — Confirmed for DoS,
Provisional for Web. 2018→2017 (RF, 1 seed): E2E 0.337, DoS 0.031, Web 0.000 — Provisional.
XGBoost 2017→2018 (1 seed): DoS 0.000 — Provisional.

**X6. 2018 SlowHTTPTest is 55 unique vectors in 139,890 rows** (top vector 44.3%) — consistent with
Cantone et al. (2024), who report 56 unique values in 105,550 samples in their corrected 2018 data.

## 5. Not tested

- Domain-adaptation methods beyond normalisation / feature dropping
- Removing the attack-specific shifted features (needs target labels)
- Attack families other than DoS-Hulk / SlowHTTPTest / web attacks across datasets; other 2018 days
- Models beyond RF (5 seeds) and XGBoost (1 seed)
- Exact day composition of the forward-split benign test set

## 6. Limitations

- exp002 exceeded the 6 GB budget; lacks confusion matrices / per-class CIs; its exact
  `ids_common.py` revision was not snapshotted.
- exp003 ran unmonitored for its last ~12 minutes; exit code not recorded.
- exp004 (n=2) and exp005 / reverse / XGBoost (n=1): seed estimates unstable or absent.
- RF seeds on deterministic splits measure model randomness only.
- One dataset pair; two 2018 days.

## 7. Addendum (2026-10-15): what the chronological split's false positives are (exp009, exp010)

Prompted by review feedback that the "forward" split is per class (each label cut at its own time,
no global cutoff), two descriptive analyses were added. No configuration was changed; exp010 re-fits
the exp004 forward and random seed-42 models and stops unless they reproduce the stored confusion
counts exactly (they did: 10,612 and 254 benign false positives).

**exp009 (split composition, no models).** 86% of forward test flows have at least one later
training flow. Benign test flows span Thu 16:23 – Fri 17:02 (92% Friday); 103,694 of 265,566 attack
training flows (39%; DDoS, PortScan, Bot) fall inside that window. A single global cutoff is not
feasible: at the 50th–90th time percentiles at most 2 of 14 attack classes have flows on both
sides; a Friday-00:00 cutoff leaves none. — Confirmed (deterministic).

**exp010 (endpoint audit, seed 42).** Of 10,612 forward-split benign false positives, 9,685 lie on
the DDoS victim–attacker pair (192.168.10.50 ↔ 172.16.0.1); 9,680 of those run victim → attacker
(ports ≥ 1024), opposite to every DDoS-labelled flow, and fall inside the labelled DDoS interval
15:56–16:16 (benign FPR inside the interval 20.5%, outside 0.26%). 802 lie on the Bot C&C channel
(→ 205.174.165.73:8080) and were recorded 13:00–17:00, after the last Bot label at 12:59. Together
98.8%. Random split: 4 and 116 of 254. Excluding benign flows on both sets from both test sets:
FPR 0.037% [0.031, 0.044] under both protocols; precision 0.998 both; malicious F1 0.977 vs 0.997
(gap 0.092 → 0.020, recall only: 0.957 vs 0.997). Five row-order seeds (exp002, recovered from
per-class precision): DDoS-assigned share of benign FPs 90.8–91.9% vs 2.6–5.2% random. — Confirmed
as a description of seed 42 (pattern stable over five seeds); post hoc, sets identified from the
errors they explain, so not a corrected benchmark. Residual recall loss: 85% DoS Hulk (both seeds);
cause not examined.

**Consequence for the earlier claim.** "The random-vs-temporal gap is temporal drift" is withdrawn.
The per-class chronological gap on CICIDS2017 is mainly benign-labelled attack-session flows that a
random split memorises; the item "exact day composition of the forward-split benign test set" in
§5 is now answered by exp009.
