from __future__ import annotations

from bs4 import BeautifulSoup

from ..constants import normalize_pos
from ..models import Inflection


def parse_wiktionary(html: str) -> dict[str, list[Inflection]]:
    """Parse Simple Wiktionary inflection tables.

    Returns {canonical_pos: [Inflection(kind, text), ...]}.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, list[Inflection]] = {}

    headings = [
        h for h in soup.find_all("h2", id=True)
        if h.get("id") != "mw-toc-heading"
    ]
    for h in headings:
        pos = normalize_pos(h.get("id") or "")
        table = h.find_next("table")
        if table is None:
            continue
        # Use explicit separator so <br/> boundaries survive.
        raw = table.get_text(separator="\n")
        lines = [line.strip() for line in raw.splitlines() if line.strip()]

        inflections: list[Inflection] = []
        i = 0
        while i + 1 < len(lines):
            inflections.append(Inflection(kind=lines[i], text=lines[i + 1]))
            i += 2
        if i < len(lines):  # odd trailing item — keep with empty kind
            inflections.append(Inflection(kind="", text=lines[i]))

        if pos in out:
            out[pos].extend(inflections)
        else:
            out[pos] = inflections
    return out
