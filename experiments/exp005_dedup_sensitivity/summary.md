| Split | Policy | Test set | n test | Mal-F1 | Benign FPR | Family GT | Family E2E | Fine GT | PortScan fam-GT F1 |
|---|---|---|---|---|---|---|---|---|---|
| random (hash group) | drop_conflicts | own_test | 439,665 | 0.9966 | 0.077% | 0.9745 | 0.9378 | 0.9053 | 0.9865 |
| random (hash group) | drop_conflicts | common_test | 439,665 | 0.9966 | 0.077% | 0.9745 | 0.9378 | 0.9053 | 0.9865 |
| random (hash group) | keep_first | own_test | 439,725 | 0.9966 | 0.079% | 0.9741 | 0.9373 | 0.9037 | 0.9865 |
| random (hash group) | keep_first | common_test | 439,665 | 0.9967 | 0.078% | 0.9741 | 0.9375 | 0.9037 | 0.9865 |
| random (hash group) | majority | own_test | 439,725 | 0.9964 | 0.081% | 0.9740 | 0.9134 | 0.9071 | 0.9871 |
| random (hash group) | majority | common_test | 439,665 | 0.9965 | 0.081% | 0.9738 | 0.9146 | 0.9070 | 0.9865 |
| random (hash group) | none | own_test | 558,427 | 0.9955 | 0.151% | 0.9771 | 0.9284 | 0.9122 | 0.9999 |
| random (hash group) | none | common_test | 439,665 | 0.9968 | 0.082% | 0.9750 | 0.9397 | 0.9105 | 0.9905 |
| random (row) | none | own_test | 565,576 | 0.9968 | 0.124% | 0.9652 | 0.9373 | 0.9166 | 0.9999 |
| temporal (hash group) | drop_conflicts | own_test | 439,721 | 0.9003 | 3.041% | 0.8420 | 0.7814 | 0.7785 | 0.3193 |
| temporal (hash group) | drop_conflicts | common_test | 439,721 | 0.9003 | 3.041% | 0.8420 | 0.7814 | 0.7785 | 0.3193 |
| temporal (hash group) | keep_first | own_test | 439,731 | 0.9011 | 2.934% | 0.8660 | 0.7808 | 0.7575 | 0.3397 |
| temporal (hash group) | keep_first | common_test | 439,721 | 0.9012 | 2.934% | 0.8660 | 0.7808 | 0.7575 | 0.3397 |
| temporal (hash group) | majority | own_test | 439,731 | 0.8999 | 3.013% | 0.8278 | 0.7795 | 0.7866 | 0.3463 |
| temporal (hash group) | majority | common_test | 439,721 | 0.8999 | 3.013% | 0.8278 | 0.7796 | 0.7866 | 0.3463 |
| temporal (hash group) | none | own_test | 445,627 | 0.9042 | 2.950% | 0.8678 | 0.7770 | 0.7921 | 0.3562 |
| temporal (hash group) | none | common_test | 439,721 | 0.9034 | 2.988% | 0.8669 | 0.7769 | 0.7919 | 0.3495 |
