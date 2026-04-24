"""Download HTML fixtures for offline tests.

Run once with network access:
    python scripts/capture_fixtures.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dictpro.constants import CAMBRIDGE_URL, THESAURUS_URL, WIKTIONARY_URL  # noqa: E402
from dictpro.fetchers import FetchError, NotFound, http_get  # noqa: E402

WORDS = ["swarm", "good", "who", "run", "nonexistent_xyz"]
SITES = {
    "cambridge": CAMBRIDGE_URL,
    "wiktionary": WIKTIONARY_URL,
    "thesaurus": THESAURUS_URL,
}

FIXTURES = ROOT / "tests" / "fixtures"


def main() -> int:
    for site, tpl in SITES.items():
        out_dir = FIXTURES / site
        out_dir.mkdir(parents=True, exist_ok=True)
        for word in WORDS:
            dest = out_dir / f"{word}.html"
            if dest.exists():
                print(f"[skip] {dest.relative_to(ROOT)}")
                continue
            url = tpl.format(word=word)
            try:
                html = http_get(url)
                dest.write_text(html, encoding="utf-8")
                print(f"[ok]   {dest.relative_to(ROOT)} ({len(html)} bytes)")
            except NotFound:
                dest.write_text("", encoding="utf-8")
                print(f"[404]  {dest.relative_to(ROOT)} (empty)")
            except FetchError as exc:
                print(f"[err]  {url}: {exc}")
            time.sleep(0.4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
