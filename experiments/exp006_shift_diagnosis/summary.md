## Q1 unit identities (median [p05, p95])

| Dataset/class | dur×bytes_rate/bytes (1e6 = µs) | dur×pkt_rate/pkts (1e6) | IAT_mean×(pkts−1)/dur (1) | Flow Duration median |
|---|---|---|---|---|
| 2017/BENIGN | 1e+06 [1e+06, 1e+06] | 1e+06 [1e+06, 1e+06] | 1 [1, 1] | 5.883e+04 |
| 2017/DoS Hulk | 1e+06 [1e+06, 1e+06] | 1e+06 [1e+06, 1e+06] | 1 [1, 1] | 8.642e+07 |
| 2018/BENIGN | 1e+06 [1e+06, 1e+06] | 1e+06 [1e+06, 1e+06] | 1 [1, 1] | 4.143e+06 |
| 2018/DoS Hulk | 1e+06 [1e+06, 1e+06] | 1e+06 [1e+06, 1e+06] | 1 [1, 1] | 5.095e+04 |

## Q3 adversarial validation (RF holdout AUC; 0.5 = indistinguishable)

- all_2017_vs_all_2018 (label-free): **0.9997** (n=[100000, 100000]); top features: Bwd Header Length (0.069), Fwd Header Length (0.061), min_seg_size_forward (0.060), Bwd IAT Min (0.049), Max Packet Length (0.046)
- benign_2017_vs_benign_2018: **0.9997** (n=[100000, 100000]); top features: min_seg_size_forward (0.075), Fwd Header Length (0.067), Bwd IAT Min (0.058), Fwd IAT Min (0.044), Bwd Header Length (0.042)
- hulk_2017_vs_hulk_2018: **1.0000** (n=[100000, 100000]); top features: Bwd Packet Length Mean (0.125), Avg Bwd Segment Size (0.093), Init_Win_bytes_backward (0.073), Average Packet Size (0.067), Bwd Packet Length Max (0.064)
- hulk_2018_vs_benign_2017: **1.0000** (n=[100000, 100000]); top features: Fwd IAT Min (0.101), Packet Length Mean (0.062), Total Backward Packets (0.062), Subflow Bwd Packets (0.059), Average Packet Size (0.058)
- hulk_2017_vs_benign_2017 (in-domain reference): **1.0000** (n=[100000, 100000]); top features: Bwd Packet Length Mean (0.128), Avg Bwd Segment Size (0.107), Bwd Packet Length Std (0.095), Packet Length Std (0.056), Bwd Packet Length Max (0.050)

## Q2 top-10 shifted features, DoS Hulk (KS; medians 2017 → 2018)

| Feature | KS | single-feature AUC | median 2017 | median 2018 | zero share 2017 | zero share 2018 |
|---|---|---|---|---|---|---|
| Init_Win_bytes_backward | 0.911 | 0.934 | 235 | -1 | 0.00 | 0.00 |
| Total Length of Bwd Packets | 0.897 | 0.943 | 1.16e+04 | 0 | 0.10 | 0.82 |
| Bwd Packet Length Max | 0.897 | 0.943 | 5792 | 0 | 0.10 | 0.82 |
| Bwd Packet Length Mean | 0.897 | 0.943 | 1932 | 0 | 0.10 | 0.82 |
| Max Packet Length | 0.897 | 0.963 | 5792 | 0 | 0.05 | 0.82 |
| Packet Length Std | 0.897 | 0.963 | 1657 | 0 | 0.05 | 0.82 |
| Packet Length Variance | 0.897 | 0.963 | 2.745e+06 | 0 | 0.05 | 0.82 |
| Avg Bwd Segment Size | 0.897 | 0.943 | 1932 | 0 | 0.10 | 0.82 |
| Subflow Bwd Bytes | 0.897 | 0.943 | 1.16e+04 | 0 | 0.10 | 0.82 |
| Bwd Packet Length Std | 0.897 | 0.942 | 2178 | 0 | 0.10 | 0.82 |

Features with KS > 0.5: DoS Hulk 50/75, Benign 0/75

## Q4 duplication (before dedup)

| Dataset | Label | Rows | Unique vectors | Duplicate share | Top vector share | Top vector non-zero features |
|---|---|---|---|---|---|---|
| 2018 | BENIGN | 1,489,375 | 1,274,630 | 14.4% | 0.1% | 16 |
| 2018 | DoS Hulk | 461,912 | 145,199 | 68.6% | 0.0% | 16 |
| 2018 | DoS Slowhttptest | 139,890 | 55 | 100.0% | 44.3% | 16 |
| 2018 | Web Attack - Brute Force | 249 | 228 | 8.4% | 1.6% | 16 |
| 2018 | Web Attack - XSS | 79 | 79 | 0.0% | 1.3% | 49 |
| 2018 | Web Attack - Sql Injection | 34 | 34 | 0.0% | 2.9% | 49 |
| 2017 | BENIGN | 2,271,320 | 1,862,465 | 18.0% | 0.4% | 29 |
| 2017 | DoS Hulk | 230,124 | 172,846 | 24.9% | 4.1% | 17 |
| 2017 | PortScan | 158,804 | 1,956 | 98.8% | 4.2% | 36 |
| 2017 | DDoS | 128,025 | 128,014 | 0.0% | 0.0% | 35 |
| 2017 | DoS GoldenEye | 10,293 | 10,275 | 0.2% | 0.0% | 20 |
| 2017 | FTP-Patator | 7,935 | 5,931 | 25.3% | 8.5% | 31 |
| 2017 | SSH-Patator | 5,897 | 3,219 | 45.4% | 2.0% | 19 |
| 2017 | DoS slowloris | 5,796 | 5,372 | 7.3% | 0.3% | 32 |
| 2017 | DoS Slowhttptest | 5,499 | 5,228 | 4.9% | 1.5% | 32 |
| 2017 | Bot | 1,956 | 1,437 | 26.5% | 1.1% | 36 |
| 2017 | Web Attack - Brute Force | 1,507 | 1,470 | 2.5% | 0.3% | 19 |
| 2017 | Web Attack - XSS | 652 | 652 | 0.0% | 0.2% | 47 |
| 2017 | Infiltration | 36 | 36 | 0.0% | 2.8% | 48 |
| 2017 | Web Attack - Sql Injection | 21 | 21 | 0.0% | 4.8% | 48 |
| 2017 | Heartbleed | 11 | 11 | 0.0% | 9.1% | 51 |
