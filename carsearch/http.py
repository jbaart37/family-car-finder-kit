"""HTTP session that presents a real Chrome TLS fingerprint (most listing sites 403 plain clients)."""
import random
import time

from curl_cffi import requests

TIMEOUT = 30


def new_session():
    return requests.Session(impersonate="chrome")


def pause():
    """Polite delay between page requests to the same site."""
    time.sleep(random.uniform(1.0, 2.2))
