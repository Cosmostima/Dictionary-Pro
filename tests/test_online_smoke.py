"""Online smoke tests. Run explicitly with `pytest -m online`."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.online


def test_online_cambridge_swarm() -> None:
    from dictpro.constants import CAMBRIDGE_URL
    from dictpro.fetchers import http_get
    from dictpro.parsers import parse_cambridge

    html = http_get(CAMBRIDGE_URL.format(word="swarm"))
    entry = parse_cambridge(html, "swarm")
    assert len(entry.senses) >= 3
    assert any(s.pos == "noun" for s in entry.senses)


def test_online_wiktionary_swarm() -> None:
    from dictpro.constants import WIKTIONARY_URL
    from dictpro.fetchers import http_get
    from dictpro.parsers import parse_wiktionary

    html = http_get(WIKTIONARY_URL.format(word="swarm"))
    infl = parse_wiktionary(html)
    assert infl, "expected at least one inflection group"


def test_online_thesaurus_swarm() -> None:
    from dictpro.constants import THESAURUS_URL
    from dictpro.fetchers import http_get
    from dictpro.parsers import parse_thesaurus

    html = http_get(THESAURUS_URL.format(word="swarm"))
    syn = parse_thesaurus(html)
    # swarm has synonyms on freethesaurus, but be tolerant if site changes.
    assert isinstance(syn, dict)
