from __future__ import annotations

import pytest

from dictpro import fetchers


class _Resp:
    def __init__(self, status=200, text="ok"):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


def test_http_get_returns_text_on_200():
    sess = _FakeSession([_Resp(200, "hello")])
    assert fetchers.http_get("https://x", session=sess, retries=0) == "hello"


def test_http_get_raises_not_found_on_404():
    sess = _FakeSession([_Resp(404)])
    with pytest.raises(fetchers.NotFound):
        fetchers.http_get("https://x", session=sess, retries=0)


def test_http_get_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(fetchers.time, "sleep", lambda _s: None)
    sess = _FakeSession([RuntimeError("boom"), _Resp(200, "ok")])
    assert fetchers.http_get("https://x", session=sess, retries=1) == "ok"
    assert sess.calls == 2


def test_http_get_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(fetchers.time, "sleep", lambda _s: None)
    sess = _FakeSession([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")])
    with pytest.raises(fetchers.FetchError):
        fetchers.http_get("https://x", session=sess, retries=2)
