"""End-to-end tests of demo_v2: four real processes, the real dataset (a small prefix), the real verifier.

    ../.venv/bin/python -m pytest demo_v2/tests -q

Nothing is mocked. A test passes only if amtp.user.DataUser.verify, running in the client process,
accepts an honest answer and rejects every tampered one.
"""
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import run_demo  # noqa: E402

FILES = 300


def free_base_port():
    for base in range(8301, 8900, 10):
        try:
            for p in range(base, base + 4):
                with socket.socket() as s:
                    s.bind(("127.0.0.1", p))
            return base
        except OSError:
            continue
    raise RuntimeError("no free ports")


def call(url, body=None, timeout=900):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "detail": e.read().decode("utf-8", "replace")}


@pytest.fixture(scope="session")
def demo():
    procs, urls = run_demo.start_stack(FILES, "D1,D2", free_base_port(), quiet=True)
    try:
        for _ in range(600):
            st = call(urls["client"] + "/api/status")
            if st["ready"] or st["error"]:
                break
            time.sleep(0.5)                                  # test harness only: wait for the bulk load
        assert st["ready"], st["error"]
        urls["examples"] = {e["label"]: e["query"] for e in st["examples"]["D1"]}
        urls["status"] = st
        yield urls
    finally:
        run_demo.stop_stack(procs)


@pytest.fixture(autouse=True)
def honest(demo):
    """Every test starts and ends with an honest server, an honest network and untampered storage."""
    def reset():
        call(demo["server"] + "/attack", {"mode": "honest"})
        call(demo["network"] + "/mitm", {"mode": "off"})
        call(demo["server"] + "/attack/restore", {})
    reset()
    yield
    reset()


def search(demo, query, domains=("D1",)):
    out = call(demo["client"] + "/api/search", {"query": query, "domains": list(domains)})
    assert "http_error" not in out, out
    return out


def last_attack(demo):
    return [e for e in call(demo["server"] + "/events?since=0") if e["kind"] == "query"][-1]["attack"]


# ---------------------------------------------------------------- set-up and honest searches
def test_real_dataset_and_bulk_path(demo):
    st = demo["status"]
    assert "arXiv" in st["dataset"]["name"]
    assert st["dataset"]["loaded"]["D1"]["files"] == FILES and st["dataset"]["totals"]["domains"] == 2
    assert "bulk" in st["startup"]["path"] and st["startup"]["D1"]["encrypt_ms"] > 0
    assert st["config"]["theta_max"] == 64 and st["config"]["theta_min"] == 16
    assert "‖ v ‖" in st["config"]["gamma"]
    assert "No NOT" in st["query_language"]
    assert {s["demo"] for s in st["stand_ins"]} >= {"Ed25519 signature", "Python class in its own process"}


@pytest.mark.parametrize("label", ["Rare keyword", "Frequent keyword", "AND of two", "Boolean, 12 keywords",
                                   "Boolean, 20 keywords"])
def test_honest_queries_verify(demo, label):
    run = search(demo, demo["examples"][label])["runs"][0]
    assert run["verdict"] == "VERIFIED" and run["result_count"] >= 1
    assert all(c["ok"] for c in run["checks"]) and len(run["checks"]) == 7
    assert run["results"][0]["status"] == "open" and run["results"][0]["snippet"]
    assert run["proof"]["rebuilt_R_D"] == run["anchored"]["R_D"]          # Domain Root, not Global Root
    assert run["proof"]["hashes_checked"] > 0 and run["sizes"]["proof_bytes"] > 0


def test_frequent_keyword_touches_more_partitions_than_rare(demo):
    rare = search(demo, demo["examples"]["Rare keyword"])["runs"][0]["proof"]
    freq = search(demo, demo["examples"]["Frequent keyword"])["runs"][0]["proof"]
    assert rare["partitions_touched"] < freq["partitions_touched"] <= freq["partitions_total"]


def test_evidence_counts_cover_pruned_keywords(demo):
    """Rare AND frequent: with AND pruning on (default) the frequent keyword arrives as focus evidence (segs + nb, no L).
    The panels must still count what it carries instead of showing 0 partitions / 0 entries."""
    q = f'{demo["examples"]["Rare keyword"]} AND {demo["examples"]["Frequent keyword"]}'
    run = search(demo, q)["runs"][0]
    assert run["verdict"] == "VERIFIED"
    rows = [e for e in run["proof"]["evidence"] if e["status"] == "present"]
    assert len(rows) == 2
    for e in rows:
        assert e["of"] >= 1 and e["partitions"] + e["neighbours"] >= 1, e
        assert e["partitions"] <= e["of"] and (e["entries"] >= 1) == (e["partitions"] >= 1), e
        if not e["pruned"]:
            assert e["partitions"] == e["of"] and e["neighbours"] == 0, e
    server_rows = [e for e in last_query_event(demo)["evidence"] if e["status"] == "present"]
    assert sorted((e["partitions"], e["entries"], e["pruned"]) for e in server_rows) == \
        sorted((e["partitions"], e["entries"], e["pruned"]) for e in rows)
    if os.environ.get("AMTP_AND_PRUNE", "1") != "0":
        assert any(e["pruned"] for e in rows), rows
    else:
        assert not any(e["pruned"] for e in rows), rows


def last_query_event(demo):
    return [e for e in call(demo["server"] + "/events?since=0") if e["kind"] == "query"][-1]


def test_misspelled_keyword_is_proven_absent(demo):
    run = search(demo, demo["examples"]["Misspelled keyword"])["runs"][0]
    assert run["verdict"] == "VERIFIED" and run["result_count"] == 0
    ev = run["proof"]["evidence"][0]
    assert ev["status"] == "absent" and ev["bracket"]["lo"] and ev["proof_hashes"] > 0
    assert "proven absent" in next(c["detail"] for c in run["checks"] if c["key"] == "idx")


def test_all_domains_one_query_per_domain(demo):
    out = search(demo, demo["examples"]["Frequent keyword"], ("D1", "D2"))
    assert [r["domain"] for r in out["runs"]] == ["D1", "D2"] and out["summary"]["verdict"] == "VERIFIED"
    assert out["runs"][0]["anchored"]["R_D"] != out["runs"][1]["anchored"]["R_D"]
    assert out["audit"]["match"] and "audit value only" in out["audit"]["note"]


def test_not_is_refused_not_emulated(demo):
    out = call(demo["client"] + "/api/search", {"query": "algorithm AND NOT paper", "domains": ["D1"]})
    assert out["http_error"] == 400


def test_server_sees_no_keyword_text(demo):
    word = demo["examples"]["Rare keyword"].strip('"')
    search(demo, demo["examples"]["Rare keyword"])
    ev = [e for e in call(demo["server"] + "/events?since=0") if e["kind"] == "query"][-1]
    assert word not in json.dumps(ev) and re.fullmatch(r"[0-9a-f]{8}…", ev["token"]["B_Q"])


# ---------------------------------------------------------------- attacks (scenario 4 and 5)
SERVER_ATTACKS = {                 # mode -> the Phase 5 check(s) that may catch it
    "drop_result": {"comp"},                       # 5a omission
    "hide_posting": {"papc"},                      # 5a omission in the index
    "false_absent": {"idx"},                       # 5a claims the keyword does not exist
    "extra_result": {"comp"},                      # 5b injection
    "forge_partition": {"part"},                   # 5b forged partition content
    "wrong_partition": {"papc", "part"},           # 5c
    "wrong_domain": {"anchor"},                    # 5c
    "stale": {"anchor"},                           # 5d
    "replay": {"ctx"},                             # 5d
    "tamper_ct": {"ct"},                           # modified file
    "tamper_store_ct": {"ct"},                     # scenario 4
    "tamper_store_index": {"papc"},                # scenario 4
}


@pytest.mark.parametrize("mode", sorted(SERVER_ATTACKS))
def test_server_attack_is_rejected(demo, mode):
    q = demo["examples"]["Frequent keyword"]
    assert search(demo, q)["runs"][0]["verdict"] == "VERIFIED"           # honest first (also feeds the replay)
    call(demo["server"] + "/attack", {"mode": mode})
    out = search(demo, q)
    run = out["runs"][0]
    assert last_attack(demo)["applied"], last_attack(demo)
    assert run["verdict"] == "REJECTED" and run["failed"] in SERVER_ATTACKS[mode], (mode, run["failed"], run["reason"])
    assert run["results"] == [] and run["timing"]["decrypt_ms"] is None    # nothing is decrypted
    assert "attack" not in json.dumps(out)                                 # the client is never told


def test_stored_tamper_persists_until_restored(demo):
    q = demo["examples"]["Frequent keyword"]
    call(demo["server"] + "/attack", {"mode": "tamper_store_index"})
    assert search(demo, q)["runs"][0]["failed"] == "papc"
    call(demo["server"] + "/attack", {"mode": "honest"})                   # an honest server, damaged index
    assert search(demo, q)["runs"][0]["failed"] == "papc"
    assert call(demo["server"] + "/attack/restore", {})["restored"] == 1
    assert search(demo, q)["runs"][0]["verdict"] == "VERIFIED"


def test_honest_server_refuses_to_serve_a_damaged_file(demo):
    q = demo["examples"]["Frequent keyword"]
    call(demo["server"] + "/attack", {"mode": "tamper_store_ct"})
    assert search(demo, q)["runs"][0]["failed"] == "ct"
    call(demo["server"] + "/attack", {"mode": "honest"})
    run = search(demo, q)["runs"][0]
    assert run["verdict"] == "NO ANSWER" and "replica" in run["reason"]


@pytest.mark.parametrize("mode,check", [("flip_ct", "ct"), ("drop_result", "comp"), ("rewrite_root", "anchor")])
def test_man_in_the_middle_is_rejected(demo, mode, check):                # 5e
    call(demo["network"] + "/mitm", {"mode": mode})
    run = search(demo, demo["examples"]["Frequent keyword"])["runs"][0]
    assert call(demo["network"] + "/mitm")["last"]["applied"]
    assert run["verdict"] == "REJECTED" and run["failed"] == check
    assert last_attack(demo)["mode"] == "honest"                           # the server itself was honest


def test_storage_loss_gives_no_answer(demo):
    call(demo["server"] + "/attack", {"mode": "storage_loss"})
    assert search(demo, demo["examples"]["Frequent keyword"])["runs"][0]["verdict"] == "NO ANSWER"


# ---------------------------------------------------------------- updates (scenario 6)
def test_update_split_merge_and_old_proofs(demo):
    q, c = demo["examples"]["Frequent keyword"], demo["client"]
    assert search(demo, q)["runs"][0]["verdict"] == "VERIFIED"
    before = call(demo["anchor"] + "/state")

    ins = call(c + "/api/owner/insert", {"domain": "D1", "count": 1})
    ep = ins["epochs"][0]
    assert ins["ok"] and ep["domains_changed"] == ["D1"] and ep["domains_unchanged"] == ["D2"]
    assert ep["R_old"] != ep["R_new"] and ep["R_G_before"] != ep["R_G_after"]
    assert ep["stats"]["partitions_changed"] == 1 and ep["timing"]["validate_ms"] > 0
    after = call(demo["anchor"] + "/state")
    assert after["domains"]["D1"]["epoch"] == before["domains"]["D1"]["epoch"] + 1
    assert after["domains"]["D1"]["R_D"] == ep["R_new"] and after["domains"]["D2"] == before["domains"]["D2"]

    old = call(c + "/api/reverify", {"domain": "D1"})                      # the pre-update response
    assert not old["accepted"] and old["failed"] == "ctx"
    assert search(demo, q)["runs"][0]["verdict"] == "VERIFIED"             # a fresh search verifies
    call(demo["server"] + "/attack", {"mode": "stale"})                    # the server serves the old snapshot
    assert search(demo, q)["runs"][0]["failed"] == "anchor"
    call(demo["server"] + "/attack", {"mode": "honest"})

    assert call(c + "/api/owner/delete", {"domain": "D1"})["ok"]

    sp = call(c + "/api/owner/split", {"domain": "D1"})
    assert sp["ok"] and sp["splits"] >= 1 and sp["epochs"][-1]["structure"][0][0] == "split"
    assert sp["plan"]["theta_max"] == 64 and sp["audit"]["match"]
    assert search(demo, q)["runs"][0]["verdict"] == "VERIFIED"

    mg = call(c + "/api/owner/merge", {"domain": "D1"})
    assert mg["ok"] and mg["merges"] >= 1 and mg["epochs"][-1]["structure"][0][0] == "merge"
    assert search(demo, q, ("D1", "D2"))["summary"]["verdict"] == "VERIFIED"


# ---------------------------------------------------------------- honesty of the numbers
def test_timings_are_measured(demo):
    small = search(demo, demo["examples"]["Rare keyword"])["runs"][0]
    big = search(demo, demo["examples"]["Boolean, 20 keywords"])["runs"][0]
    again = search(demo, demo["examples"]["Boolean, 20 keywords"])["runs"][0]
    for run in (small, big, again):
        t = run["timing"]
        assert all(t[k] > 0 for k in ("token_ms", "server_ms_reported", "verify_ms", "decrypt_ms"))
        assert t["network_ms"] >= 0
    assert big["timing"]["verify_ms"] != again["timing"]["verify_ms"]      # not a constant
    assert big["proof"]["hashes_checked"] == again["proof"]["hashes_checked"]   # the work is the same
    assert big["proof"]["hashes_checked"] > small["proof"]["hashes_checked"]
    assert big["sizes"]["proof_bytes"] > small["sizes"]["proof_bytes"]


def test_no_sleep_and_no_canned_verdict_in_the_demo_code():
    for name in ("server_app.py", "client_app.py", "anchor_app.py", "mitm_app.py", "attacks.py", "common.py"):
        src = open(os.path.join(HERE, name), encoding="utf-8").read()
        assert "sleep(" not in src, name
    client = open(os.path.join(HERE, "client_app.py"), encoding="utf-8").read()
    assert "self.user.verify(ctx, resp)" in client                         # the verdict comes from the real verifier
    server = open(os.path.join(HERE, "server_app.py"), encoding="utf-8").read()
    assert '"accepted"' not in server and '"verdict"' not in server        # the server sends no verdict


def test_core_code_is_untouched():
    """demo_v2 only adds files; amtp_code has no uncommitted change."""
    import subprocess
    out = subprocess.run(["git", "status", "--porcelain", "--", "amtp_code", "baselines"],
                         cwd=os.path.dirname(HERE), capture_output=True, text=True).stdout
    assert out.strip() == "", out
