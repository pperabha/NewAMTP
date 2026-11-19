| skew | variant | mean update_ms | mean restructure_ms | mean hash_calls | mean hash_bytes | mean server_ms | mean verify_ms | mean proof_bytes | mean max_partition |
|---|---|---|---|---|---|---|---|---|---|
| 0.5 | AMTP | 1061.058 | 8.674 | 445271 | 30564364 | 2.491 | 5.197 | 68370 | 64 |
| 0.5 | Static-MT | 2941.252 | 0.012 | 1023087 | 74263351 | 2.375 | 4.717 | 65004 | 4547 |

Means over every batch of every run (paper (32): values averaged over the runs; restructure_ms = split / merge and relocation inside the commit). Raw rows: updates.csv.
