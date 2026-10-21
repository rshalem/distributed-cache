import time

from cache_logic.cache import Cache
from cache_logic.consistent_hashing import HashRing


def test_lru_eviction_removes_least_recent():
    c = Cache(capacity=2)
    c.set("a", "1")
    c.set("b", "2")
    c.get("a")            # a becomes most recent
    c.set("c", "3")       # evicts b
    assert c.get("b") is None
    assert c.get("a") == "1"
    assert c.get("c") == "3"
    assert len(c) == 2


def test_eviction_with_and_without_ttl():
    c = Cache(capacity=1)
    c.set("a", "1")                 # no TTL
    c.set("b", "2", ttl=60)         # evicts a (previously KeyError)
    c.set("c", "3")                 # evicts b, which had a TTL
    assert c.get("c") == "3"
    assert "b" not in c.ttl_map


def test_delete_key_without_ttl():
    c = Cache()
    c.set("a", "1")
    assert c.delete("a") is True
    assert c.delete("a") is False


def test_ttl_expiry_lazy_and_background():
    c = Cache(cleanup_interval=0.1)
    c.set("lazy", "x", ttl=1)
    c.set("bg", "y", ttl=1)
    time.sleep(1.3)
    assert c.get("lazy") is None
    assert "bg" not in c.cache       # removed by cleaner thread


def test_update_resets_ttl():
    c = Cache()
    c.set("a", "1", ttl=1)
    c.set("a", "2", ttl=60)
    time.sleep(1.1)
    assert c.get("a") == "2"


def test_ring_returns_distinct_replicas():
    ring = HashRing(["n1", "n2", "n3"], vnodes=100)
    r = ring.get_replicas("user123", replication_factor=2)
    assert len(r) == 2 and len(set(r)) == 2


def test_ring_remaps_few_keys_on_node_add():
    ring = HashRing(["n1", "n2", "n3"], vnodes=100)
    keys = [f"k{i}" for i in range(5000)]
    before = {k: ring.get_replicas(k, 1)[0] for k in keys}
    ring.add_node("n4")
    moved = sum(before[k] != ring.get_replicas(k, 1)[0] for k in keys)
    assert moved / len(keys) < 0.35   # ~1/4 expected, vs ~3/4 with hash % N
