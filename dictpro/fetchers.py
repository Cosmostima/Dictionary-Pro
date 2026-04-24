from __future__ import annotations

import time
from typing import Optional

import requests

from .constants import DEFAULT_RETRIES, DEFAULT_TIMEOUT, UA


class FetchError(Exception):
    pass


class NotFound(FetchError):
    pass


def http_get(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    session: Optional[requests.Session] = None,
) -> str:
    """GET with retry + timeout. Returns body text. Raises NotFound on 404,
    FetchError on other failures."""
    headers = {"User-Agent": UA}
    sess = session or requests
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = sess.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                raise NotFound(url)
            resp.raise_for_status()
            return resp.text
        except NotFound:
            raise
        except Exception as exc:  # network, timeout, 5xx
            last_exc = exc
            if attempt < retries:
                time.sleep(0.3 * (attempt + 1))
    raise FetchError(f"GET {url} failed: {last_exc}") from last_exc
