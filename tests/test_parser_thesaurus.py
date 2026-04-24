from __future__ import annotations

import pytest

from dictpro.parsers import parse_thesaurus
from tests.conftest import load_golden, load_html


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_thesaurus_pos_presence(word: str) -> None:
    html = load_html("thesaurus", word)
    syn = parse_thesaurus(html)
    gold = load_golden(word)["thesaurus"]
    for pos in gold.get("pos_present", []):
        assert pos in syn, f"{word}: expected pos {pos} in {list(syn)}"
    if not gold.get("pos_present"):
        assert syn == {}


@pytest.mark.parametrize("word", ["swarm", "good", "run"])
def test_thesaurus_contains_expected_words(word: str) -> None:
    html = load_html("thesaurus", word)
    syn = parse_thesaurus(html)
    gold = load_golden(word)["thesaurus"]
    for pos, expected in gold.get("contains", {}).items():
        for w in expected:
            assert w in syn.get(pos, []), f"{word}/{pos}: {w} missing"


def test_thesaurus_nonexistent() -> None:
    html = load_html("thesaurus", "nonexistent_xyz")
    syn = parse_thesaurus(html)
    assert syn == {}
