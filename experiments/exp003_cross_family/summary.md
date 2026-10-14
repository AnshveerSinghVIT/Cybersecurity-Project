| Metric | 2017→2017 (reference) | 2017→2018 (cross) |
|---|---|---|
| Stage 1 malicious F1 | 0.9017 ± 0.0050 | 0.0006 ± 0.0004 |
| Stage 1 benign FPR | 0.0259 ± 0.0013 | 0.0001 ± 0.0000 |
| Stage 2 family macro-F1 (GT malicious) | 0.9884 ± 0.0054 | 0.7772 ± 0.0455 |
| End-to-end 3-class macro-F1 | 0.9491 ± 0.0026 | 0.3223 ± 0.0151 |
| Benign: Stage 1 recall (n=372,432 / 1,274,630) | 0.9741 ± 0.0013 | 0.9999 ± 0.0000 |
| Benign: E2E recall (n=372,432 / 1,274,630) | 0.9741 ± 0.0013 | 0.9999 ± 0.0000 |
| Benign: E2E precision (n=372,432 / 1,274,630) | 0.9900 ± 0.0006 | 0.8975 ± 0.0000 |
| DoS/DDoS: Stage 1 recall (n=64,316 / 145,254) | 0.9431 ± 0.0032 | 0.0003 ± 0.0002 |
| DoS/DDoS: E2E recall (n=64,316 / 145,254) | 0.9431 ± 0.0032 | 0.0003 ± 0.0002 |
| DoS/DDoS: E2E precision (n=64,316 / 145,254) | 0.8629 ± 0.0066 | 0.1773 ± 0.1114 |
| Web Attack: Stage 1 recall (n=430 / 335) | 0.9423 ± 0.0067 | 0.0107 ± 0.0240 |
| Web Attack: E2E recall (n=430 / 335) | 0.9372 ± 0.0057 | 0.0107 ± 0.0240 |
| Web Attack: E2E precision (n=430 / 335) | 0.9926 ± 0.0000 | 1.0000 ± 0.0000 |

Per raw label (end-to-end recall):

| Raw label | n ref | ref E2E recall | n cross | cross E2E recall |
|---|---|---|---|---|
| BENIGN | 372432 | 0.9741 ± 0.0013 | 1274630 | 0.9999 ± 0.0000 |
| DDoS | 25603 | 0.9974 ± 0.0001 | - | - |
| DoS GoldenEye | 2055 | 0.9985 ± 0.0000 | - | - |
| DoS Hulk | 34538 | 0.8988 ± 0.0059 | 145199 | 0.0003 ± 0.0002 |
| DoS Slowhttptest | 1046 | 0.9960 ± 0.0004 | 55 | 0.0000 ± 0.0000 |
| DoS slowloris | 1074 | 0.9196 ± 0.0067 | - | - |
| Web Attack - Brute Force | 294 | 0.9619 ± 0.0065 | 225 | 0.0000 ± 0.0000 |
| Web Attack - Sql Injection | 5 | 0.3200 ± 0.1095 | 31 | 0.0000 ± 0.0000 |
| Web Attack - XSS | 131 | 0.9053 ± 0.0042 | 79 | 0.0456 ± 0.1019 |
