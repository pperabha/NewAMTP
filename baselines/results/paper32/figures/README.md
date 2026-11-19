# Paper (32) figures (baselines/plot_p32.py)

Every timing = mean of 10 runs after 3 warm-up runs (#46). Query-level points (Exp. 1, 2, 5 queries, tamper verification) = median over the queries of that x, error bars = interquartile range (#66); Exp. 3, Exp. 4, update isolation and Sepolia = mean over runs / batches / updates, no bars. Numbers (and q1 / q3) in figure_points.csv.

| figure | data | note |
|---|---|---|
| e1_single_kq_search | <data>/p32_ex1_search1_w6 search_single N=100000 | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud |
| e1_single_n_search | <data>/p32_ex1_search1_w6 search_single kQ=4 | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud |
| e1_single_kq_query_gen | <data>/p32_ex1_search1_w6 search_single N=100000 |  |
| e1_single_n_query_gen | <data>/p32_ex1_search1_w6 search_single kQ=4 |  |
| e1_single_kq_server | <data>/p32_ex1_search1_w6 search_single N=100000 |  |
| e1_single_n_server | <data>/p32_ex1_search1_w6 search_single kQ=4 |  |
| e1_single_kq_e2e | <data>/p32_ex1_search1_w6 search_single N=100000 | query generation + server + DU verification; record decryption and AMTP's root read excluded |
| e1_single_n_e2e | <data>/p32_ex1_search1_w6 search_single kQ=4 | query generation + server + DU verification; record decryption and AMTP's root read excluded |
| e1_single_kq_verify | <data>/p32_ex1_search1_w6 search_single N=100000 |  |
| e1_single_n_verify | <data>/p32_ex1_search1_w6 search_single kQ=4 |  |
| e1_multi_AND_search | <data>/p32_x_search_verify_w8 search_multi shape=AND (4 domains) | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_e2e | <data>/p32_x_search_verify_w8 search_multi shape=AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_query_gen | <data>/p32_x_search_verify_w8 search_multi shape=AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_server | <data>/p32_x_search_verify_w8 search_multi shape=AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_verify | <data>/p32_x_search_verify_w8 search_multi shape=AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_search | <data>/p32_x_search_verify_w8 search_multi shape=OR (4 domains) | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_e2e | <data>/p32_x_search_verify_w8 search_multi shape=OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_query_gen | <data>/p32_x_search_verify_w8 search_multi shape=OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_server | <data>/p32_x_search_verify_w8 search_multi shape=OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_verify | <data>/p32_x_search_verify_w8 search_multi shape=OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_of_OR_search | <data>/p32_x_search_verify_w8 search_multi shape=AND_of_OR (4 domains) | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_of_OR_e2e | <data>/p32_x_search_verify_w8 search_multi shape=AND_of_OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_of_OR_query_gen | <data>/p32_x_search_verify_w8 search_multi shape=AND_of_OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_of_OR_server | <data>/p32_x_search_verify_w8 search_multi shape=AND_of_OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_AND_of_OR_verify | <data>/p32_x_search_verify_w8 search_multi shape=AND_of_OR (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_of_AND_search | <data>/p32_x_search_verify_w8 search_multi shape=OR_of_AND (4 domains) | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_of_AND_e2e | <data>/p32_x_search_verify_w8 search_multi shape=OR_of_AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_of_AND_query_gen | <data>/p32_x_search_verify_w8 search_multi shape=OR_of_AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_of_AND_server | <data>/p32_x_search_verify_w8 search_multi shape=OR_of_AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_multi_OR_of_AND_verify | <data>/p32_x_search_verify_w8 search_multi shape=OR_of_AND (4 domains) | ; SE-COLLAB only (multi-domain Boolean) |
| e1_domains_search | <data>/p32_xdomains_w9 domains_scaling | same files regrouped into D domains |
| e1_domains_e2e | <data>/p32_xdomains_w9 domains_scaling | same files regrouped into D domains |
| e1_domains_verify | <data>/p32_xdomains_w9 domains_scaling | same files regrouped into D domains |
| e1_domains_server | <data>/p32_xdomains_w9 domains_scaling | same files regrouped into D domains |
| e1_domains_query_gen | <data>/p32_xdomains_w9 domains_scaling | same files regrouped into D domains |
| e2_layout_clustered_proof | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=clustered | Chen and Du have no separate proof generation |
| e2_layout_dispersed_proof | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=dispersed | Chen and Du have no separate proof generation |
| e2_layout_partition_spread_proof | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=partition_spread | Chen and Du have no separate proof generation |
| e2_layouts_proof | <data>/p32_exp2_exp5_w10 exp2_selective_proof | clustered = few partitions, dispersed = many, partition spread = one record per partition |
| e2_layout_clustered_verify | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=clustered |  |
| e2_layout_dispersed_verify | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=dispersed |  |
| e2_layout_partition_spread_verify | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=partition_spread |  |
| e2_layouts_verify | <data>/p32_exp2_exp5_w10 exp2_selective_proof | clustered = few partitions, dispersed = many, partition spread = one record per partition |
| e2_layout_clustered_proof_kb | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=clustered |  |
| e2_layout_dispersed_proof_kb | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=dispersed |  |
| e2_layout_partition_spread_proof_kb | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=partition_spread |  |
| e2_layouts_proof_kb | <data>/p32_exp2_exp5_w10 exp2_selective_proof | clustered = few partitions, dispersed = many, partition spread = one record per partition |
| e2_layout_clustered_server | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=clustered |  |
| e2_layout_dispersed_server | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=dispersed |  |
| e2_layout_partition_spread_server | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=partition_spread |  |
| e2_layouts_server | <data>/p32_exp2_exp5_w10 exp2_selective_proof | clustered = few partitions, dispersed = many, partition spread = one record per partition |
| e2_layout_clustered_e2e | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=clustered |  |
| e2_layout_dispersed_e2e | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=dispersed |  |
| e2_layout_partition_spread_e2e | <data>/p32_exp2_exp5_w10 exp2_selective_proof layout=partition_spread |  |
| e2_layouts_e2e | <data>/p32_exp2_exp5_w10 exp2_selective_proof | clustered = few partitions, dispersed = many, partition spread = one record per partition |
| e2_single_verify_verify | <data>/p32_ex2_verify1_tamper_w7 verify_single |  |
| e2_single_verify_proof_kb | <data>/p32_ex2_verify1_tamper_w7 verify_single |  |
| e2_single_verify_e2e | <data>/p32_ex2_verify1_tamper_w7 verify_single |  |
| e2_single_verify_search | <data>/p32_ex2_verify1_tamper_w7 verify_single | server search = posting retrieval + Boolean evaluation, no proof, no fetch; Chen's server does not evaluate the AND (the DU ANDs the decrypted bitmaps); Du = slowest cloud |
| e2_single_verify_server | <data>/p32_ex2_verify1_tamper_w7 verify_single |  |
| e2_tamper_modify_detection | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | a scheme without this attack model has no line (Chen: modify / old version N/A) |
| e2_tamper_modify_verify | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | time until the DU rejects |
| e2_tamper_hide_detection | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | a scheme without this attack model has no line (Chen: modify / old version N/A) |
| e2_tamper_hide_verify | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | time until the DU rejects |
| e2_tamper_inject_detection | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | a scheme without this attack model has no line (Chen: modify / old version N/A) |
| e2_tamper_inject_verify | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | time until the DU rejects |
| e2_tamper_old_version_detection | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | a scheme without this attack model has no line (Chen: modify / old version N/A) |
| e2_tamper_old_version_verify | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | time until the DU rejects |
| e2_tamper_attack_types | <data>/p32_ex2_verify1_tamper_w7 tamper_detection | attack types (modified, hidden, injected, old version) detected in every run; Chen has no modified / old-version attack model |
| e2_multi_verify_verify | <data>/p32_x_search_verify_w8 verify_multi | SE-COLLAB only (multi domain) |
| e2_multi_verify_proof_kb | <data>/p32_x_search_verify_w8 verify_multi | SE-COLLAB only (multi domain) |
| e2_multi_verify_e2e | <data>/p32_x_search_verify_w8 verify_multi | SE-COLLAB only (multi domain) |
| e2_multi_verify_search | <data>/p32_x_search_verify_w8 verify_multi | SE-COLLAB only (multi domain) |
| e3_b_update | <data>/p32_ex3_w10/. exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_b_per_request | <data>/p32_ex3_w10/. exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_b_throughput | <data>/p32_ex3_w10/. exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_b_breakdown_insert | <data>/p32_ex3_w10/. exp3_dynamic_update | ABS is part of request / CS prepare / DO validation; posting repair + auth tree are inside CS prepare |
| e3_b_breakdown_delete | <data>/p32_ex3_w10/. exp3_dynamic_update | ABS is part of request / CS prepare / DO validation; posting repair + auth tree are inside CS prepare |
| e3_n_update | <data>/p32_ex3_w10/update_n exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_n_per_request | <data>/p32_ex3_w10/update_n exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_n_throughput | <data>/p32_ex3_w10/update_n exp3_dynamic_update | AMTP: signed requests (ABS) + CS prepare + DO validation + anchor (local EVM); Chen: token generation + CS apply, no update verification |
| e3_n_breakdown_insert | <data>/p32_ex3_w10/update_n exp3_dynamic_update | ABS is part of request / CS prepare / DO validation; posting repair + auth tree are inside CS prepare |
| e3_n_breakdown_delete | <data>/p32_ex3_w10/update_n exp3_dynamic_update | ABS is part of request / CS prepare / DO validation; posting repair + auth tree are inside CS prepare |
| e4_update_insert | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | mean over every batch of the phase and the 10 runs; AMTP (full protocol) = signed requests, DO validation and anchor (local EVM) around the same index work |
| e4_update_delete | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | mean over every batch of the phase and the 10 runs; AMTP (full protocol) = signed requests, DO validation and anchor (local EVM) around the same index work |
| e4_restructure | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | restructure_ms inside the commit |
| e4_splits_merges | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 |  |
| e4_max_partition | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | after the last batch (insert + hot delete) |
| e4_query_server | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | queries after the last batch |
| e4_query_verify | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | queries after the last batch |
| e4_proof_kb | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | queries after the last batch |
| e4_batches_skew0 | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | skew 0: mean over the 10 runs at every batch (insert batches, then hot delete); index level |
| e4_batches_skew0.25 | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | skew 0.25: mean over the 10 runs at every batch (insert batches, then hot delete); index level |
| e4_batches_skew0.5 | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | skew 0.5: mean over the 10 runs at every batch (insert batches, then hot delete); index level |
| e4_batches_skew0.75 | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | skew 0.75: mean over the 10 runs at every batch (insert batches, then hot delete); index level |
| e4_batches_skew0.95 | ex4_*skew*/<job>/amtp/{splitmerge,skewproto}_n25000_t64 | skew 0.95: mean over the 10 runs at every batch (insert batches, then hot delete); index level |
| e5_query_search | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_query_proof | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_query_verify | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_query_e2e | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_query_query_gen | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_query_server | <data>/p32_exp2_exp5_w10 exp5_domains | queried domain fixed at 5,000 records |
| e5_isolation_update | <data>/p32_exp2_exp5_w10 exp5_domains op=update_one_domain | one epoch on the target domain; every other Domain Root unchanged (checked); RootAnchor on a local EVM |
| e5_isolation_protocol | <data>/p32_exp2_exp5_w10 exp5_domains op=update_one_domain | one epoch on the target domain; every other Domain Root unchanged (checked); RootAnchor on a local EVM |
| e5_root_anchor_ms | <data>/p32_exp2_exp5_w10 exp5_domains op=update_one_domain | one epoch on the target domain; every other Domain Root unchanged (checked); RootAnchor on a local EVM |
| e5_root_gas_localevm | <data>/p32_exp2_exp5_w10 exp5_domains op=update_one_domain | one epoch on the target domain; every other Domain Root unchanged (checked); RootAnchor on a local EVM; NOT for the paper: py-evm's gas schedule differs from Ethereum (same transaction: 64.1k local vs 86.7k on Sepolia at D = 1); use e5_sepolia_gas |
| e5_sepolia_gas | chain/runs/gas_domains_20261119_005048.csv | Ethereum Sepolia, one submit per D |
| e5_sepolia_time | chain/runs/gas_domains_20261119_005048.csv | time until the transaction is mined |
