from __future__ import annotations

from dictpro.agent import result_to_json
from dictpro.concurrent import LookupResult
from dictpro.models import Extras, Inflection, Pronunciation, Sense, WordEntry


def _result_ok() -> LookupResult:
    entry = WordEntry(
        word="swarm",
        senses=[
            Sense(pos="noun", text="a large group", pron_group=0),
            Sense(pos="verb", text="to move in a swarm", pron_group=0),
        ],
        pronunciations={
            "noun": [[
                Pronunciation("US", "/swɔːrm/", "/us.mp3"),
                Pronunciation("UK", "/swɔːm/", "/uk.mp3"),
            ]],
            "verb": [[]],
        },
    )
    extras = Extras(
        inflections={"noun": [Inflection("Plural", "swarms")]},
        synonyms={"noun": ["multitude"]},
    )
    return LookupResult(word="swarm", entry=entry, extras=extras, errors={})


def test_result_to_json_success_shape():
    r = _result_ok()
    out = result_to_json(r)
    assert out["word"] == "swarm"
    assert out["ok"] is True
    assert out["senses"] == [
        {"i": 0, "pos": "noun", "text": "a large group"},
        {"i": 1, "pos": "verb", "text": "to move in a swarm"},
    ]
    assert out["inflections"] == {"noun": ["swarms"]}
    assert out["synonyms"] == {"noun": ["multitude"]}
    assert out["pronunciations"]["noun"][0][0] == {
        "region": "US", "ipa": "/swɔːrm/", "audio": "/us.mp3",
    }
    assert "errors" not in out
    assert "written" not in out


def test_result_to_json_not_found():
    r = LookupResult(
        word="xyznope",
        entry=None,
        extras=Extras(),
        errors={"cambridge": "404 https://...", "wiktionary": "404 https://..."},
    )
    out = result_to_json(r)
    assert out["word"] == "xyznope"
    assert out["ok"] is False
    assert out["senses"] == []
    assert out["errors"] == {"cambridge": "404 https://...", "wiktionary": "404 https://..."}
    assert "inflections" not in out
    assert "synonyms" not in out
    assert "pronunciations" not in out


def test_result_to_json_partial_errors_only_failing_sources():
    r = _result_ok()
    r.errors = {"wiktionary": "timeout"}
    out = result_to_json(r)
    assert out["ok"] is True
    assert out["errors"] == {"wiktionary": "timeout"}


def test_result_to_json_empty_source_dicts_omitted():
    entry = WordEntry(
        word="x",
        senses=[Sense(pos="noun", text="t", pron_group=0)],
        pronunciations={"noun": [[]]},
    )
    r = LookupResult(word="x", entry=entry, extras=Extras(), errors={})
    out = result_to_json(r)
    assert "synonyms" not in out
    assert "inflections" not in out
    assert "written" not in out
