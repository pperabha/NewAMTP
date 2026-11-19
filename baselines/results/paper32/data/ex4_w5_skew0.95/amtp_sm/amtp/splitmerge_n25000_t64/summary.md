| skew | variant | mean update_ms | mean restructure_ms | mean hash_calls | mean hash_bytes | mean server_ms | mean verify_ms | mean proof_bytes | mean max_partition |
|---|---|---|---|---|---|---|---|---|---|
| 0.95 | AMTP | 1089.718 | 8.279 | 432494 | 29740535 | 2.102 | 4.838 | 59733 | 64 |
| 0.95 | Static-MT | 3643.149 | 0.010 | 1247651 | 92109653 | 1.947 | 4.253 | 56466 | 8206 |

Means over every batch of every run (paper (32): values averaged over the runs; restructure_ms = split / merge and relocation inside the commit). Raw rows: updates.csv.
