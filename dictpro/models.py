from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Pronunciation:
    region: Literal["US", "UK"]
    ipa: str
    audio_url: str  # may be absolute URL or path starting with "/"


@dataclass(frozen=True)
class Sense:
    pos: str         # canonical POS (Cambridge long name) or ""
    text: str
    pron_group: int  # index into WordEntry.pronunciations[pos]


@dataclass
class WordEntry:
    word: str
    senses: list[Sense] = field(default_factory=list)
    pronunciations: dict[str, list[list[Pronunciation]]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.senses


@dataclass(frozen=True)
class Inflection:
    kind: str
    text: str


@dataclass
class Extras:
    inflections: dict[str, list[Inflection]] = field(default_factory=dict)
    synonyms: dict[str, list[str]] = field(default_factory=dict)
