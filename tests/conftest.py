from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent / "golden"
WORDS = ["swarm", "good", "who", "run", "nonexistent_xyz"]


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return GOLDEN


def load_html(site: str, word: str) -> str:
    return (FIXTURES / site / f"{word}.html").read_text(encoding="utf-8")


def load_golden(word: str) -> dict:
    return json.loads((GOLDEN / f"{word}.json").read_text(encoding="utf-8"))
