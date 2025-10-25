import bisect, hashlib
import logging
from typing import List
from cache_logic.config import VIRTUAL_NODES, REPLICATION_FACTOR

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbosity
    format="%(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("hash-ring")

class HashRing:
    """
    Consistent hash ring with virtual replicas (replicas parameter).
    Nodes are strings like "127.0.0.1:8001".
    """
    def __init__(self, nodes: List[str] = None, vnodes: int = VIRTUAL_NODES):
        self.vnodes = vnodes          # virtual nodes per real node (for distribution), just reference for real nodes
        self.ring = {}                # map: vnode_hash -> node
        self.sorted_keys = []         # sorted list of vnode_hashes
        if nodes:                     # actual nodes to be there on ring with cache data
            for n in nodes:
                self.add_node(n)
    
    def _get_hash_val(self, key):
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)
    
    def add_node(self, node):
        """
        Adds hashed node to the ring
        Each node gets 100 vNodes (default). Each pointing to current main node
        """
        for i in range(self.vnodes):
            # 105418963916085178198107114039827826184948299117374288074204493484117044635428 of nodeA
            node_hash = self._get_hash_val(f"{node}:{i}") # nodeA:0, nodeA:1, nodeA:3 hashed
            self.ring[node_hash] = node # {'nodeA:1 hashed': 'nodeA', 'nodeB:1 hashed': 'nodeB'}
            # insert item x in list a, and keep it sorted assuming a is sorted.
            # if x is already in a, insert it to the right of the rightmost x.
            bisect.insort(self.sorted_keys, node_hash) # 100 vnodes sorted for easy node lookup

    def get_replicas(self, key, replication_factor=REPLICATION_FACTOR):
        """
        Return list of distinct nodes responsible for this key
        get_replicas() walks across vNodes,
        but returns real nodes (the replicas).
        """
        if not self.ring:
            return []
        # key hashed
        key_hash = self._get_hash_val(key)
        # start finds where the key’s hash would fit in the sorted ring.
        start_idx = bisect.bisect(self.sorted_keys, key_hash)
        # from here start looking for our key in ring among vnodes clockwise
        replicas = []
        i = 0
        while len(replicas) < replication_factor and i < len(self.sorted_keys):
            hash_ring_vnode = self.sorted_keys[(start_idx + i) % len(self.sorted_keys)] # always wrap around if start_idx becomes > to run clockwise
            actual_node_where_key_stored = self.ring[hash_ring_vnode] # gives actual node like nodeA from a vnode of nodeA
            if actual_node_where_key_stored not in replicas: # not costly as only 3 replicas will be there at max
                replicas.append(actual_node_where_key_stored)
            i += 1
        logger.info(f"replicas for key: {key} are: {replicas}")
        return replicas