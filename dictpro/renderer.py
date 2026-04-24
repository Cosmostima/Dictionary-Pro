from __future__ import annotations

from dataclasses import dataclass

from .constants import CAMBRIDGE_BASE, CAMBRIDGE_URL
from .models import Extras, Pronunciation, WordEntry


@dataclass
class RenderOptions:
    include_audio: bool = True
    include_synonyms: bool = True


def header(opts: RenderOptions) -> str:
    cols = ["Word", "Pos", "Def"]
    if opts.include_synonyms:
        cols.append("Syn")
    cols.append("Verbs")
    if opts.include_audio:
        cols.append("Pron")
    cols.append("Web")
    return "|" + "|".join(cols) + "|\n" + "|" + "|".join("-" for _ in cols) + "|\n"


def _format_synonyms(pos: str, syn_map: dict[str, list[str]]) -> str:
    if pos in syn_map and syn_map[pos]:
        return "; ".join(syn_map[pos])
    # Fallback: dump everything with pos labels.
    parts = []
    for k, v in syn_map.items():
        if v:
            parts.append(f"{k}: " + "; ".join(v))
    return " | ".join(parts)


def _format_inflections(pos: str, infl_map) -> str:
    if pos in infl_map and infl_map[pos]:
        parts = [item.text for item in infl_map[pos]]
    else:
        parts = []
        for forms in infl_map.values():
            parts.extend(item.text for item in forms)
    return "; ".join(parts)


def _format_prons(prons: list[Pronunciation]) -> str:
    us = [p for p in prons if p.region == "US" and p.ipa]
    uk = [p for p in prons if p.region == "UK" and p.ipa]
    parts = []
    if us:
        parts.append("US: " + "; ".join(_link(p) for p in us))
    if uk:
        parts.append("UK: " + "; ".join(_link(p) for p in uk))
    return " ".join(parts)


def _link(p: Pronunciation) -> str:
    if p.audio_url:
        href = p.audio_url if p.audio_url.startswith("http") else CAMBRIDGE_BASE + p.audio_url
        return f"[{p.ipa}]({href})"
    return p.ipa


def render_row(
    entry: WordEntry,
    extras: Extras,
    sense_index: int,
    opts: RenderOptions,
) -> str:
    sense = entry.senses[sense_index]
    pos = sense.pos
    cells = [entry.word, pos, sense.text]
    if opts.include_synonyms:
        cells.append(_format_synonyms(pos, extras.synonyms))
    cells.append(_format_inflections(pos, extras.inflections))
    if opts.include_audio:
        prons = entry.pronunciations.get(pos, [])
        group = prons[sense.pron_group] if sense.pron_group < len(prons) else []
        cells.append(_format_prons(group))
    cells.append(f"[^_^]({CAMBRIDGE_URL.format(word=entry.word)})")
    return "|" + "|".join(cells) + "|\n"
