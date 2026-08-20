# Encrypted Traffic Classification — Cross-Dataset IDS Evaluation

## What this project is

A network intrusion detection (IDS) project using Random Forest and XGBoost on flow-level
traffic features (packet sizes, timing, flag counts — no packet contents). It trains on
**CICIDS2017** and then tests whether the trained model still works on **CICIDS2018**, a
different network's traffic captured a year later, plus a simple evasion test (packet padding +
timing jitter) against the cross-dataset model.

## Conclusion so far

| | F1 score |
|---|---|
| In-dataset (train & test on CICIDS2017) | 0.997 |
| Cross-dataset (train on 2017, test on 2018) | 0.002 |

The model is near-perfect on the network it was trained on and effectively blind on a different
network — recall on malicious traffic collapses to ~0% cross-dataset. Part of this is genuine
overfitting to network-specific traffic patterns, and part is attributable to a distributional
shift between the two CICFlowMeter capture versions (flow statistics like packet count and
inter-arrival time differ by 13x–400x between years). See the notebook's markdown cells for the
full discussion. The evasion test is inconclusive on its own, since cross-dataset detection was
already near-zero before any perturbation was applied.

## How to run

**Requirements:** Python 3.10+, ~10GB free disk (for downloaded datasets), ~6GB free RAM.

```bash
git clone https://github.com/AnshveerSinghVIT/Cybersecurity-Project.git
cd Cybersecurity-Project
pip install -r requirements.txt
```

A Kaggle API token (`kaggle.json`) is already included in this repo for downloading CICIDS2017.
CICIDS2018 downloads automatically from a public, unauthenticated AWS S3 bucket.

Open `ids_implementation.ipynb` in VS Code (with the Jupyter extension) or `jupyter notebook`,
select a Python kernel with the above packages installed, and run all cells top to bottom.

- First run downloads ~1.5GB of data into `cicids2017/` and `cicids2018/` folders (gitignored,
  skipped automatically on future runs if already present).
- GPU is optional — the notebook auto-detects whether it can actually be used and falls back to
  CPU cleanly if not.
- If you edit a cell and re-run only part of the notebook, prefer Kernel → Restart → Run All to
  avoid stale state.

## What's in this repo

- `ids_implementation.ipynb` — the full analysis, Day 1 (baseline) and Day 2 (cross-dataset +
  evasion test).
- `*.png` — saved output plots (confusion matrices, feature importance, cross-dataset F1
  comparison, evasion robustness, early-flow detection curve).
- `requirements.txt` — package versions used to produce the results above.
- `kaggle.json` — Kaggle API token for downloading CICIDS2017. This repo is private; do not make
  it public without removing this file first.
