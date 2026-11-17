"""Cost of real CP-ABE (BSW07, Charm, SS512) for K_d, next to the policy key wrap stand-in.

    cd amtp_code && ../.venv/bin/python -m bench.cpabe_bench --out ../baselines/results/cpabe

For n attributes in {1, 2, 5, 10, 20} and an AND policy over all n (the user holds all n), it measures:
  setup_ms    DA Setup (once per domain)
  keygen_ms   KeyGen for a user with n attributes (once per user)
  enc_ms      C_Kd = CPABE.Enc(PK, K_d, A_d), the owner's cost per document (Phase 1, eq. 3)
  dec_ms      K_d = CPABE.Dec(SK, C_Kd), the user's cost per opened document (Phase 5, eq. 88)
  ck_bytes    size of C_Kd inside CT_d (canonical encoding, as stored)
Median over --reps runs after --warmup unrecorded runs. Not part of any search or verification
timing: CP-ABE runs only when a document is encrypted or decrypted.
"""
import argparse
import csv
import json
import os
import platform
import statistics as st
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amtp.core import cpabe                                    # noqa: E402
from amtp.core.crypto import AttributeAuthority, unwrap        # noqa: E402
from amtp.core.hashing import enc                              # noqa: E402

K_D = os.urandom(32)


def timed(fn, reps, warmup):
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1e3)
    return st.median(out)


def measure(make, n, reps, warmup):
    attrs = [f"attr{i:02d}" for i in range(n)]
    policy = " AND ".join(attrs)
    setup_ms = timed(make, max(3, reps // 5), 1)
    da = make()
    keygen_ms = timed(lambda: da.user_keys(attrs), reps, warmup)
    key = da.user_keys(attrs)
    enc_ms = timed(lambda: da.wrap(K_D, policy), reps, warmup)
    blob = da.wrap(K_D, policy)
    assert unwrap(blob, key) == K_D
    dec_ms = timed(lambda: unwrap(blob, key), reps, warmup)
    return dict(n_attrs=n, setup_ms=round(setup_ms, 4), keygen_ms=round(keygen_ms, 4),
                enc_ms=round(enc_ms, 4), dec_ms=round(dec_ms, 4), ck_bytes=len(enc(blob)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attrs", type=int, nargs="+", default=[1, 2, 5, 10, 20])
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--out", default="../baselines/results/cpabe")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for scheme, make in (("BSW07 (SS512)", cpabe.CpAbeAuthority), ("policy key wrap (stand-in)", AttributeAuthority)):
        for n in a.attrs:
            r = dict(scheme=scheme, **measure(make, n, a.reps, a.warmup))
            print(r, flush=True)
            rows.append(r)
    path = os.path.join(a.out, "cpabe_costs.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    here = os.path.dirname(os.path.abspath(__file__))
    git = lambda *c: subprocess.run(["git", *c], cwd=here, capture_output=True, text=True).stdout.strip()
    try:
        import charm
        charm_v = getattr(charm, "__version__", "unknown")
    except ImportError:
        charm_v = None
    manifest = dict(command=" ".join(sys.argv), git_commit=git("rev-parse", "HEAD"),
                    git_dirty=bool(git("status", "--porcelain", "--", ".")), reps=a.reps, warmup=a.warmup,
                    curve=cpabe.CURVE, charm=charm_v, python=sys.version.split()[0],
                    platform=platform.platform(), processor=platform.processor() or platform.machine(),
                    started=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(os.path.join(a.out, "cpabe_costs.manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("wrote", path)


if __name__ == "__main__":
    main()
