"""
Logging handler that ships records to the central log collector.

emit() only puts the record on an in-memory queue; a daemon thread does
the HTTP POST. Logging therefore never blocks a request, and a down
collector only drops log lines instead of slowing the cache.
"""
import logging
import queue
import threading

from cache_logic.utils import post


class HttpLogHandler(logging.Handler):
    def __init__(self, endpoint_url, service_name, max_queue=10_000):
        super().__init__()
        self.endpoint_url = endpoint_url
        self.service_name = service_name
        self._queue = queue.Queue(maxsize=max_queue)
        threading.Thread(target=self._sender, daemon=True).start()

    def emit(self, record):
        payload = {
            "service": self.service_name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            pass  # drop rather than block the caller

    def _sender(self):
        while True:
            payload = self._queue.get()
            post(self.endpoint_url, payload)  # returns None on failure
