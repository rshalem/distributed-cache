import bisect
import hashlib
import logging
from typing import List

from cache_logic.config import REPLICATION_FACTOR, VIRTUAL_NODES

logger = logging.getLogger("hash-ring")


class HashRing:
    """
    Consistent hash ring with virtual nodes.

    Each real node is placed on the ring `vnodes` times (node:0, node:1, ...)
    so keys spread evenly and adding/removing a node only remaps ~1/N keys.
    Lookup is a binary search over the sorted vnode hashes: O(log V).
    """

    def __init__(self, nodes: List[str] = None, vnodes: int = VIRTUAL_NODES):
        self.vnodes = vnodes
        self.ring = {}          # vnode hash -> real node
        self.sorted_keys = []   # sorted vnode hashes (the ring)
        self.nodes = set()
        for n in nodes or []:
            self.add_node(n)

    @staticmethod
    def _hash(key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)

    def add_node(self, node: str):
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.vnodes):
            h = self._hash(f"{node}:{i}")
            self.ring[h] = node
            bisect.insort(self.sorted_keys, h)

    def remove_node(self, node: str):
        if node not in self.nodes:
            return
        self.nodes.discard(node)
        for i in range(self.vnodes):
            h = self._hash(f"{node}:{i}")
            if self.ring.pop(h, None) is not None:
                idx = bisect.bisect_left(self.sorted_keys, h)
                del self.sorted_keys[idx]

    def get_replicas(self, key: str, replication_factor: int = REPLICATION_FACTOR) -> List[str]:
        """
        Walk clockwise from the key's position and collect the first
        `replication_factor` distinct real nodes. replicas[0] is the primary.
        """
        if not self.ring:
            return []
        target = min(replication_factor, len(self.nodes))
        start = bisect.bisect(self.sorted_keys, self._hash(key))
        replicas = []
        for i in range(len(self.sorted_keys)):
            node = self.ring[self.sorted_keys[(start + i) % len(self.sorted_keys)]]
            if node not in replicas:
                replicas.append(node)
                if len(replicas) == target:
                    break
        logger.debug(f"replicas for key '{key}': {replicas}")
        return replicas
