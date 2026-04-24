"""End-to-end smoke: feed HTML fixtures through the full stack
(parsers -> concurrent -> agent -> cli) without hitting the network."""
from __future__ import annotations

import json

import pytest

from dictpro import concurrent as dc
from dictpro.cli import main
from dictpro.fetchers import NotFound


@pytest.fixture
def offline_fixtures(monkeypatch, fixtures_dir):
    """Route http_get to local fixture files so the whole stack runs offline."""
    def _fake_get(url: str, **_kw) -> str:
        if "cambridge" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "cambridge" / f"{word}.html"
        elif "wiktionary" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "wiktionary" / f"{word}.html"
        elif "freethesaurus" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "thesaurus" / f"{word}.html"
        else:
            raise NotFound(url)
        if not path.exists():
            raise NotFound(url)
        return path.read_text(encoding="utf-8")

    monkeypatch.setattr("dictpro.fetchers.http_get", _fake_get)
    monkeypatch.setattr(dc, "http_get", _fake_get)


def test_e2e_query_swarm(offline_fixtures, capsys):
    rc = main(["-q", "swarm"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["word"] == "swarm"
    assert out["ok"] is True
    assert len(out["senses"]) > 0
    assert any(s["pos"] == "noun" for s in out["senses"])


def test_e2e_batch_mixed(offline_fixtures, tmp_path, capsys):
    words = tmp_path / "w.txt"
    words.write_text("swarm\nnonexistent_xyz\n")
    rc = main(["-b", str(words)])
    assert rc == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert [l["word"] for l in lines] == ["swarm", "nonexistent_xyz"]
    assert lines[0]["ok"] is True
    assert lines[1]["ok"] is False
