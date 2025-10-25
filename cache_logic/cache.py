"""
threading will help me create a sub thread from main thread
that would run a cleanup task for deleting cache which reaches ttl

If you dont use threading, the main process (the one running FastAPI or the CLI) would block,
youd either have to manually call a cleanup function or let the cache leak memory indefinitely.

The cache object (self.cache, self.ttl_map) lives in Python memory.
Threads in the same process share memory, so the cleaner thread can directly access and modify those dictionaries.

when main thread is having a get operation on a key, and at the same time worker thread is running cleanup ttl task for same key
then it might cause inconsistency, hence we do self.lock to ensure main thread first completes it operation and then
allow others to execute

main thread
|
| -> sub thread
|

"""
import logging
import threading
import time

logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more verbosity
    format="%(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("cache-node")

class Node:
    # doubly linked list
    def __init__(self, key, value):
        self.key=key
        self.value=value
        self.next=self.prev=None

class Cache:
    def __init__(self, capacity=500):
        self.capacity = capacity # upper limit for nodes
        self.current_cache_size = 0 # for tracking real time node count
        self.cache = {} # will store key and value as node
        self.ttl_map = {} # will store key and their ttl
        self.lock = threading.Lock() # only one thread at a time can execute any code inside this block”
        # While one thread holds the lock, all other threads trying to acquire it must wait until it’s released.
        threading.Thread(target=self._cleaner, daemon=True).start() # creates worker thread and runs sef._cleaner method.
        
        self.head, self.tail = Node(0,0), Node(0,0) # dummy head and tail for ease
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def set(self, key, value, ttl=None):
        # only one thread at a time can execute any code inside this block
        with self.lock:
            # if current_cache_size >= self.capacity, remove LRU and then insert
            if key not in self.cache:
                if self.current_cache_size >= self.capacity: #remove LRU
                    node_to_evict = self.tail.prev
                    del self.cache[node_to_evict.key]
                    del self.ttl_map[key]
                    self.current_cache_size -= 1

                # insert
                node = Node(key, value)
                self._insert(node)
                self.current_cache_size += 1
                self.cache[key] = node
                if ttl:
                    self.ttl_map[key] = time.time() + ttl
                logger.info(f"[{node}] SET key='{key}' ttl={ttl}")
            # update
            else:
                node = self.cache.get(key)
                node.value = value
                self._remove(node)
                self._insert(node)
            

    def get(self, key):
        # only one thread at a time can execute any code inside this block
        with self.lock:
            if key not in self.cache: 
                return None
            # if key is expired, remove it from cache
            if key in self.ttl_map and time.time() > self.ttl_map[key]:
                print(self.ttl_map)
                self.delete(key)
                return None
            node = self.cache.get(key)
            self._remove(node)
            self._insert(node)
            return node.value

    def delete(self, key):
        if key in self.cache:
            node = self.cache[key] # get key from cache
            self._remove(node) # call remove to remove links
            del self.cache[key] # remove from cache dict
            del self.ttl_map[key] # remove key from ttl_map dict
            self.current_cache_size -= 1 # reduce size since its complete delete

    def _remove(self, node):
        """
        Helper method to remove a node
        and link its previous and next pointer to point each other.
        called when a node is to be made MRU or while evicting keys after its expiry
        """
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _insert(self, node):
        """
        Helper method to insert a node at front
        and make head point to it
        """
        node.next = self.head.next
        node.next.prev = node
        self.head.next = node
        node.prev = self.head

    def _cleaner(self):
        """
        Helper method to delete expired keys using a worker thread
        """
        logger.info("Running cleaner job to expire expired keys.")
        while True:
            time.sleep(1)
            now = time.time()
            with self.lock:
                expired_keys = [key for key, ttl in self.ttl_map.items() if now > ttl]
                for key in expired_keys:
                    self.delete(key)
                    logger.info(f"KeyExpired at: {now}, removed from cache: {key}")