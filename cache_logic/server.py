"""
Cache node. Each node runs this app on its own port and keeps its own
in-memory LRU cache. The coordinator talks to nodes over HTTP.

uvicorn cache_logic.server:app --port 8001
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from cache_logic.cache import Cache
from cache_logic.config import DEFAULT_TTL, NODE_CAPACITY

app = FastAPI()
cache = Cache(capacity=NODE_CAPACITY)


class Item(BaseModel):
    key: str
    value: str
    ttl: int = DEFAULT_TTL


@app.get("/health")
def health():
    return {"status": "ok", "keys": len(cache)}


@app.get("/get/{key}")
def get_key(key: str):
    value = cache.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"value": value}


@app.post("/set")
def set_key(item: Item):
    cache.set(item.key, item.value, item.ttl)
    return {"status": "OK"}


@app.delete("/delete/{key}")
def delete_key(key: str):
    existed = cache.delete(key)
    return {"status": "deleted" if existed else "not_found"}
