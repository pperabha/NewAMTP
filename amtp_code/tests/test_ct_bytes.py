"""CT_d is raw bytes: cid = H(CT bytes), the DHT stores and returns the same bytes,
and Phase 5 rejects a ciphertext with one flipped byte or a malformed encoding at b_ct."""
import json

import pytest

from amtp.core.crypto import CT_MAGIC, make_ct, unpack_ct
from amtp.core.hashing import H
from amtp.dht import DHT, StorageError, ciphertext_id
from amtp.scenario import World
from amtp.adversary import flip_one_byte


def test_ct_is_bytes_and_cid_hashes_the_raw_bytes():
    ct = make_ct(b"k" * 32, b"hello", {"t": "none"}, {"domain": "A", "doc": "d1"})
    assert isinstance(ct, bytes) and ct.startswith(CT_MAGIC)
    assert ciphertext_id(ct) == H(ct)
    parsed = unpack_ct(ct)
    assert parsed["aad"] == {"domain": "A", "doc": "d1"}
    with pytest.raises(TypeError):
        ciphertext_id({"E": "not bytes"})


@pytest.mark.parametrize("bad", [b"", b"AMTP-CT1", b"XXXX-CT1" + b"\0" * 16, b"AMTP-CT1\0\0\0\x09abc"])
def test_malformed_ct_does_not_parse(bad):
    with pytest.raises(ValueError):
        unpack_ct(bad)


def test_trailing_bytes_are_rejected():
    ct = make_ct(b"k" * 32, b"x", {"t": "none"}, {"domain": "A", "doc": "d"})
    with pytest.raises(ValueError):
        unpack_ct(ct + b"\0")


def test_dht_returns_stored_bytes_and_deletes():
    dht = DHT()
    ct = make_ct(b"k" * 32, b"body", {"t": "none"}, {"domain": "A", "doc": "d"})
    cid = ciphertext_id(ct)
    dht.put(cid, ct)
    assert dht.get(cid) is ct                     # immutable bytes: no copy needed
    with pytest.raises(TypeError):
        dht.put(cid, bytearray(ct))
    dht.delete(cid)
    with pytest.raises(StorageError):
        dht.get(cid)


def test_dht_skips_a_corrupted_replica():
    dht = DHT()
    ct = make_ct(b"k" * 32, b"body", {"t": "none"}, {"domain": "A", "doc": "d"})
    cid = ciphertext_id(ct)
    dht.put(cid, ct)
    first = dht.replica_nodes(cid)[0]
    dht.store[first][cid] = bytes.fromhex(flip_one_byte(ct.hex()))
    assert dht.get(cid) == ct


def _honest(w):
    user = w.users["mali"]
    domain = sorted(user.domain_keys)[0]
    t_q, ctx = user.make_query(domain, "insulin OR diabetes", w.anchor)
    resp = json.loads(json.dumps(w.server.search(t_q)["response"]))
    assert user.verify(ctx, json.loads(json.dumps(resp)))["accepted"] and resp["R_ct"]
    return user, ctx, resp


@pytest.mark.parametrize("index", [0, 8, 40, -1])
def test_one_flipped_byte_is_caught_by_b_ct(index):
    user, ctx, resp = _honest(World())
    resp["R_ct"][0]["ct"] = flip_one_byte(resp["R_ct"][0]["ct"], index)
    rep = user.verify(ctx, resp)
    assert not rep["accepted"] and rep["failed"] == "ct"


@pytest.mark.parametrize("value", ["zz", "", None, 5])
def test_malformed_ct_field_is_rejected_at_b_ct(value):
    user, ctx, resp = _honest(World())
    resp["R_ct"][0]["ct"] = value
    rep = user.verify(ctx, resp)
    assert not rep["accepted"] and rep["failed"] == "ct"
