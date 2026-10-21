"""
Configuration. Every value can be overridden with an environment variable,
so the same code runs in Docker Compose and on a local machine.

Docker Compose (defaults): nodes are reached by service name.
Local:
    export CACHE_NODES="http://localhost:8001,http://localhost:8002,http://localhost:8003"
    export LOG_ENDPOINT_URL="http://localhost:9000/log"
"""
import os

NODES = [
    n.strip()
    for n in os.getenv(
        "CACHE_NODES",
        "http://node1:8001,http://node2:8002,http://node3:8003",
    ).split(",")
    if n.strip()
]

# Must be smaller than the node count, otherwise every key lands on every
# node and the hash ring does no partitioning.
REPLICATION_FACTOR = int(os.getenv("REPLICATION_FACTOR", "2"))
VIRTUAL_NODES = int(os.getenv("VIRTUAL_NODES", "100"))
DEFAULT_TTL = int(os.getenv("DEFAULT_TTL", "60"))
NODE_CAPACITY = int(os.getenv("NODE_CAPACITY", "1000"))

# Service name "log" in docker-compose.yml.
LOG_ENDPOINT_URL = os.getenv("LOG_ENDPOINT_URL", "http://log:9000/log")
