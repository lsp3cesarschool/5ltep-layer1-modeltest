"""HTTP for the benchmark: one keep-alive session, fast failure on connection refusals.

Same rule as the Layer 1 toolkit (lesson from the Recife portal, 01/10/2026): seen from GitHub's
runners, some servers intermittently refuse new connections; reusing connections and giving a
connection 15 s (an answer, longer) avoids minutes lost per refusal.
"""

import time

import requests

UA = {"User-Agent": "5ltep-layer1-modeltest (+https://github.com/lsp3cesarschool/5ltep-layer1-modeltest)"}
CONNECT_TIMEOUT_S = 15
SESSION = requests.Session()
SESSION.headers.update(UA)
_adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)


def get(url: str, read_timeout: float = 60, retries: int = 3, **kwargs) -> requests.Response:
    """GET with (connect, read) timeouts and a few retries on network errors (not on HTTP errors)."""
    for attempt in range(1, retries + 1):
        try:
            return SESSION.get(url, timeout=(CONNECT_TIMEOUT_S, read_timeout), **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == retries:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")
