"""Backward-compatible entry point for Dictionary Pro.

The interactive + Cambridge / Wiktionary / FreeThesaurus logic now lives in
the `dictpro` package. This file is kept so existing command lines
(`python main.py ...`) continue to work.
"""
from dictpro.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
