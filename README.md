# Encrypted Traffic Classification — Cross-Dataset IDS Evaluation

A network intrusion detection (IDS) project that:

1. Trains Random Forest and XGBoost classifiers to distinguish benign vs. malicious network flows on **CICIDS2017**.
2. Tests whether that model still works on a **different network's traffic** (CICIDS2018) captured a year later — the "cross-dataset generalization" question that single-dataset IDS papers usually skip.
3. Simulates a simple evasion attack (packet padding + timing jitter) against the cross-dataset model.

## Headline result

| | F1 score |
|---|---|
| In-dataset (train & test on CICIDS2017) | 0.997 |
| Cross-dataset (train on 2017, test on 2018) | 0.002 |

The model is near-perfect on the network it was trained on and effectively blind on a different network — recall on malicious traffic collapses to ~0%. This was verified against three specific pipeline bugs (label case-mismatch between dataset years, a feature-alignment gap that silently dropped 30 features, and a feature-order/encoding consistency check) before being accepted as a genuine result — see the diagnostic print statements embedded in the notebook itself (Day 2, Step 3) for the receipts. Part of the magnitude is attributable to a known distributional shift between the two CICFlowMeter capture versions, not purely model failure to learn general attack signatures — see the notebook's markdown commentary for the full discussion.

## Setup

**Requirements:** Python 3.10+, ~10GB free disk (for the downloaded datasets), ~6GB free RAM while running.

```bash
git clone https://github.com/AnshveerSinghVIT/Cybersecurity-Project.git
cd Cybersecurity-Project
pip install -r requirements.txt
```

**Get a Kaggle API token** (needed to download CICIDS2017):
1. Go to [kaggle.com/settings](https://kaggle.com/settings) → "Create New Token" — downloads `kaggle.json`.
2. Place `kaggle.json` in this same folder, next to the notebook. (It's gitignored — never commit it.)

CICIDS2018 downloads automatically from a public, unauthenticated AWS S3 bucket — no AWS account needed.

## Running

Open `ids_implementation.ipynb` in VS Code (with the Jupyter extension) or `jupyter notebook`, select a Python kernel with the above packages installed, and run all cells top to bottom.

- First run downloads ~1.5GB of data total (CICIDS2017 + two days of CICIDS2018) into `cicids2017/` and `cicids2018/` folders (gitignored, re-downloaded on demand, skipped automatically if already present).
- GPU is optional — the notebook auto-detects whether XGBoost can actually use your GPU (not just whether one is present) and falls back to CPU cleanly if not.
- If you hit `MemoryError` or the kernel dies, close other applications — the notebook prints available RAM at the top and warns if it's under 6GB.
- **If you re-run only part of the notebook after editing a cell, prefer Kernel → Restart → Run All.** Jupyter keeps stale function definitions in memory otherwise, which can silently make an edited cell behave as if unedited.

## What's in this repo

- `ids_implementation.ipynb` — the full analysis, Day 1 (baseline) and Day 2 (cross-dataset + evasion test).
- `*.png` — saved output plots (confusion matrices, feature importance, cross-dataset F1 comparison, evasion robustness, early-flow detection curve).
- `requirements.txt` — pinned package versions used to produce the results above.

Not included (see `.gitignore`): the downloaded CICIDS2017/2018 CSVs (~1.5GB, re-downloaded automatically) and `kaggle.json` (personal API credentials — get your own, see Setup above).
