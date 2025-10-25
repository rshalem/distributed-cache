"""
Each node will have this code, it can be ran in a designated port via uvicorn
Stores and retrives data from its local cache using Cache class
Replies back to coordinator with results
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from cache_logic.cache import Cache

app = FastAPI()
cache = Cache(capacity=1000)

class Item(BaseModel):
    key: str
    value: str
    ttl: int = 60

@app.get("/get/{key}")
def get_key(key: str):
    value = cache.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Not found")
    return {"value": value}

@app.post("/set/")
def set_key(item: Item):
    cache.set(item.key, item.value, item.ttl)
    return {"status": "OK"}

@app.delete("/delete/{key}")
def delete_key(key: str):
    cache.delete(key)
    return {"status": "deleted"}