from __future__ import annotations

import pytest

from dictpro.parsers import parse_wiktionary
from tests.conftest import load_golden, load_html


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_wiktionary_pos_counts(word: str) -> None:
    html = load_html("wiktionary", word)
    infl = parse_wiktionary(html)
    gold = load_golden(word)["wiktionary"]
    counts = {k: len(v) for k, v in infl.items()}
    assert counts == gold["pos_counts"]


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_wiktionary_contains_expected_forms(word: str) -> None:
    html = load_html("wiktionary", word)
    infl = parse_wiktionary(html)
    gold = load_golden(word)["wiktionary"]
    for pos, expected_words in gold["contains"].items():
        texts = [i.text for i in infl.get(pos, [])]
        for w in expected_words:
            assert w in texts, f"{word}/{pos}: {w} missing in {texts}"


def test_wiktionary_empty_html_returns_empty() -> None:
    # Our fixture for 404 stores empty string.
    html = load_html("wiktionary", "nonexistent_xyz")
    infl = parse_wiktionary(html)
    assert infl == {}
