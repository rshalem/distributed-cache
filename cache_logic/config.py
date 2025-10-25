# config.py
# http://node1:8001 - inside container, hostname is resolved as service name
# if run locally, replace it with localhost:port
NODES = [
    "http://node1:8001",
    "http://node2:8002",
    "http://node3:8003",
]

REPLICATION_FACTOR = 3
VIRTUAL_NODES = 100
DEFAULT_TTL = 60