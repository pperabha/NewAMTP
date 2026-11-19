| skew | variant | mean update_ms | mean restructure_ms | mean hash_calls | mean hash_bytes | mean server_ms | mean verify_ms | mean proof_bytes | mean max_partition |
|---|---|---|---|---|---|---|---|---|---|
| 0.75 | AMTP | 1102.171 | 8.431 | 460798 | 31694633 | 2.209 | 4.745 | 63436 | 64 |
| 0.75 | Static-MT | 3238.690 | 0.010 | 1138738 | 83519572 | 2.065 | 4.309 | 60403 | 6588 |

Means over every batch of every run (paper (32): values averaged over the runs; restructure_ms = split / merge and relocation inside the commit). Raw rows: updates.csv.
