from __future__ import annotations

from bs4 import BeautifulSoup

from ..constants import normalize_pos
from ..models import Pronunciation, Sense, WordEntry


def _extract_prons(body, region_cls: str, region: str) -> list[Pronunciation]:
    out: list[Pronunciation] = []
    for pr in body.find_all("span", class_=region_cls):
        au = pr.find("source", type="audio/mpeg")
        text = pr.find("span", class_="pron dpron")
        out.append(
            Pronunciation(
                region=region,  # type: ignore[arg-type]
                ipa=text.text if text else "",
                audio_url=au.get("src") if au else "",
            )
        )
    return out


def parse_cambridge(html: str, word: str) -> WordEntry:
    """Parse Cambridge dictionary entry HTML into a WordEntry.

    Flattens senses across all POS into a single indexable list; each sense
    carries its own POS + pron_group so renderer can look up pronunciation.
    """
    soup = BeautifulSoup(html, "html.parser")
    entry = WordEntry(word=word)
    pron_groups: dict[str, list[list[Pronunciation]]] = {}
    senses: list[Sense] = []

    for body in soup.find_all("div", class_="pr entry-body__el"):
        us = _extract_prons(body, "us dpron-i", "US")
        uk = _extract_prons(body, "uk dpron-i", "UK")

        pos_raw = body.find("span", class_="pos dpos")
        if pos_raw:
            pos = normalize_pos(pos_raw.text)
            def_wrapper = body.find("div", class_="sense-body dsense_b")
            if def_wrapper:
                def_blocks = def_wrapper.find_all(
                    "div", class_="def-block ddef_block", recursive=False
                )
            else:
                def_blocks = []
        else:
            pos = ""
            single = body.find("div", class_="def-block ddef_block")
            def_blocks = [single] if single else []

        groups = pron_groups.setdefault(pos, [])
        groups.append([*us, *uk])
        group_idx = len(groups) - 1

        for block in def_blocks:
            d = block.find("div", class_="def ddef_d db")
            if not d:
                continue
            text = d.text.replace(": ", "").replace("\n", ": ").strip()
            senses.append(Sense(pos=pos, text=text, pron_group=group_idx))

    entry.senses = senses
    entry.pronunciations = pron_groups
    return entry
