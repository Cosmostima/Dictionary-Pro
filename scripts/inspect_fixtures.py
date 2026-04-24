"""One-time helper: parse fixtures and print summary so we can hand-build
golden JSON. Run:  python scripts/inspect_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dictpro.parsers import parse_cambridge, parse_thesaurus, parse_wiktionary

FIXTURES = ROOT / "tests" / "fixtures"
WORDS = ["swarm", "good", "who", "run"]


def show(word: str) -> None:
    cam_html = (FIXTURES / "cambridge" / f"{word}.html").read_text(encoding="utf-8")
    wik_html = (FIXTURES / "wiktionary" / f"{word}.html").read_text(encoding="utf-8")
    syn_html = (FIXTURES / "thesaurus" / f"{word}.html").read_text(encoding="utf-8")
    entry = parse_cambridge(cam_html, word)
    infl = parse_wiktionary(wik_html) if wik_html else {}
    syn = parse_thesaurus(syn_html)

    pos_counts: dict[str, int] = {}
    for s in entry.senses:
        pos_counts[s.pos] = pos_counts.get(s.pos, 0) + 1

    first_per_pos = {}
    for s in entry.senses:
        first_per_pos.setdefault(s.pos, s.text[:60])

    us_ipas = {}
    uk_ipas = {}
    for pos, groups in entry.pronunciations.items():
        for grp in groups:
            for p in grp:
                if p.region == "US" and pos not in us_ipas and p.ipa:
                    us_ipas[pos] = p.ipa
                if p.region == "UK" and pos not in uk_ipas and p.ipa:
                    uk_ipas[pos] = p.ipa

    summary = {
        "word": word,
        "total_senses": len(entry.senses),
        "pos_counts": pos_counts,
        "first_def_per_pos": first_per_pos,
        "us_ipa_per_pos": us_ipas,
        "uk_ipa_per_pos": uk_ipas,
        "inflection_pos_counts": {k: len(v) for k, v in infl.items()},
        "inflection_samples": {k: [(i.kind, i.text) for i in v[:3]] for k, v in infl.items()},
        "synonym_pos_counts": {k: len(v) for k, v in syn.items()},
        "synonym_samples": {k: v[:3] for k, v in syn.items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    for w in WORDS:
        print(f"\n===== {w} =====")
        show(w)
