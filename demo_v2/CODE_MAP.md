# AMTP demo v2 — code map (Phase 0)

Status: Phase 0 map. The demo is now built; see `README.md` for how it runs and the decisions taken
(A: Domain Root for the verdict, `R_G` as an audit display; B: reuse `amtp/adversary.py` plus new mutations
in `attacks.py`; C: FastAPI; D: 4 × 5,000 files by default with `--files-per-domain`; E: four processes,
with every search going through the network-path process).
Read from `main` at `0a539cb`. γ keeps the partition version v: `γ = H(PID ‖ v ‖ H(Enc(L)))`
(`amtp/index.py:65`, default `AMTP_GAMMA_V=1`). The demo will refuse to start if `gamma_has_v()` is false.

Not read and not used: `amtp_code/amtp/scenario.py` and `amtp_code/tests/test_demo.py` (the world builder of the
old Flask demo, removed before submission; the tests still use it).

All paths below are relative to `amtp_code/`.

## 1. Paper phase → real code

| Paper step | File : function | What it does |
|---|---|---|
| **Setup** — domain keys | `amtp/owner.py:22` `DomainKeys` | `K_s` (AES-SIV keyword key), `K_a` (query authentication key) |
| Setup — attribute keys | `amtp/core/crypto.py:127` `AttributeAuthority` | issues attribute keys, wraps `K_d` under a policy (**stand-in for CP-ABE**) |
| Setup — owner signing key | `amtp/core/crypto.py:108` `Signer` | Ed25519 (**stand-in for ABS**) |
| Setup — genesis root | `amtp/update.py:70` `genesis_root`, `amtp/anchor.py:43` `register_domain` | `R^(0)`, `e* = 0` on the anchor |
| **Phase 1** — encrypt a file | `amtp/owner.py:75` `DataOwner.encrypt` → `amtp/core/crypto.py:53` `make_ct` | `CT_d` (AES-GCM, raw bytes), `cid = H(CT_d)` (`amtp/dht.py:17`) |
| Phase 1 — keywords | `amtp/nlp.py:202` `phase1_keywords` (RAKE), `amtp/nlp.py:207` `norm` | the dataset already holds `W(d)` extracted with this code |
| Phase 1 — keyword tokens | `amtp/owner.py:38` `keyword_ciphers`, `:32` `keyword_key` | `C_w = DEnc_Ks(Norm(w))`, `h_w = H(C_w)` |
| **Phase 2** — signed request | `amtp/owner.py:94` `insert_request`, `:101` `delete_request` | `U_op`, `σ_op` |
| Phase 2 — server prepares candidate | `amtp/server.py:58` `CloudServer.prepare_update` → `amtp/engine.py:192` `insert`, `:215` `delete`, `:228` `commit(evidence=True)` | new roots, placements, `Aff_i`, `Δ`, `π^upd` |
| Phase 2 — owner validates | `amtp/validator.py:214` `Validator.check` | recomputes old and new roots from `π^upd`, returns `σ_root` |
| Phase 2 — anchor | `amtp/anchor.py:51` `RootAnchor.submit` | checks predecessor, `e' = e* + 1`, `σ_root`; recomputes `R_G` (`:66`) |
| Phase 2 — finalize / abort | `amtp/server.py:128` `finalize_update`, `:116` `abort_update` | expose new snapshot, or roll back |
| Phase 2 — whole epoch | `amtp/owner.py:107` `DataOwner.update` | the five steps above in order |
| **Phase 3** — split / merge | `amtp/variants.py:29` `AdaptivePolicy.adapt` → `amtp/engine.py:315` `split`, `:325` `merge`; validator side `amtp/validator.py:324` | split if `n > θ_max`, merge if `n < θ_min` and a partner fits |
| **Index** — γ, ρ, IMT leaf, `R_D` | `amtp/index.py:70` `gamma`, `:76` `rho`, `:81` `imt_leaf`, `:162` `domain_root` | PAPC and indexed Merkle tree |
| Index — lookup only | `amtp/bptree.py`, `amtp/cuckoo.py`, `amtp/server.py:284` `lookup` | B+ tree and Cuckoo filter; not evidence |
| **Phase 4** — trapdoor | `amtp/user.py:63` `DataUser.make_query` | parse → `h_w` per keyword → canonical `B_Q` → read `(e*, R_D)` from the anchor → `τ_Q = HMAC_Ka(...)` |
| Phase 4 — admission | `amtp/server.py:183` `CloudServer._admit` | `τ_Q`, timestamp, nonce, epoch |
| Phase 4 — search + proof | `amtp/server.py:221` `build_response(state, b_q, nonce, dht, timing=)` | evidence per keyword (present: postings + IMT proof; absent: non-membership), Boolean evaluation, partition multiproofs, one domain multiproof, ciphertexts from the DHT |
| Phase 4 — entry point | `amtp/server.py:163` `CloudServer.search(t_q, respond=None)` | admission + `build_response` |
| **Phase 5** — verify | `amtp/user.py:86` `DataUser.verify` | seven checks in order: `ctx`, `anchor`, `idx`, `papc`, `part`, `comp`, `ct`; returns pass/fail and detail per check, plus `phase_ms` |
| Phase 5 — decrypt | `amtp/user.py:278` `DataUser.decrypt` | only called after acceptance; `locked` if attributes do not satisfy the policy |
| **Root Anchor** | `amtp/anchor.py:35` `RootAnchor` | in-process Python class (**simulated, not a blockchain**) |
| **Storage** | `amtp/dht.py:24` `DHT` | 6 nodes, 3 replicas, in memory, one process |
| Cost counter | `amtp/core/hashing.py:23` `HashCounter` | hash calls and hashed bytes, per process |
| Boolean parser | `amtp/core/boolean.py:21` `parse`, `:87` `canonical`, `:122` `evaluate` | AND / OR / parentheses / quoted phrases |
| Cross-domain query | `bench/experiments.py:350` `run_xquery` | one domain-bound query per domain, each verified against that domain's own root |
| Dataset | `baselines/amtp_dataset.py:97` `sample`, `:113` `read_bytes`, `:119` `insert_pool`, `:88` `summary` | dataset-v4: arXiv, 4 domains × 125,000 files + 12,500 insert-pool files each, at `data/amtp_file_db_v4` |
| Bulk load (benchmarks) | `bench/experiments.py:171` `Domain`, `amtp/validator.py:196` `Validator.bootstrap` | load N files with `Engine.insert` + one `commit`, owner signs the transition, Validator trusts that start state |
| Existing attack plug-in | `amtp/adversary.py:106` `Adversary` | wraps the honest server through the `respond=` hook; see gap 9 |

## 2. Who holds what

| | Data User (client process) | Data Owner | Cloud Server (server process) | Root Anchor |
|---|---|---|---|---|
| `K_s` keyword key | yes | yes | **never** | no |
| `K_a` query-auth key | yes | yes | yes (by design: it checks `τ_Q`) | no |
| Attribute keys | own attributes only | via Authority | no | no |
| Owner signing key | no | yes | public key only | public key only |
| Plaintext keywords / files | yes (own query; decrypted results) | yes | **never** | no |
| Ciphertexts `CT_d` | results only | — | all (DHT) | no |
| Index (postings by `h_w`, PAPC, IMT, partition trees) | no | trusted metadata in the Validator (`Doc`, `Loc`, `Fwd`, roots) | yes | no |
| `(e*, R_D)` per domain, `R_G` | reads it from the anchor | reads / submits | reads | stores |

What the server sees of a query: `{domain, B_Q (tree of 32-byte h_w), epoch, t, nonce, τ_Q}`. No keyword text.

## 3. Gaps, ambiguities and stubs

Items 1–4 change what the demo can claim. Items 5–11 are wiring decisions.

1. **Query verification uses the Domain Root, not the Global Root.**
   `DataUser.verify` rebuilds `R_D = H(i ‖ e ‖ R^part ‖ R^idx)` and compares it with the anchored `R_D`
   (`amtp/user.py:132`). `R_G` is computed by the anchor (`amtp/anchor.py:66`) but no verifier uses it; the
   paper says `R_G` is for audit only. The spec's "Partition → Domain → Global root, compare with the anchored
   Global Root" does not exist in the code or the paper.
   Proposed: user step 5–6 become "rebuild `R_D`, compare with the anchored `R_D`". The UI shows `R_G`
   separately, and the client recomputes it from the anchored Domain Roots as an audit display.

2. **NOT is not supported.** The parser accepts AND, OR, parentheses and quoted phrases only
   (`amtp/core/boolean.py`), and the server rejects anything else (`amtp/server.py:21`).
   Proposed: the UI says so; a query with NOT returns the parser's real error.

3. **No fuzzy search.** A misspelled keyword gives a different `h_w`. The code can prove the empty result:
   the server returns an IMT non-membership proof (`amtp/server.py:293`) and the user checks it
   (`amtp/user.py:147`). Scenario 3 will show that proof.

4. **"Partitions skipped" may be small for frequent keywords.** The proof covers every partition that holds any
   queried keyword. A rare keyword touches 1–2 partitions; a frequent one touches hundreds. The demo will show
   the measured "touched X of Y" as it is.

5. **Stand-ins already in the code**, to be labelled in the UI: Ed25519 for ABS, policy key wrap for CP-ABE,
   Python class for the blockchain anchor, in-memory DHT in one process.

6. **The code is single-process.** `make_query` takes an anchor object, `DataOwner` calls the server object
   directly. For separate processes the demo needs thin adapters, with no change to `amtp_code`:
   - `RemoteAnchor.latest()` — HTTP read from the anchor;
   - search — the token and the response are already JSON-safe;
   - update — requests and proposals contain raw bytes and tuples, so the demo needs a wire codec
     (demo-only, not in the paper).
   Proposed processes: **client** (Data User + Data Owner, holds `K_s` and the signing key), **server**
   (CloudServer + DHT), **anchor** (RootAnchor, so the client reads roots without trusting the server).

7. **Per-step server timing.** `CloudServer.search` does not expose the lookup / eval / proof / fetch split;
   `build_response(timing=)` does. The server adapter will pass a `respond=` wrapper that calls the real
   `build_response` with `timing=`. Network and serialization time is measured in the client around the HTTP call.

8. **Bulk loading.** `DataOwner.add_documents` runs a fully validated epoch per batch (about 130 ms per file),
   too slow for thousands of files. The benchmarks load in bulk (`Engine.insert` + one `commit`, owner-signed
   transition, `Validator.bootstrap`). Proposed: same bulk path at start-up; every update made during the demo
   runs the full Phase 2 protocol. Measured on this Mac for one domain of 5,000 real files: 9 s to read the
   CSV (once), 4 s to encrypt, 12 s to build the index, 3.5 s for the snapshot.

9. **Attacks.** `amtp/adversary.py` covers: hide one result, add a non-matching result, remove a posting entry,
   claim a keyword absent, forge a partition, stale epoch, replay, modified ciphertext, storage loss. It builds
   the response with the real builder on an altered view; it does not change stored state. Still to write in
   `demo_v2`:
   - scenario 4, tamper stored data: overwrite a ciphertext in the DHT replicas and change a posting entry in
     the server's snapshot;
   - 5c, answer from the wrong partition or the wrong domain;
   - 5e, a man-in-the-middle proxy process that changes the response bytes in transit.
   `adversary.py` is in the core package and is used by the tests and the benchmarks, but the old demo imports
   it too.

10. **Web stack.** FastAPI and uvicorn are not installed in `.venv`; Flask 3.1.3 is.

11. **Demo size and θ.** θ_max = 64, θ_min = 16 (paper values). To show a split, the demo inserts real files
    from the insert pool into one group until a partition passes 64; to show a merge it deletes files.

## 4. Decisions needed before coding

| # | Question | Proposed |
|---|---|---|
| A | Root shown in user steps 5–6 (gap 1) | Domain Root for the verdict; `R_G` as a separate audit display |
| B | Reuse `amtp/adversary.py` for the attacks it already has (gap 9) | Yes, plus new real mutations in `demo_v2` for scenario 4, 5c, 5e |
| C | Web stack (gap 10) | Install `fastapi`, `uvicorn`, `websockets` into `.venv`; or Flask + server-sent events with no new package |
| D | Dataset size at start-up (gap 8) | 4 domains × 5,000 files, about 1.5 min start-up |
| E | Processes (gap 6) | client, server, anchor, and the MITM proxy only when that attack is on |
