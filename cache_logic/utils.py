"""
HTTP helpers used by the coordinator and log handler.

Failures return None instead of raising, so callers can fail over
to the next replica rather than crashing the request.
"""
import logging

import requests

logger = logging.getLogger("utils")
TIMEOUT = 1  # seconds


def post(url, data):
    try:
        return requests.post(url, json=data, timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f"POST {url} failed: {e}")
        return None


def get(url):
    try:
        return requests.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f"GET {url} failed: {e}")
        return None


def delete(url):
    try:
        return requests.delete(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        logger.warning(f"DELETE {url} failed: {e}")
        return None
