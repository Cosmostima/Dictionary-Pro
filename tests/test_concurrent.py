from __future__ import annotations

from dictpro import concurrent as dc
from dictpro.fetchers import NotFound
from dictpro.models import Inflection, WordEntry


def test_fetch_all_aggregates_success(monkeypatch):
    monkeypatch.setattr(dc, "_cam", lambda w: WordEntry(word=w))
    monkeypatch.setattr(dc, "_wik", lambda w: {"noun": [Inflection("", w)]})
    monkeypatch.setattr(dc, "_syn", lambda w: {"noun": ["alt"]})
    r = dc.fetch_all("x")
    assert r.entry is not None and r.entry.word == "x"
    assert r.extras.inflections == {"noun": [Inflection("", "x")]}
    assert r.extras.synonyms == {"noun": ["alt"]}
    assert r.errors == {}


def test_fetch_all_reports_partial_failures(monkeypatch):
    def raise_nf(_):
        raise NotFound("https://cambridge/x")
    monkeypatch.setattr(dc, "_cam", raise_nf)
    monkeypatch.setattr(dc, "_wik", lambda w: {})
    monkeypatch.setattr(dc, "_syn", lambda w: {})
    r = dc.fetch_all("x")
    assert r.entry is None
    assert "cambridge" in r.errors
    assert "404" in r.errors["cambridge"]
