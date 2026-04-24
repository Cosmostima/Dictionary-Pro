UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRIES = 2

CAMBRIDGE_URL = "https://dictionary.cambridge.org/us/dictionary/english/{word}"
WIKTIONARY_URL = "https://simple.wiktionary.org/wiki/{word}"
THESAURUS_URL = "https://www.freethesaurus.com/{word}"
CAMBRIDGE_BASE = "https://dictionary.cambridge.org"

CANONICAL_POS = {
    "noun", "verb", "adjective", "adverb",
    "preposition", "conjunction", "exclamation", "pronoun",
    "determiner", "number", "auxiliary verb", "",
}

# Map aliases from Wiktionary / FreeThesaurus to canonical Cambridge names.
POS_ALIAS = {
    "coordinator": "conjunction",
    "interjection": "exclamation",
    "adj": "adjective",
    "adv": "adverb",
    "prep": "preposition",
    "conj": "conjunction",
    "noun": "noun",
    "verb": "verb",
    "pronoun": "pronoun",
    "determiner": "determiner",
}


def normalize_pos(raw: str) -> str:
    if not raw:
        return ""
    key = raw.strip().lower()
    return POS_ALIAS.get(key, key)
