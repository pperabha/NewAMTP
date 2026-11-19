| skew | variant | mean update_ms | mean restructure_ms | mean hash_calls | mean hash_bytes | mean server_ms | mean verify_ms | mean proof_bytes | mean max_partition |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 | AMTP | 862.964 | 7.322 | 405389 | 27776117 | 2.500 | 5.458 | 73561 | 64 |
| 0.25 | Static-MT | 2428.503 | 0.011 | 937998 | 67378599 | 2.313 | 4.851 | 69711 | 2492 |

Means over every batch of every run (paper (32): values averaged over the runs; restructure_ms = split / merge and relocation inside the commit). Raw rows: updates.csv.
