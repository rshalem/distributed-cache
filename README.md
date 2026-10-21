# distributed-cache

A distributed in-memory key-value cache in Python (FastAPI). A stateless coordinator routes requests across cache nodes using a consistent hash ring, replicates writes asynchronously, and fails over to the next replica when a node is down.

## Architecture

```
client ──► coordinator :8000 ──► hash ring (SHA-256, 100 vnodes/node)
                 │
                 ├── write: first healthy replica in ring order (primary),
                 │          then async copies to the rest
                 ├── read:  first replica that has the key; dead nodes skipped
                 ▼
        node1 :8001   node2 :8002   node3 :8003     (LRU + TTL each)
                 │
                 └── all services ──► log collector :9000 ──► central.log
```

| Component | File | What it does |
|---|---|---|
| Coordinator | `coordinator.py` | Routing, write failover, read failover, delete |
| Hash ring | `cache_logic/consistent_hashing.py` | Virtual nodes, O(log n) lookup via binary search |
| Replication | `cache_logic/replication.py` | Bounded thread pool sends async copies (eventual consistency) |
| Cache node | `cache_logic/server.py`, `cache.py` | Thread-safe LRU (hash map + doubly linked list, O(1)) with TTL |
| Logging | `log_logic/` | Non-blocking HTTP log handler → async central collector |

## Design choices

- **Consistent hashing** — adding a node remaps ~1/N keys instead of most keys with `hash % N`.
- **Replication factor 2 of 3 nodes** — each key lives on 2 nodes, so the ring actually partitions data and one node can fail without losing reads.
- **Eventual consistency** — a write is acknowledged after one replica stores it; a read right after a write can hit a replica that hasn't caught up yet.
- **TTL** — expired keys are removed lazily on read and by a background cleaner thread every second. Every write resets the TTL.

## Run

**Docker Compose**
```bash
docker compose up --build
```

**Locally**
```bash
pip install -r requirements.txt
export CACHE_NODES="http://localhost:8001,http://localhost:8002,http://localhost:8003"
export LOG_ENDPOINT_URL="http://localhost:9000/log"
uvicorn cache_logic.server:app --port 8001 &
uvicorn cache_logic.server:app --port 8002 &
uvicorn cache_logic.server:app --port 8003 &
uvicorn log_logic.log_collector:app --port 9000 &
uvicorn coordinator:app --port 8000
```

## Use

```bash
curl -X POST localhost:8000/set -H "Content-Type: application/json" \
     -d '{"key": "user123", "value": "Alice", "ttl": 60}'
curl localhost:8000/get/user123
curl -X DELETE localhost:8000/delete/user123
```

Try failover: stop the node listed as `primary`, then `get` the key again — it's served from the other replica.

## Tests

```bash
pip install pytest && python -m pytest -q tests
```

## Configuration

| Env var | Default |
|---|---|
| `CACHE_NODES` | `http://node1:8001,http://node2:8002,http://node3:8003` |
| `REPLICATION_FACTOR` | `2` |
| `VIRTUAL_NODES` | `100` |
| `DEFAULT_TTL` | `60` seconds |
| `NODE_CAPACITY` | `1000` keys per node |
| `LOG_ENDPOINT_URL` | `http://log:9000/log` |

## Not yet implemented

Read repair / quorum reads, retry queue for failed replication, persistence, node health checks, mTLS between services.
