"""
Central log collector. Every service POSTs its log lines here and they are
appended to one file.

The endpoint is async so many concurrent senders don't block each other;
the file write runs in a worker thread (asyncio.to_thread) and an
asyncio.Lock keeps lines from interleaving.

uvicorn log_logic.log_collector:app --port 9000
"""
import asyncio
import datetime
import os

from fastapi import FastAPI
from pydantic import BaseModel

LOG_FILE = os.getenv("LOG_FILE", "central.log")

app = FastAPI()
_write_lock = asyncio.Lock()


class LogEntry(BaseModel):
    service: str
    level: str
    message: str


def _append(line: str):
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


@app.post("/log")
async def log(entry: LogEntry):
    line = f"{datetime.datetime.now().isoformat()} | {entry.level} | {entry.service} | {entry.message}"
    print(line, flush=True)
    async with _write_lock:
        await asyncio.to_thread(_append, line)
    return {"status": "ok"}
