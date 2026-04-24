from __future__ import annotations

import pytest

from dictpro.parsers import parse_cambridge
from tests.conftest import load_golden, load_html


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_cambridge_sense_counts_match_golden(word: str) -> None:
    entry = parse_cambridge(load_html("cambridge", word), word)
    gold = load_golden(word)["cambridge"]

    assert len(entry.senses) == gold["total_senses"]

    pos_counts: dict[str, int] = {}
    for s in entry.senses:
        pos_counts[s.pos] = pos_counts.get(s.pos, 0) + 1
    assert pos_counts == gold["pos_counts"]


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_cambridge_first_def_substring(word: str) -> None:
    entry = parse_cambridge(load_html("cambridge", word), word)
    gold = load_golden(word)["cambridge"]
    first_per_pos: dict[str, str] = {}
    for s in entry.senses:
        first_per_pos.setdefault(s.pos, s.text)
    for pos, expected_sub in gold["first_def_contains"].items():
        assert pos in first_per_pos
        assert expected_sub.lower() in first_per_pos[pos].lower(), (
            f"{word}/{pos}: expected substring {expected_sub!r} in {first_per_pos[pos]!r}"
        )


@pytest.mark.parametrize("word", ["swarm", "good", "who", "run"])
def test_cambridge_pronunciation_present(word: str) -> None:
    entry = parse_cambridge(load_html("cambridge", word), word)
    gold = load_golden(word)["cambridge"]
    for pos, expected in gold["us_ipa"].items():
        groups = entry.pronunciations.get(pos, [])
        flat = [p for grp in groups for p in grp]
        us = [p.ipa for p in flat if p.region == "US" and p.ipa]
        assert expected in us, f"{word}/{pos} US IPA {expected} not in {us}"
    for pos, expected in gold["uk_ipa"].items():
        groups = entry.pronunciations.get(pos, [])
        flat = [p for grp in groups for p in grp]
        uk = [p.ipa for p in flat if p.region == "UK" and p.ipa]
        assert expected in uk, f"{word}/{pos} UK IPA {expected} not in {uk}"


def test_cambridge_404_page_yields_empty_entry() -> None:
    html = load_html("cambridge", "nonexistent_xyz")
    entry = parse_cambridge(html, "nonexistent_xyz")
    assert entry.senses == []
    assert entry.pronunciations == {}
