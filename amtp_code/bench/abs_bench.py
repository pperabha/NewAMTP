"""Cost of real ABS (Maji-Prabhakaran-Rosulek, Charm) for σ_op, next to the Ed25519 stand-in.

    cd amtp_code && ../.venv/bin/python -m bench.abs_bench --out ../baselines/results/abs

For n attributes in {1, 2, 5} and an AND policy over all n (the owner holds all n; the AMTP policy
'domain:Di AND role:owner' is n = 2), it measures:
  setup_ms    DA Setup (once per domain; t_max = 8)
  keygen_ms   AttrGen for an owner with n attributes (once per owner)
  sign_ms     σ_op = ABS.Sign(SK, H(U_op)): the DO's cost per request (eqs. 9, 11)
  verify_ms   ABS.Verify: paid by the CS (admission) and again by the validating DO, per request
  sig_bytes   size of σ_op (2 + l + t group elements, Charm serialisation + 2-byte length prefixes)
Reports the mean (decision #46: values are averaged over the runs) and the median of --reps runs
after --warmup unrecorded runs. --curves compares pairing groups (BN254 is the one used in AMTP).
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

from amtp.core import abs as A                                 # noqa: E402
from amtp.core.crypto import Ed25519Signer, sig_ok             # noqa: E402

MSG = os.urandom(32)                                           # H(U_op) is a 32-byte digest


def timed(fn, reps, warmup):
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(reps):
        t = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t) * 1e3)
    return st.mean(out), st.median(out)


def cols(name, mean_med):
    return {f"{name}_ms": round(mean_med[0], 4), f"{name}_ms_median": round(mean_med[1], 4)}


def measure_mpr(curve, n, reps, warmup):
    attrs = [f"attr{i:02d}" for i in range(n)]
    policy = " AND ".join(f'"{a}"' for a in attrs)
    row = dict(scheme=f"ABS MPR ({curve})", curve=curve, n_attrs=n)
    row.update(cols("setup", timed(lambda: A.AbsAuthority(curve=curve), max(3, reps // 5), 1)))
    da = A.AbsAuthority(curve=curve)
    pub = da.public(policy)
    row.update(cols("keygen", timed(lambda: da.attr_gen(attrs), reps, warmup)))
    key = da.attr_gen(attrs)
    row.update(cols("sign", timed(lambda: A.sign(pub, key, MSG, attrs), reps, warmup)))
    sig = A.sign(pub, key, MSG, attrs)
    assert A.verify(pub, MSG, sig) and not A.verify(pub, MSG + b"x", sig)
    row.update(cols("verify", timed(lambda: A.verify(pub, MSG, sig), reps, warmup)))
    rows, labels, t = A.span_program(policy)
    row.update(sig_bytes=len(sig), span_l=len(labels), span_t=t)
    return row


def measure_ed25519(reps, warmup):
    s = Ed25519Signer()
    row = dict(scheme="Ed25519 (stand-in)", curve="ed25519", n_attrs=0, setup_ms=0, setup_ms_median=0)
    row.update(cols("keygen", timed(Ed25519Signer, reps, warmup)))
    row.update(cols("sign", timed(lambda: s.sign(MSG), reps, warmup)))
    sig = s.sign(MSG)
    assert sig_ok(s.public, MSG, sig)
    row.update(cols("verify", timed(lambda: sig_ok(s.public, MSG, sig), reps, warmup)))
    row.update(sig_bytes=len(sig), span_l=0, span_t=0)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attrs", type=int, nargs="+", default=[1, 2, 5])
    ap.add_argument("--curves", nargs="+", default=[A.DEFAULT_CURVE])
    ap.add_argument("--reps", type=int, default=15)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--out", default="../baselines/results/abs")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for curve in a.curves:
        for n in a.attrs:
            r = measure_mpr(curve, n, a.reps, a.warmup)
            print(r, flush=True)
            rows.append(r)
    r = measure_ed25519(a.reps, a.warmup)
    print(r, flush=True)
    rows.append(r)
    path = os.path.join(a.out, "abs_costs.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    here = os.path.dirname(os.path.abspath(__file__))
    git = lambda *c: subprocess.run(["git", *c], cwd=here, capture_output=True, text=True).stdout.strip()
    try:
        from importlib.metadata import version
        charm_v = version("charm-crypto-framework")
    except Exception:
        charm_v = None
    manifest = dict(command=" ".join(sys.argv), git_commit=git("rev-parse", "HEAD"),
                    git_dirty=bool(git("status", "--porcelain", "--", ".")), reps=a.reps, warmup=a.warmup,
                    statistic="mean (and median)", curves=a.curves, t_max=A.T_MAX, charm=charm_v,
                    python=sys.version.split()[0], platform=platform.platform(),
                    processor=platform.processor() or platform.machine(), cpus=os.cpu_count(),
                    started=time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(os.path.join(a.out, "abs_costs.manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print("->", path)


if __name__ == "__main__":
    main()
