from __future__ import annotations

import re

from dictpro.models import Extras, Inflection, Pronunciation, Sense, WordEntry
from dictpro.renderer import RenderOptions, header, render_row


def _make_entry() -> tuple[WordEntry, Extras]:
    entry = WordEntry(
        word="swarm",
        senses=[
            Sense(pos="noun", text="a large group of insects", pron_group=0),
            Sense(pos="verb", text="insects swarm together", pron_group=0),
        ],
        pronunciations={
            "noun": [[
                Pronunciation("US", "/swɔːrm/", "/us.mp3"),
                Pronunciation("UK", "/swɔːm/", "/uk.mp3"),
            ]],
            "verb": [[
                Pronunciation("US", "/swɔːrm/", ""),
            ]],
        },
    )
    extras = Extras(
        inflections={
            "noun": [Inflection("Singular", "swarm"), Inflection("Plural", "swarms")],
            "verb": [Inflection("Plain form", "swarm")],
        },
        synonyms={"noun": ["multitude", "crowd"]},
    )
    return entry, extras


def test_header_column_count_matches_row():
    entry, extras = _make_entry()
    opts = RenderOptions(include_audio=True, include_synonyms=True)
    head = header(opts)
    row = render_row(entry, extras, 0, opts)
    head_cols = head.splitlines()[0].count("|") - 1
    row_cols = row.rstrip("\n").count("|") - 1
    assert head_cols == row_cols == 7  # Word Pos Def Syn Verbs Pron Web


def test_render_row_includes_word_and_pos():
    entry, extras = _make_entry()
    opts = RenderOptions(include_audio=True, include_synonyms=True)
    row = render_row(entry, extras, 0, opts)
    assert row.startswith("|swarm|noun|")
    assert "multitude; crowd" in row
    assert "US: " in row and "UK: " in row
    assert "[^_^]" in row


def test_render_row_no_audio_no_syn():
    entry, extras = _make_entry()
    opts = RenderOptions(include_audio=False, include_synonyms=False)
    row = render_row(entry, extras, 1, opts)
    # Columns: Word Pos Def Verbs Web -> 5 separators
    cols = row.rstrip("\n").split("|")[1:-1]
    assert len(cols) == 5
    assert cols[0] == "swarm"
    assert cols[1] == "verb"


def test_synonym_fallback_when_pos_missing():
    entry = WordEntry(
        word="x",
        senses=[Sense(pos="adverb", text="fast", pron_group=0)],
        pronunciations={"adverb": [[]]},
    )
    extras = Extras(synonyms={"adjective": ["quick"]}, inflections={})
    opts = RenderOptions(include_audio=False, include_synonyms=True)
    row = render_row(entry, extras, 0, opts)
    assert "adjective: quick" in row


def test_pron_link_uses_absolute_url_for_relative_audio():
    entry, extras = _make_entry()
    opts = RenderOptions(include_audio=True, include_synonyms=False)
    row = render_row(entry, extras, 0, opts)
    assert re.search(r"\[/swɔːrm/\]\(https://dictionary\.cambridge\.org/us\.mp3\)", row)
