from __future__ import annotations

from pathlib import Path

import pytest

from dictpro.cli import build_parser, resolve_output_path


def test_parser_agent_flags():
    p = build_parser()
    args = p.parse_args(["-q", "foo"])
    assert args.query == "foo"
    assert args.batch is None

    args = p.parse_args(["-b", "words.txt"])
    assert args.batch == "words.txt"
    assert args.query is None


def test_parser_query_and_batch_mutually_exclusive():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["-q", "foo", "-b", "words.txt"])


def test_parser_rejects_old_flags():
    p = build_parser()
    for bad in (["--name", "x"], ["--path", "x.md"], ["--head"]):
        with pytest.raises(SystemExit):
            p.parse_args(bad)


def test_parser_rejects_pick_flag():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["-q", "foo", "--pick", "0"])


def test_resolve_output_auto_appends_md(tmp_path):
    (tmp_path / "notes").mkdir()
    assert resolve_output_path(str(tmp_path / "vocab")) == tmp_path / "vocab.md"
    assert resolve_output_path(str(tmp_path / "vocab.md")) == tmp_path / "vocab.md"
    assert resolve_output_path(str(tmp_path / "notes" / "book")) == tmp_path / "notes" / "book.md"


def test_resolve_output_errors_on_missing_parent(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve_output_path(str(tmp_path / "no_such_dir" / "vocab.md"))


def test_resolve_output_none_returns_none():
    assert resolve_output_path(None) is None
    assert resolve_output_path("") is None
