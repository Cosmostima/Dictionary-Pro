from __future__ import annotations

import json

import pytest

from dictpro import agent, concurrent
from dictpro.cli import main
from dictpro.models import Extras, Inflection, Pronunciation, Sense, WordEntry


def _ok(word: str) -> concurrent.LookupResult:
    return concurrent.LookupResult(
        word=word,
        entry=WordEntry(
            word=word,
            senses=[
                Sense(pos="noun", text="first def", pron_group=0),
                Sense(pos="verb", text="second def", pron_group=0),
            ],
            pronunciations={"noun": [[Pronunciation("US", "/x/", "/a.mp3")]], "verb": [[]]},
        ),
        extras=Extras(
            inflections={"noun": [Inflection("Plural", word + "s")]},
            synonyms={"noun": ["alt"]},
        ),
        errors={},
    )


def _nf(word: str) -> concurrent.LookupResult:
    return concurrent.LookupResult(
        word=word, entry=None, extras=Extras(),
        errors={"cambridge": "404"},
    )


@pytest.fixture
def mock_fetch(monkeypatch):
    calls: dict[str, concurrent.LookupResult] = {}

    def _fake(word: str) -> concurrent.LookupResult:
        return calls.get(word, _nf(word))

    monkeypatch.setattr(concurrent, "fetch_all", _fake)
    monkeypatch.setattr(agent, "fetch_all", _fake)
    return calls


def test_query_returns_full_json(mock_fetch, capsys):
    mock_fetch["serendipity"] = _ok("serendipity")
    rc = main(["-q", "serendipity"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["word"] == "serendipity"
    assert out["ok"] is True
    assert out["senses"][0] == {"i": 0, "pos": "noun", "text": "first def"}
    assert "written" not in out


def test_query_not_found_exit_2(mock_fetch, capsys):
    rc = main(["-q", "xyznope"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "errors" in out


def test_batch_returns_ndjson(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    mock_fetch["beta"] = _ok("beta")
    words_file = tmp_path / "w.txt"
    words_file.write_text("alpha\nbeta\n")
    rc = main(["-b", str(words_file)])
    assert rc == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert [l["word"] for l in lines] == ["alpha", "beta"]
    assert all(l["ok"] for l in lines)
    assert all("written" not in l for l in lines)


def test_batch_from_stdin(mock_fetch, tmp_path, capsys, monkeypatch):
    import io
    mock_fetch["serendipity"] = _ok("serendipity")
    monkeypatch.setattr("sys.stdin", io.StringIO("serendipity\n"))
    rc = main(["-b", "-"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["word"] == "serendipity"


def test_batch_mixed_exits_0_if_any_success(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    words_file = tmp_path / "w.txt"
    words_file.write_text("alpha\nxyznope\n")
    rc = main(["-b", str(words_file)])
    assert rc == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["ok"] is True
    assert lines[1]["ok"] is False


def test_batch_all_fail_exit_2(mock_fetch, tmp_path, capsys):
    words_file = tmp_path / "w.txt"
    words_file.write_text("xyznope1\nxyznope2\n")
    rc = main(["-b", str(words_file)])
    assert rc == 2


def test_batch_empty_lines_silently_skipped(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    words_file = tmp_path / "w.txt"
    words_file.write_text("\n\nalpha\n   \n")
    rc = main(["-b", str(words_file)])
    assert rc == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 1


def test_batch_no_words_exit_2(mock_fetch, tmp_path, capsys):
    words_file = tmp_path / "w.txt"
    words_file.write_text("\n\n   \n")
    rc = main(["-b", str(words_file)])
    assert rc == 2
    assert capsys.readouterr().out == ""
