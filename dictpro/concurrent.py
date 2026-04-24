from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .constants import CAMBRIDGE_URL, THESAURUS_URL, WIKTIONARY_URL
from .fetchers import FetchError, NotFound, http_get
from .models import Extras, Inflection, WordEntry
from .parsers import parse_cambridge, parse_thesaurus, parse_wiktionary


@dataclass
class LookupResult:
    word: str
    entry: WordEntry | None
    extras: Extras
    errors: dict[str, str]  # source -> error message (empty if all ok)


def _safe(fn, *args):
    try:
        return fn(*args), None
    except NotFound as exc:
        return None, f"404 {exc}"
    except FetchError as exc:
        return None, str(exc)
    except Exception as exc:  # parser crash — keep going, return empty
        return None, f"{type(exc).__name__}: {exc}"


def _cam(word: str) -> WordEntry:
    return parse_cambridge(http_get(CAMBRIDGE_URL.format(word=word)), word)


def _wik(word: str) -> dict[str, list[Inflection]]:
    return parse_wiktionary(http_get(WIKTIONARY_URL.format(word=word)))


def _syn(word: str) -> dict[str, list[str]]:
    return parse_thesaurus(http_get(THESAURUS_URL.format(word=word)))


def fetch_all(word: str) -> LookupResult:
    """Fetch three sources concurrently. Missing sources degrade gracefully."""
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_cam = ex.submit(_safe, _cam, word)
        f_wik = ex.submit(_safe, _wik, word)
        f_syn = ex.submit(_safe, _syn, word)
        entry, err_cam = f_cam.result()
        infl, err_wik = f_wik.result()
        syn, err_syn = f_syn.result()
    if err_cam:
        errors["cambridge"] = err_cam
    if err_wik:
        errors["wiktionary"] = err_wik
    if err_syn:
        errors["thesaurus"] = err_syn
    extras = Extras(inflections=infl or {}, synonyms=syn or {})
    return LookupResult(word=word, entry=entry, extras=extras, errors=errors)
