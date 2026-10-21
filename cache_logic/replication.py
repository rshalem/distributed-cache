"""
Asynchronous replication to secondary replicas (eventual consistency).

The coordinator acknowledges a write once one replica has stored it, then
hands the remaining replicas to this module. A bounded thread pool sends
the copies in the background, so a slow replica never delays the client
and a burst of writes can't spawn unbounded threads.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from cache_logic.utils import post

logger = logging.getLogger("replication")
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="replicator")


def _replicate_one(node: str, payload: dict):
    res = post(f"{node}/set", payload)
    if res is not None and res.ok:
        logger.info(f"[REPLICATION] key='{payload['key']}' -> {node} OK")
    else:
        # A real system would queue this for retry or rely on read repair.
        logger.warning(f"[REPLICATION] key='{payload['key']}' -> {node} FAILED")


def replicate_async(payload: dict, targets: list):
    """Fire-and-forget copies of `payload` to each node in `targets`."""
    for node in targets:
        _executor.submit(_replicate_one, node, payload)
