"""Agent-mode helpers: JSON serialization, single/batch query drivers."""
from __future__ import annotations

import json
import sys
from typing import Any, Iterable, TextIO

from .concurrent import LookupResult, fetch_all


def result_to_json(result: LookupResult) -> dict[str, Any]:
    entry = result.entry
    ok = entry is not None and bool(entry.senses)

    out: dict[str, Any] = {"word": result.word, "ok": ok}

    out["senses"] = (
        [{"i": i, "pos": s.pos, "text": s.text} for i, s in enumerate(entry.senses)]
        if entry is not None
        else []
    )

    if entry is not None and entry.pronunciations:
        out["pronunciations"] = {
            pos: [
                [{"region": p.region, "ipa": p.ipa, "audio": p.audio_url} for p in group]
                for group in groups
            ]
            for pos, groups in entry.pronunciations.items()
        }

    infl = {
        pos: [item.text for item in items]
        for pos, items in result.extras.inflections.items()
        if items
    }
    if infl:
        out["inflections"] = infl

    syn = {pos: v for pos, v in result.extras.synonyms.items() if v}
    if syn:
        out["synonyms"] = syn

    if result.errors:
        out["errors"] = dict(result.errors)

    return out


def run_single(word: str) -> int:
    result = fetch_all(word)
    payload = result_to_json(result)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 2


def _iter_words(source: TextIO) -> Iterable[str]:
    for raw in source:
        line = raw.rstrip("\n").rstrip("\r")
        stripped = line.strip()
        if not stripped:
            continue
        if any(ord(ch) < 0x20 for ch in stripped):
            print(f":) skipping line with control chars: {stripped!r}", file=sys.stderr)
            continue
        yield stripped


def run_batch(source_path: str) -> int:
    if source_path == "-":
        source = sys.stdin
        close_source = False
    else:
        try:
            source = open(source_path, "r", encoding="utf-8")
        except OSError as exc:
            print(f":) cannot open input: {exc}", file=sys.stderr)
            return 1
        close_source = True

    any_ok = False
    any_row = False
    try:
        for word in _iter_words(source):
            any_row = True
            result = fetch_all(word)
            payload = result_to_json(result)
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            if payload["ok"]:
                any_ok = True
    finally:
        if close_source:
            source.close()

    if not any_row:
        return 2
    return 0 if any_ok else 2
