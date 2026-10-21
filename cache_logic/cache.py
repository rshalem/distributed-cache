"""
Thread-safe LRU cache with per-key TTL.

- Hash map (key -> Node) gives O(1) lookup.
- Doubly linked list keeps recency order: most recently used right after
  `head`, least recently used right before `tail`. Move-to-front and
  evict-from-tail are both O(1).
- A background daemon thread wakes every second and removes expired keys.
  Expired keys are also removed lazily on `get`.
- One lock guards all state. It is NOT re-entrant, so internal helpers
  (`_delete_unlocked`, `_remove`, `_insert`) assume the caller holds it.
"""
import logging
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("cache-node")


class Node:
    """Doubly linked list node."""

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class Cache:
    def __init__(self, capacity=500, cleanup_interval=1.0):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.cache = {}    # key -> Node
        self.ttl_map = {}  # key -> absolute expiry time (only keys with a TTL)
        self.lock = threading.Lock()
        self.cleanup_interval = cleanup_interval

        # Dummy head/tail so insert/remove never deal with None neighbours.
        self.head, self.tail = Node(None, None), Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head

        # Start the cleaner only after all state exists.
        threading.Thread(target=self._cleaner, daemon=True).start()

    # ---------- public API ----------

    def set(self, key, value, ttl=None):
        """Insert or update a key. ttl in seconds; None or 0 means no expiry."""
        with self.lock:
            if key in self.cache:
                node = self.cache[key]
                node.value = value
                self._remove(node)
                self._insert(node)
            else:
                if len(self.cache) >= self.capacity:
                    lru = self.tail.prev
                    self._delete_unlocked(lru.key)
                    logger.info(f"EVICT key='{lru.key}' (LRU, capacity={self.capacity})")
                node = Node(key, value)
                self._insert(node)
                self.cache[key] = node

            # Every write resets the TTL; a write without TTL clears it.
            if ttl:
                self.ttl_map[key] = time.time() + ttl
            else:
                self.ttl_map.pop(key, None)
            logger.info(f"SET key='{key}' ttl={ttl}")

    def get(self, key):
        """Return the value, or None if missing or expired. Marks key as MRU."""
        with self.lock:
            node = self.cache.get(key)
            if node is None:
                return None
            if self._is_expired(key, time.time()):
                self._delete_unlocked(key)
                return None
            self._remove(node)
            self._insert(node)
            return node.value

    def delete(self, key):
        """Remove a key. Returns True if it existed."""
        with self.lock:
            return self._delete_unlocked(key)

    def __len__(self):
        with self.lock:
            return len(self.cache)

    # ---------- internals (caller holds self.lock) ----------

    def _is_expired(self, key, now):
        expiry = self.ttl_map.get(key)
        return expiry is not None and now > expiry

    def _delete_unlocked(self, key):
        node = self.cache.pop(key, None)
        if node is None:
            return False
        self._remove(node)
        self.ttl_map.pop(key, None)
        return True

    def _remove(self, node):
        """Unlink a node from the list."""
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = node.next = None

    def _insert(self, node):
        """Insert a node right after head (most recently used position)."""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def _cleaner(self):
        """Background thread: remove expired keys periodically."""
        logger.info("TTL cleaner started")
        while True:
            time.sleep(self.cleanup_interval)
            now = time.time()
            with self.lock:
                expired = [k for k, exp in self.ttl_map.items() if now > exp]
                for key in expired:
                    self._delete_unlocked(key)
            for key in expired:
                logger.info(f"EXPIRE key='{key}'")
