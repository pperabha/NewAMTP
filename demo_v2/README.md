# AMTP demo v2

A live demo of the AMTP flow on the real code (`amtp_code/`) and the real dataset (dataset-v4, arXiv).
γ keeps the partition version: `γ = H(PID ‖ v ‖ H(Enc(L)))`. The demo refuses to start with `AMTP_GAMMA_V=0`.

Nothing in `amtp_code/` or `baselines/` is changed. Everything here is adapters, a wire format and a page.

## Run

```bash
./demo_v2/run_demo.sh
```

Opens `http://127.0.0.1:8102`. The default loads 4 domains × 5,000 real files and takes about 1.5 minutes;
the page shows the progress. For a rehearsal:

```bash
./demo_v2/run_demo.sh --files-per-domain 500
```

Other flags: `--domains D1,D2`, `--base-port 8101`, `--no-browser`. Stop with Ctrl-C.

Real CP-ABE instead of the policy key wrap (BSW07 in Charm, SS512; needs Charm, see `baselines/README.md`):

```bash
AMTP_CPABE=bsw07 ./demo_v2/run_demo.sh
```

Encrypting with CP-ABE costs about 10 ms per file on a Mac (Intel), so 4 × 5,000 files add about 3–4 minutes
to the start; `--files-per-domain 500` starts in seconds. The CP-ABE line then disappears from the stand-ins
at the top of the page.

First time only (already done in this checkout's `.venv`):

```bash
.venv/bin/python -m pip install -r demo_v2/requirements.txt
```

Tests (four real processes on a 300-file prefix of two domains, about 25 s):

```bash
.venv/bin/python -m pytest demo_v2/tests -q
```

## Architecture

Four separate processes that talk over HTTP. The browser page is served by the client process and also
opens WebSockets to the server, the network path and the anchor, so each panel shows its own process.

```
                      reads (e*, R_D)                 submits signed roots
        ┌──────────────────────────────┐   ┌──────────────────────────────────┐
        │                              ▼   ▼                                  │
 ┌──────┴───────────────┐      ┌───────────────────┐                          │
 │ CLIENT  :8102        │      │ ROOT ANCHOR :8103 │                          │
 │ Data User            │      │ amtp.anchor       │                          │
 │  amtp.user.DataUser  │      │ (Python class,    │                          │
 │ Data Owners          │      │  not a blockchain)│                          │
 │  amtp.owner.DataOwner│      └───────────────────┘                          │
 │  amtp.validator      │                                                     │
 │ holds K_s, K_a,      │  search   ┌────────────────────┐  search  ┌─────────┴──────────┐
 │ signing + attr keys  ├──────────►│ NETWORK PATH :8104 ├─────────►│ CLOUD SERVER :8101 │
 │                      │◄──────────┤ forwards; can alter│◄─────────┤ amtp.server        │
 │                      │           │ the response (5e)  │          │ amtp.engine, DHT   │
 │                      │  update protocol (prepare / abort / finalize)                  │
 │                      ├───────────────────────────────────────────►│ + attack switch    │
 └──────────────────────┘                                            │ holds K_a, public  │
                                                                     │ keys, ciphertexts  │
                                                                     └────────────────────┘
```

| File | Role |
|---|---|
| `client_app.py` | Data User and Data Owners. `RemoteAnchor` / `RemoteServer` give the real `DataOwner` and `DataUser` the method names they call, over HTTP |
| `server_app.py` | `CloudServer` behind HTTP, live events, the attack switch |
| `anchor_app.py` | `RootAnchor` behind HTTP |
| `mitm_app.py` | The network path between client and server |
| `attacks.py` | The attacks `amtp/adversary.py` does not have |
| `common.py` | Import paths, the wire format (`pack` / `unpack`), HTTP helper, event hub |
| `run_demo.py`, `run_demo.sh` | Launcher |
| `static/index.html` | The page |
| `CODE_MAP.md` | Paper phase → file and function in `amtp_code` |

## The page

**Data User (left).** Search box (Enter to run), a domain selector (one domain or all), example buttons built
from the loaded data, the verdict badge, the user-side steps with their measured times, the decrypted
results, and the Data Owner's update buttons.

The user-side steps are: parse the query → read `(e*, R_D)` from the Root Anchor → build the keyword tokens
and the tag → send and receive → run the seven checks → **rebuild the Domain Root and compare it with the
anchored `R_D`** → decrypt, only if accepted.

**Cloud Server (middle).** Fills from the server's own event stream when a query arrives: the token as the
server sees it (opaque 32-byte keys), admission, partitions touched and skipped, the search, the proof tree
(`R_D` → `R^part` and `R^idx` → partition roots, touched ones highlighted), and the time of each server step.
The adversary controls are here.

**Proof & verification (right).** The anchored Domain Root and where it came from, the rebuilt root, the
seven checks with pass or fail and the reason, the proof size, the number of hashes the client computed,
the evidence per keyword, and the partitions in the proof. `R_G` is shown below as an audit value.

**Bottom.** A table of this session's searches.

## Scenarios

| # | How to run it | What to expect |
|---|---|---|
| 1 | Example "Rare keyword" or "Frequent keyword" | VERIFIED. Rare: 1 partition in the proof; frequent: most of them |
| 2 | Examples "Boolean, 12 keywords" and "Boolean, 20 keywords"; choose "All domains" | VERIFIED; the bottom table shows how time and proof size grow |
| 3 | Example "Misspelled keyword" | VERIFIED with 0 files: the proof panel shows the non-membership proof (`h_lo < h_w < next(h_lo)`) |
| 4 | Server behaviour → "Tamper a stored ciphertext…" or "Tamper a posting entry…", then search | REJECTED at ciphertext integrity, or at PAPC. The damage stays until "Restore tampered stored data" |
| 5a | "Hide one matching file", "Remove an entry from a keyword's posting list", "Claim a keyword does not exist" | REJECTED at exact Boolean result, PAPC, index evidence |
| 5b | "Add a file that does not match", "Forge a partition's content" | REJECTED at exact Boolean result, partition authentication |
| 5c | "Answer with another partition's root and proof", "Answer from another domain's index" | REJECTED at PAPC or partition authentication; at anchored snapshot |
| 5d | "Answer from an old epoch", "Replay an earlier response" | REJECTED at anchored snapshot; at query context |
| 5e | Network path → any man-in-the-middle mode | REJECTED; the server panel shows the server itself was honest |
| 6 | Owner buttons: insert, delete, "Insert until a partition splits", "Delete until a partition merges", then "Check my previous response…" | Each epoch is anchored; only that domain's root changes; a new search verifies; the previous response is rejected |

## Honesty notes

What is real:

- Every search, proof and verification calls the functions of `amtp_code`: `DataUser.make_query`,
  `CloudServer.search` → `build_response`, `DataUser.verify`, `DataUser.decrypt`.
- The verdict comes only from `DataUser.verify` in the client process. The server's reply has no verdict
  field, and the client is never sent the attack mode (a test checks both).
- Updates during the demo run `DataOwner.update`: signed requests, `CloudServer.prepare_update`,
  `Validator.check`, `RootAnchor.submit`, `finalize_update`.
- Every attack changes real data: the stored bytes, the stored index, the response the server builds, or
  the response bytes in transit.
- All times are `time.perf_counter_ns()` around the real calls. There is no `sleep` in the demo processes
  (the launcher and the test harness poll while waiting for start-up).
- The dataset is dataset-v4. Example queries are built from the loaded files at start-up.

Stand-ins and limits:

1. **Ed25519 stands in for ABS**, a **policy key wrap stands in for CP-ABE** (unless `AMTP_CPABE=bsw07`), the **Root Anchor is a Python
   class in its own process, not a blockchain**, and the **DHT is in memory inside the server process**.
   These are the stand-ins of `amtp_code` itself; the page lists them at the top.
2. **Verification is against the Domain Root.** `R_G` is not used to accept a result, in the code or in the
   paper. The client recomputes `R_G` from the anchored Domain Roots with the anchor's own formula and shows
   whether it matches; that is an audit display.
3. **No NOT, no fuzzy search.** The query language is AND, OR, parentheses and quoted phrases. A query with
   NOT returns the parser's error.
4. **Start-up uses the bulk path**, like the benchmarks: every file is encrypted for real, indexed with
   `Engine.insert` and one `commit`, and anchored with one owner-signed transition per domain. The owner
   builds its own copy of the index, checks that the server's root equals its own, and takes its trusted
   metadata from it (`Validator.bootstrap`). The page shows this and the time it took.
5. **The server's time is the server's own report.** "Network" is the client's measured round trip minus
   that report, so it includes the network-path process and JSON handling inside the server framework.
6. **Per-step server times exist only for an honest server.** While an attack of `amtp/adversary.py` is
   active the server reports its total only.
7. **"Hashes checked"** is the client's `HashCounter` difference around `verify`.
8. **Partition selection is shown as measured.** A frequent keyword is in most partitions, so few are skipped.
9. **The split and merge buttons choose which real files to insert or delete** from the server's public
   layout (group sizes), so that the threshold is reached quickly. The split and the merge themselves are
   decided by the server's policy and validated by the owner.
10. **Finalizing an update takes seconds** at 5,000 files per domain because the prototype rebuilds the
    whole query snapshot (`Engine.snapshot`). The page shows it as "server finalizes".
11. **All searches go through the network-path process**, also when it is set to forward unchanged, so the
    client cannot tell from its configuration whether a man in the middle is active.
12. **The wire format** (`common.pack`) is demo-only. It carries the real update requests and proposals
    between processes with their types intact; it is not part of the paper.
13. **One access policy** (`auditor`) protects every demo file, and the demo user holds that attribute.
14. `K_a` is on the server by design (it checks the query tag). `K_s`, plaintext keywords, file keys and the
    owners' private keys never leave the client process.

## Measured on the final run-through

MacBook, Python 3.12, 4 domains × 5,000 files (20,000 encrypted files, 452 partitions), domain D1 unless
stated. One run each; times vary from run to run.

Start-up: 92.5 s in total (16.2 s reading the dataset file; per domain about 5 s to encrypt and 8–9 s to
build the index).

| Scenario | Verdict | Partitions in proof | Files | Token | Server | Verify | Proof | Hashes checked |
|---|---|---|---|---|---|---|---|---|
| 1 Rare keyword | VERIFIED | 1 / 109 | 1 | 0.31 ms | 0.38 ms | 1.07 ms | 1.2 KB | 41 |
| 1 Frequent keyword | VERIFIED | 97 / 109 | 284 | 0.13 ms | 4.39 ms | 18.6 ms | 51.6 KB | 2,517 |
| 2 AND of two | VERIFIED | 1 / 109 | 1 | 0.29 ms | 0.31 ms | 0.56 ms | 1.8 KB | 64 |
| 2 Boolean, 12 keywords | VERIFIED | 7 / 109 | 3 | 0.55 ms | 1.04 ms | 2.83 ms | 11.1 KB | 401 |
| 2 Boolean, 20 keywords | VERIFIED | 109 / 109 | 1,825 | 0.63 ms | 30.8 ms | 85.6 ms | 212 KB | 14,086 |
| 2 Boolean, 20 keywords, all 4 domains | VERIFIED | 444 / 452 | 6,540 | 2.63 ms | 92.0 ms | 299 ms | 748 KB | 49,790 |
| 3 Misspelled keyword | VERIFIED, proven absent | 0 / 109 | 0 | 0.13 ms | 0.16 ms | 0.30 ms | 704 B | 20 |

| Attack | Verdict | Check that failed |
|---|---|---|
| 4 Tamper a stored ciphertext | REJECTED | ciphertext integrity |
| 4 Tamper a stored posting entry | REJECTED | PAPC |
| 5a Hide one matching file | REJECTED | exact Boolean result |
| 5a Remove a posting entry | REJECTED | PAPC |
| 5a Claim a keyword does not exist | REJECTED | index evidence |
| 5b Add a non-matching file | REJECTED | exact Boolean result |
| 5b Forge a partition's content | REJECTED | partition authentication |
| 5c Another partition's root and proof | REJECTED | partition authentication (PAPC when the versions differ) |
| 5c Another domain's index | REJECTED | anchored snapshot |
| 5d Old epoch | REJECTED | anchored snapshot |
| 5d Replay | REJECTED | query context |
| 5e Network: change a byte of a file | REJECTED | ciphertext integrity |
| 5e Network: remove a file | REJECTED | exact Boolean result |
| 5e Network: replace `R^idx` | REJECTED | anchored snapshot |

| Update on D1 | Epochs | Result | Last epoch: prepare / validate / anchor / finalize |
|---|---|---|---|
| Insert 1 file | 1 | 1 partition changed, 1,126 keyword commitments recomputed; D2–D4 roots unchanged | 196 / 114 / 3.4 / 3,357 ms |
| Delete that file | 1 | 1 partition changed | 204 / 105 / 2.4 / 3,438 ms |
| Insert until a split | 2 (16 files) | 2 splits; 109 → 111 partitions | 1,690 / 310 / 3.0 / 2,633 ms |
| Delete until a merge | 1 (3 files) | 1 merge; 111 → 110 partitions | 259 / 141 / 3.0 / 3,926 ms |

After the insert, the previous accepted response was rejected at query context (response epoch 1, anchored
epoch 2), and a new search verified. The recomputed `R_G` matched the anchor's after every step.
