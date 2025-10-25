"""
Interacts with hashring to find replicas/nodes for get/post requests
Calls utils's helper get and post methods that requests to running local node instances (server.py).

(1) coordinator -> (2) hash_ring to find replica/node -> (3) utils -> (4) server
(2) - for post we require only 1 node and then replication can be performed.
  - for get we require all replicas/nodes to search the key into

# uvicorn coordinator:app --port 8000   - runs coordinator.py
# uvicorn cache_logic.server:app --port 8001  - node 1 at localhost:8001
# uvicorn cache_logic.server:app --port 8002  - node 2 at localhost:8002
# uvicorn cache_logic.server:app --port 8003  - node 3 at localhost:8003

-- for running on local machine, coordinator runs on localhost:8000
curl -X POST "http://127.0.0.1:8000/set" \
     -H "Content-Type: application/json" \
     -d '{"key": "user123", "value": "Alice"}'  

curl -X GET "http://127.0.0.1:8000/get/user123"

-- for running inside container use
curl -X POST "http://localhost:8000/set" \
     -H "Content-Type: application/json" \
     -d '{"key":"user123","value":"Alice"}'
""" 
# # curl "localhost:8000/get/foo"
from fastapi import FastAPI
from pydantic import BaseModel
from cache_logic.consistent_hashing import HashRing
from cache_logic.config import NODES, REPLICATION_FACTOR, VIRTUAL_NODES
from cache_logic.utils import post, get
import logging
import threading

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("coordinator")

app = FastAPI()
ring = HashRing(NODES, vnodes=VIRTUAL_NODES)

class Item(BaseModel):
    key: str
    value: str
    ttl: int = 60

def replicate_async(key: str, value: str, ttl: int, replicas: list):
    """Asynchronous background replication
    achieving eventual consistency
    """
    for node in replicas[1:]: #rest of the replica node after primary node, 2 threads spinned
        threading.Thread(
            target=post,
            args=(f"{node}/set", {"key": key, "value": value, "ttl": ttl}),
            daemon=True
        ).start()

@app.post("/set")
def set_item(item: Item):
    # get the replicas, and pick the 1st one [0]
    # send a post request to that node to be stored.
    # then sync to rest of the replicas[1:]
    replicas = ring.get_replicas(item.key, replication_factor=REPLICATION_FACTOR)
    primary_node = replicas[0]
    print(f"node where key is to be set: {primary_node}")
    try:
        url = f"{primary_node}/set"
        response = post(url, item.dict())
        if response and response.ok:
            # replicate asynchronously
            replicate_async(item.key, item.value, item.ttl, replicas)
            logging.info(f"[SET] Key : {item.key} → Primary Node : {primary_node}")
            return {"status": "stored", "primary": primary_node, "replicas": replicas}
        else:
            print(f"[SET] Key={item.key} FAILED")
    except Exception as e:
        logger.error(f"Error writing to {primary_node}: {e}")
        return {"error": "Failed to contact primary"}

@app.get("/get/{key}")
def get_item(key: str):
    replicas = ring.get_replicas(key, replication_factor=REPLICATION_FACTOR)
    for node in replicas:
        url = f"{node}/get/{key}"
        res = get(url)
        if res and res.ok and "value" in res.json():
            val = res.json().get("value")
            if val:
                logger.info(f"[GET] Key={key} from Node : {node}")
                return {"value": val, "source": node}
    return {"error": "Not found"}