import requests

def post(url, data):
    try:
        return requests.post(url, json=data, timeout=1)
    except Exception as e:
        raise e

def get(url):
    try:
        return requests.get(url, timeout=1)
    except Exception as e:
        raise e