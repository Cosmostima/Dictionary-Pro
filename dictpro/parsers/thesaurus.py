from __future__ import annotations

from bs4 import BeautifulSoup

from ..constants import normalize_pos


def parse_thesaurus(html: str) -> dict[str, list[str]]:
    """Parse FreeThesaurus synonyms page. Returns {canonical_pos: [word, ...]}.

    Returns empty dict for disambiguation pages or missing sections.
    """
    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", {"data-src": "hc_thes"})
    if not section:
        return {}
    tm = section.find("div", class_="TM")
    if not tm:
        return {}

    out: dict[str, list[str]] = {}
    for block in tm.find_all("div", recursive=False):
        pos_raw = block.get("data-part") or ""
        pos = normalize_pos(pos_raw)
        h3 = block.find("h3")
        if not h3:
            continue
        text = h3.text.strip()
        out.setdefault(pos, []).append(text)
    return out
