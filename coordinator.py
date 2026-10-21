"""
Stateless coordinator. Routes each request to the right cache nodes using
the consistent hash ring.

Write path: try replicas in ring order; the first node that accepts the
write acts as primary (so a dead primary fails over to the next replica),
then the remaining replicas are updated asynchronously.

Read path: try replicas in ring order and return the first hit; a node
that is down or times out is skipped.

Run with Docker Compose:   docker compose up --build
Run locally:               see README.md

curl -X POST localhost:8000/set -H "Content-Type: application/json" \
     -d '{"key": "user123", "value": "Alice", "ttl": 60}'
curl localhost:8000/get/user123
curl -X DELETE localhost:8000/delete/user123
"""
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cache_logic.config import (
    DEFAULT_TTL,
    LOG_ENDPOINT_URL,
    NODES,
    REPLICATION_FACTOR,
    VIRTUAL_NODES,
)
from cache_logic.consistent_hashing import HashRing
from cache_logic.replication import replicate_async
from cache_logic.utils import delete, get, post
from log_logic.log_handler import HttpLogHandler

logger = logging.getLogger("coordinator")
logger.setLevel(logging.INFO)
logger.addHandler(HttpLogHandler(LOG_ENDPOINT_URL, "coordinator"))

app = FastAPI()
ring = HashRing(NODES, vnodes=VIRTUAL_NODES)


class Item(BaseModel):
    key: str
    value: str
    ttl: int = DEFAULT_TTL


@app.get("/health")
def health():
    return {"status": "ok", "nodes": NODES, "replication_factor": REPLICATION_FACTOR}


@app.post("/set")
def set_item(item: Item):
    replicas = ring.get_replicas(item.key, replication_factor=REPLICATION_FACTOR)
    payload = item.model_dump()

    for i, node in enumerate(replicas):
        res = post(f"{node}/set", payload)
        if res is not None and res.ok:
            if i > 0:
                logger.warning(f"[SET] key='{item.key}' failed over to {node}")
            others = [n for n in replicas if n != node]
            replicate_async(payload, others)
            logger.info(f"[SET] key='{item.key}' primary={node}")
            return {"status": "stored", "primary": node, "replicas": replicas}
        logger.warning(f"[SET] key='{item.key}' write to {node} failed, trying next replica")

    logger.error(f"[SET] key='{item.key}' failed on all replicas {replicas}")
    raise HTTPException(status_code=503, detail="No replica available")


@app.get("/get/{key}")
def get_item(key: str):
    replicas = ring.get_replicas(key, replication_factor=REPLICATION_FACTOR)
    reachable = 0

    for node in replicas:
        res = get(f"{node}/get/{key}")
        if res is None:
            logger.warning(f"[GET] key='{key}' node {node} unreachable, trying next replica")
            continue
        reachable += 1
        if res.ok:
            logger.info(f"[GET] key='{key}' hit on {node}")
            return {"value": res.json()["value"], "source": node}

    if reachable == 0:
        raise HTTPException(status_code=503, detail="No replica available")
    raise HTTPException(status_code=404, detail="Not found")


@app.delete("/delete/{key}")
def delete_item(key: str):
    replicas = ring.get_replicas(key, replication_factor=REPLICATION_FACTOR)
    results = {}
    for node in replicas:
        res = delete(f"{node}/delete/{key}")
        results[node] = "ok" if res is not None and res.ok else "unreachable"
    logger.info(f"[DELETE] key='{key}' {results}")
    return {"status": "deleted", "replicas": results}
