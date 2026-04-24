# Agent CLI Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `-q/--query`, `-b/--batch`, and `--pick` to `dictpro` so AI agents can call it non-interactively for single or batch word lookups, with JSON/NDJSON stdout and deterministic exit codes; simultaneously unify `--name`/`--path` → `-o`, rename `--head` → `--rewrite-header`, without breaking the existing interactive mode.

**Architecture:** A new `dictpro/agent.py` module holds agent-mode logic (pick-spec parsing, JSON serialization, single/batch drivers). `dictpro/cli.py` is refactored to a thin dispatcher: parse args, choose agent-mode vs interactive-mode, delegate. The existing `concurrent.fetch_all` and `renderer.render_row` stay unchanged and are called from both paths. Shared `write_senses` helper is lifted out of `_lookup_and_write`.

**Tech Stack:** Python 3.10+, stdlib (`argparse`, `json`, `sys`, `pathlib`), `pytest` for tests. No new deps.

**Reference spec:** `docs/superpowers/specs/2026-04-22-agent-cli-mode-design.md`

---

## Preconditions

Before Task 1, verify environment:

- [ ] **Step 0.1: Ensure Python 3.10+ and pytest available**

Run:
```bash
python3 --version
# If < 3.10, install via pyenv: `pyenv install 3.11.9 && pyenv local 3.11.9`
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[test]'
pytest --version
```
Expected: Python ≥ 3.10, pytest ≥ 7.

- [ ] **Step 0.2: Run existing test suite to confirm baseline**

Run: `pytest -q`
Expected: all tests pass (online-marked tests skipped).

---

## File Structure

**Create:**
- `dictpro/agent.py` — agent-mode logic (pick parsing, JSON serialization, single/batch drivers, shared write helper)
- `tests/test_agent_serialize.py` — unit tests for `result_to_json`
- `tests/test_agent_pick.py` — unit tests for `parse_pick_spec`, `select_indices`
- `tests/test_cli_agent.py` — end-to-end tests invoking `main(argv)` for `-q`/`-b`

**Modify:**
- `dictpro/cli.py` — argparse changes, dispatch to agent or interactive, import write helper from agent.py

**Unchanged:**
- `dictpro/concurrent.py`, `dictpro/renderer.py`, `dictpro/models.py`, `dictpro/parsers/*`, `dictpro/fetchers.py`, `dictpro/constants.py`

---

## Task 1: Extract `write_senses` helper + add `result_to_json`

**Rationale:** Pure refactor first — decouples write-to-md from interactive UI, gives agent mode a shared building block, and a JSON serializer with tests locks in the schema contract before any CLI wiring.

**Files:**
- Create: `dictpro/agent.py`
- Create: `tests/test_agent_serialize.py`
- Modify: `dictpro/cli.py` (extract helper, import from agent.py)

### Step 1.1: Write failing tests for `result_to_json`

- [ ] Create `tests/test_agent_serialize.py`:

```python
from __future__ import annotations

from dictpro.agent import result_to_json
from dictpro.concurrent import LookupResult
from dictpro.models import Extras, Inflection, Pronunciation, Sense, WordEntry


def _result_ok() -> LookupResult:
    entry = WordEntry(
        word="swarm",
        senses=[
            Sense(pos="noun", text="a large group", pron_group=0),
            Sense(pos="verb", text="to move in a swarm", pron_group=0),
        ],
        pronunciations={
            "noun": [[
                Pronunciation("US", "/swɔːrm/", "/us.mp3"),
                Pronunciation("UK", "/swɔːm/", "/uk.mp3"),
            ]],
            "verb": [[]],
        },
    )
    extras = Extras(
        inflections={"noun": [Inflection("Plural", "swarms")]},
        synonyms={"noun": ["multitude"]},
    )
    return LookupResult(word="swarm", entry=entry, extras=extras, errors={})


def test_result_to_json_success_shape():
    r = _result_ok()
    out = result_to_json(r, written=None)
    assert out["word"] == "swarm"
    assert out["ok"] is True
    assert out["senses"] == [
        {"i": 0, "pos": "noun", "text": "a large group"},
        {"i": 1, "pos": "verb", "text": "to move in a swarm"},
    ]
    assert out["inflections"] == {"noun": ["swarms"]}
    assert out["synonyms"] == {"noun": ["multitude"]}
    assert out["pronunciations"]["noun"][0][0] == {
        "region": "US", "ipa": "/swɔːrm/", "audio": "/us.mp3",
    }
    # errors omitted when empty
    assert "errors" not in out
    # written omitted when None
    assert "written" not in out


def test_result_to_json_written_present_when_wrote():
    r = _result_ok()
    out = result_to_json(r, written=[0, 1])
    assert out["written"] == [0, 1]


def test_result_to_json_not_found():
    r = LookupResult(
        word="xyznope",
        entry=None,
        extras=Extras(),
        errors={"cambridge": "404 https://...", "wiktionary": "404 https://..."},
    )
    out = result_to_json(r, written=None)
    assert out["word"] == "xyznope"
    assert out["ok"] is False
    assert out["senses"] == []
    assert out["errors"] == {"cambridge": "404 https://...", "wiktionary": "404 https://..."}
    assert "inflections" not in out
    assert "synonyms" not in out
    assert "pronunciations" not in out


def test_result_to_json_partial_errors_only_failing_sources():
    r = _result_ok()
    r.errors = {"wiktionary": "timeout"}
    out = result_to_json(r, written=None)
    assert out["ok"] is True
    assert out["errors"] == {"wiktionary": "timeout"}


def test_result_to_json_empty_source_dicts_omitted():
    # entry present but thesaurus returned empty dict — omit synonyms key
    entry = WordEntry(
        word="x",
        senses=[Sense(pos="noun", text="t", pron_group=0)],
        pronunciations={"noun": [[]]},
    )
    r = LookupResult(word="x", entry=entry, extras=Extras(), errors={})
    out = result_to_json(r, written=None)
    assert "synonyms" not in out
    assert "inflections" not in out
```

### Step 1.2: Run tests — expect failure

Run: `pytest tests/test_agent_serialize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dictpro.agent'`.

### Step 1.3: Create `dictpro/agent.py` with `result_to_json`

- [ ] Create `dictpro/agent.py`:

```python
"""Agent-mode helpers: JSON serialization, pick parsing, single/batch drivers."""
from __future__ import annotations

from typing import Any

from .concurrent import LookupResult
from .models import WordEntry


def result_to_json(result: LookupResult, written: list[int] | None) -> dict[str, Any]:
    """Serialize a LookupResult to the agent-facing JSON schema.

    Keys omitted when empty (errors, inflections, synonyms, pronunciations, written).
    """
    entry = result.entry
    ok = entry is not None and bool(entry.senses)

    out: dict[str, Any] = {"word": result.word, "ok": ok}

    out["senses"] = (
        [
            {"i": i, "pos": s.pos, "text": s.text}
            for i, s in enumerate(entry.senses)
        ]
        if entry is not None
        else []
    )

    if entry is not None and entry.pronunciations:
        out["pronunciations"] = {
            pos: [
                [
                    {"region": p.region, "ipa": p.ipa, "audio": p.audio_url}
                    for p in group
                ]
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

    if written is not None:
        out["written"] = written

    return out
```

### Step 1.4: Run tests — expect pass

Run: `pytest tests/test_agent_serialize.py -v`
Expected: all 5 tests PASS.

### Step 1.5: Extract `write_senses` into `dictpro/agent.py`

Current `dictpro/cli.py:72-86` `_lookup_and_write` conflates fetching + prompting + writing. Lift the write-only portion into a reusable helper.

- [ ] Append to `dictpro/agent.py`:

```python
from .renderer import RenderOptions, render_row


def write_senses(
    result: LookupResult,
    indices: list[int],
    out_file,
    opts: RenderOptions,
) -> list[int]:
    """Write selected senses to an already-open md file. Returns indices actually written.

    Silently filters out indices that are out of range for this entry.
    """
    entry = result.entry
    if entry is None:
        return []
    written: list[int] = []
    for n in indices:
        if 0 <= n < len(entry.senses):
            out_file.write(render_row(entry, result.extras, n, opts))
            written.append(n)
    if written:
        out_file.flush()
    return written
```

### Step 1.6: Refactor `cli.py::_lookup_and_write` to use `write_senses`

- [ ] Modify `dictpro/cli.py` — replace the body of `_lookup_and_write` to delegate writing. Open the file and replace these lines:

Current `dictpro/cli.py:72-86`:
```python
def _lookup_and_write(word: str, out_file, opts: RenderOptions) -> bool:
    result: LookupResult = fetch_all(word)
    if result.entry is None or not result.entry.senses:
        print(f":) Word not found: {word} ({'; '.join(result.errors.values())})")
        return False
    print("-" * 20)
    print(word)
    _print_senses(result.entry)
    picks = _prompt("pick> ")
    if picks.strip() == "/x":
        return False
    for n in _parse_indices(picks, len(result.entry.senses)):
        out_file.write(render_row(result.entry, result.extras, n, opts))
    out_file.flush()
    return True
```

Replace with:
```python
def _lookup_and_write(word: str, out_file, opts: RenderOptions) -> bool:
    result: LookupResult = fetch_all(word)
    if result.entry is None or not result.entry.senses:
        print(f":) Word not found: {word} ({'; '.join(result.errors.values())})")
        return False
    print("-" * 20)
    print(word)
    _print_senses(result.entry)
    picks = _prompt("pick> ")
    if picks.strip() == "/x":
        return False
    indices = _parse_indices(picks, len(result.entry.senses))
    write_senses(result, indices, out_file, opts)
    return True
```

And at the top of `dictpro/cli.py`, remove the now-unused `render_row` import and add `write_senses`:
```python
from .agent import write_senses
from .renderer import RenderOptions, header
```
(Remove `render_row` from the `.renderer` import.)

### Step 1.7: Run all tests — expect pass

Run: `pytest -q`
Expected: all tests pass (existing + 5 new).

### Step 1.8: Commit

Run:
```bash
git add dictpro/agent.py dictpro/cli.py tests/test_agent_serialize.py
git commit -m "refactor: extract write_senses + add result_to_json serializer

Prepares for agent CLI mode — decouples md writing from the interactive
prompt loop and locks in the agent-facing JSON schema with unit tests."
```

---

## Task 2: Pick spec parsing + `select_indices`

**Files:**
- Modify: `dictpro/agent.py`
- Create: `tests/test_agent_pick.py`

### Step 2.1: Write failing tests

- [ ] Create `tests/test_agent_pick.py`:

```python
from __future__ import annotations

import pytest

from dictpro.agent import parse_pick_spec, select_indices, PickSpecError
from dictpro.models import Sense, WordEntry


def _entry_multi_pos() -> WordEntry:
    return WordEntry(
        word="run",
        senses=[
            Sense(pos="verb", text="to move fast", pron_group=0),
            Sense(pos="verb", text="to operate", pron_group=0),
            Sense(pos="noun", text="a jog", pron_group=0),
            Sense(pos="noun", text="a streak", pron_group=0),
        ],
    )


def test_parse_numeric_list_single_mode():
    assert parse_pick_spec("0,2,5", batch=False) == ("numeric", [0, 2, 5])


def test_parse_numeric_list_rejects_in_batch_mode():
    with pytest.raises(PickSpecError, match="numeric"):
        parse_pick_spec("0,2", batch=True)


def test_parse_strategies():
    for name in ("first", "first-per-pos", "all"):
        assert parse_pick_spec(name, batch=False) == (name, None)
        assert parse_pick_spec(name, batch=True) == (name, None)


def test_parse_empty_or_invalid():
    with pytest.raises(PickSpecError):
        parse_pick_spec("", batch=False)
    with pytest.raises(PickSpecError):
        parse_pick_spec("bogus", batch=False)
    with pytest.raises(PickSpecError):
        parse_pick_spec("0,abc", batch=False)
    with pytest.raises(PickSpecError):
        parse_pick_spec("-1", batch=False)


def test_select_first():
    entry = _entry_multi_pos()
    assert select_indices(entry, ("first", None)) == [0]


def test_select_first_per_pos():
    entry = _entry_multi_pos()
    # senses are grouped verb, verb, noun, noun — first of each pos = indices 0, 2
    assert select_indices(entry, ("first-per-pos", None)) == [0, 2]


def test_select_all():
    entry = _entry_multi_pos()
    assert select_indices(entry, ("all", None)) == [0, 1, 2, 3]


def test_select_numeric_filters_out_of_range():
    entry = _entry_multi_pos()
    assert select_indices(entry, ("numeric", [0, 9, 3])) == [0, 3]


def test_select_empty_entry():
    entry = WordEntry(word="x", senses=[])
    assert select_indices(entry, ("first", None)) == []
    assert select_indices(entry, ("all", None)) == []
```

### Step 2.2: Run tests — expect failure

Run: `pytest tests/test_agent_pick.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_pick_spec'`.

### Step 2.3: Implement `parse_pick_spec` and `select_indices`

- [ ] Append to `dictpro/agent.py`:

```python
PickStrategy = tuple[str, list[int] | None]  # ("numeric", [0,2]) | ("first", None) | ...

_NAMED_STRATEGIES = {"first", "first-per-pos", "all"}


class PickSpecError(ValueError):
    """Raised when --pick spec is malformed or incompatible with the mode."""


def parse_pick_spec(spec: str, *, batch: bool) -> PickStrategy:
    s = spec.strip()
    if not s:
        raise PickSpecError("empty --pick spec")
    if s in _NAMED_STRATEGIES:
        return (s, None)
    if any(ch.isdigit() for ch in s) or "," in s:
        if batch:
            raise PickSpecError(
                "numeric --pick spec not allowed in batch mode; "
                "use first | first-per-pos | all"
            )
        out: list[int] = []
        for piece in s.split(","):
            piece = piece.strip()
            if not piece:
                raise PickSpecError(f"empty index in spec: {spec!r}")
            try:
                n = int(piece)
            except ValueError as exc:
                raise PickSpecError(f"invalid index: {piece!r}") from exc
            if n < 0:
                raise PickSpecError(f"negative index: {n}")
            out.append(n)
        return ("numeric", out)
    raise PickSpecError(
        f"unknown --pick spec: {spec!r} "
        f"(use first | first-per-pos | all | 0,2,5)"
    )


def select_indices(entry: WordEntry, strategy: PickStrategy) -> list[int]:
    name, payload = strategy
    senses = entry.senses
    if not senses:
        return []
    if name == "numeric":
        assert payload is not None
        return [n for n in payload if 0 <= n < len(senses)]
    if name == "first":
        return [0]
    if name == "all":
        return list(range(len(senses)))
    if name == "first-per-pos":
        seen: set[str] = set()
        out: list[int] = []
        for i, s in enumerate(senses):
            if s.pos not in seen:
                seen.add(s.pos)
                out.append(i)
        return out
    raise PickSpecError(f"unknown strategy: {name}")
```

### Step 2.4: Run tests — expect pass

Run: `pytest tests/test_agent_pick.py -v`
Expected: all 10 tests PASS.

### Step 2.5: Commit

Run:
```bash
git add dictpro/agent.py tests/test_agent_pick.py
git commit -m "feat: add --pick spec parsing and index selection

Supports numeric lists (0,2,5), 'first', 'first-per-pos', and 'all'.
Batch mode rejects numeric specs at parse time — each word in a batch
has different valid indices, so explicit numbers are meaningless."
```

---

## Task 3: Refactor CLI args — `-o` / `--rewrite-header`, delete `--name`/`--path`/`--head`

**Files:**
- Modify: `dictpro/cli.py`
- Create: `tests/test_cli_args.py`

### Step 3.1: Write failing tests

- [ ] Create `tests/test_cli_args.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from dictpro.cli import build_parser, resolve_output_path


def test_parser_has_new_flags():
    p = build_parser()
    args = p.parse_args(["-q", "foo", "--pick", "0", "-o", "vocab", "--rewrite-header"])
    assert args.query == "foo"
    assert args.pick == "0"
    assert args.output == "vocab"
    assert args.rewrite_header is True


def test_parser_query_and_batch_mutually_exclusive():
    p = build_parser()
    with pytest.raises(SystemExit):
        p.parse_args(["-q", "foo", "-b", "words.txt"])


def test_parser_rejects_old_flags():
    p = build_parser()
    for bad in (["--name", "x"], ["--path", "x.md"], ["--head"]):
        with pytest.raises(SystemExit):
            p.parse_args(bad)


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
```

### Step 3.2: Run tests — expect failure

Run: `pytest tests/test_cli_args.py -v`
Expected: FAIL (imports missing or old flags accepted).

### Step 3.3: Rewrite `dictpro/cli.py::build_parser` and add `resolve_output_path`

- [ ] Replace `dictpro/cli.py:89-105` (the current `build_parser`) with the new parser. Also add `resolve_output_path` as a module-level helper. Full replacement of those lines:

```python
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dictpro")

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "-q", "--query", default=None, metavar="WORD",
        help="Agent mode: look up a single word non-interactively.",
    )
    mode.add_argument(
        "-b", "--batch", default=None, metavar="FILE",
        help="Agent mode: batch lookup. FILE is a path or '-' for stdin "
             "(one word per line).",
    )
    p.add_argument(
        "--pick", default=None, metavar="SPEC",
        help="Which senses to write to md. Values: 0,2,5 (single mode only) | "
             "first | first-per-pos | all. Omit to skip writing.",
    )
    p.add_argument(
        "-o", "--output", default=None, metavar="PATH",
        help="Output md path. '.md' auto-appended if missing. "
             "Omit in agent mode to skip writing.",
    )
    p.add_argument(
        "--audio", action=argparse.BooleanOptionalAction, default=True,
        help="Include pronunciation column in md output.",
    )
    p.add_argument(
        "--synonym", action=argparse.BooleanOptionalAction, default=True,
        help="Include synonym column in md output.",
    )
    p.add_argument(
        "--rewrite-header", action="store_true", default=False,
        help="Rewrite the md header even if the file already exists.",
    )
    return p


def resolve_output_path(raw: str | None) -> Path | None:
    """Normalize -o value: auto-append .md, verify parent dir exists.

    Returns None when raw is empty/None (= 'no write'). Raises FileNotFoundError
    if the parent directory is missing.
    """
    if not raw:
        return None
    p = Path(raw)
    if p.suffix != ".md":
        p = p.with_suffix(".md")
    parent = p.parent if str(p.parent) != "" else Path(".")
    if not parent.exists():
        raise FileNotFoundError(f"output parent directory does not exist: {parent}")
    return p
```

### Step 3.4: Adjust `main()` to use the new args

The existing `main()` body (`dictpro/cli.py:108-120`) references `args.name`, `args.path`, `args.head`, and calls `_resolve_path(args)`. These no longer exist. Temporarily keep `main()` working in interactive-only form for Task 3 — we'll add the agent dispatch in Task 4.

- [ ] Replace the body of `main()` with:

```python
def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    # Agent mode is wired in Task 4; for now, only interactive mode works.
    if args.query is not None or args.batch is not None:
        print(":) agent mode not yet wired (Task 4)", file=sys.stderr)
        return 1
    opts = RenderOptions(include_audio=args.audio, include_synonyms=args.synonym)
    try:
        out_path = resolve_output_path(args.output)
    except FileNotFoundError as exc:
        print(f":) {exc}", file=sys.stderr)
        return 1
    if out_path is None:
        name = _prompt(":) Please input the file name: ")
        out_path = Path(f"./{name}.md")
    with _open_output(out_path, args.rewrite_header, opts) as f:
        while True:
            inp = _prompt("word> ")
            if inp.strip() == "/q":
                break
            for word in (w.strip() for w in inp.split(",") if w.strip()):
                _lookup_and_write(word, f, opts)
    return 0
```

Also delete `_resolve_path` (lines ~60-69) — it's superseded by `resolve_output_path` + the inline interactive prompt above.

### Step 3.5: Run tests — expect pass

Run: `pytest tests/test_cli_args.py -v && pytest -q`
Expected: all tests pass.

### Step 3.6: Commit

Run:
```bash
git add dictpro/cli.py tests/test_cli_args.py
git commit -m "refactor: unify --name/--path into -o, rename --head to --rewrite-header

Deletes --name, --path, --head. -o auto-appends .md when missing and
validates parent-dir existence. Adds -q/-b/--pick flags (agent dispatch
wired in next commit). Interactive mode still works identically."
```

---

## Task 4: Agent single-query mode (`-q`)

**Files:**
- Modify: `dictpro/agent.py` (add `run_single`)
- Modify: `dictpro/cli.py` (dispatch to `run_single`)
- Create: `tests/test_cli_agent.py`

### Step 4.1: Write failing tests

- [ ] Create `tests/test_cli_agent.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dictpro import agent, concurrent
from dictpro.cli import main
from dictpro.models import Extras, Inflection, Pronunciation, Sense, WordEntry


def _ok(word: str) -> concurrent.LookupResult:
    return concurrent.LookupResult(
        word=word,
        entry=WordEntry(
            word=word,
            senses=[
                Sense(pos="noun", text="first def", pron_group=0),
                Sense(pos="verb", text="second def", pron_group=0),
            ],
            pronunciations={"noun": [[Pronunciation("US", "/x/", "/a.mp3")]], "verb": [[]]},
        ),
        extras=Extras(
            inflections={"noun": [Inflection("Plural", word + "s")]},
            synonyms={"noun": ["alt"]},
        ),
        errors={},
    )


def _nf(word: str) -> concurrent.LookupResult:
    return concurrent.LookupResult(
        word=word, entry=None, extras=Extras(),
        errors={"cambridge": "404"},
    )


@pytest.fixture
def mock_fetch(monkeypatch):
    """Mock concurrent.fetch_all — and also the reference inside agent.py."""
    calls: dict[str, concurrent.LookupResult] = {}

    def _fake(word: str) -> concurrent.LookupResult:
        return calls.get(word, _nf(word))

    monkeypatch.setattr(concurrent, "fetch_all", _fake)
    monkeypatch.setattr(agent, "fetch_all", _fake)
    return calls


def test_query_json_only_no_write(mock_fetch, capsys):
    mock_fetch["serendipity"] = _ok("serendipity")
    rc = main(["-q", "serendipity"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["word"] == "serendipity"
    assert out["ok"] is True
    assert out["senses"][0] == {"i": 0, "pos": "noun", "text": "first def"}
    assert "written" not in out


def test_query_with_pick_writes_md_and_reports_written(mock_fetch, tmp_path, capsys):
    mock_fetch["serendipity"] = _ok("serendipity")
    out_file = tmp_path / "vocab"  # no .md on purpose — should auto-append
    rc = main(["-q", "serendipity", "--pick", "0,1", "-o", str(out_file)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["written"] == [0, 1]
    md = (tmp_path / "vocab.md").read_text()
    # Header + two rows
    assert md.count("|serendipity|") == 2
    assert "first def" in md and "second def" in md


def test_query_output_without_pick_is_usage_error(mock_fetch, tmp_path, capsys):
    mock_fetch["foo"] = _ok("foo")
    rc = main(["-q", "foo", "-o", str(tmp_path / "vocab.md")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "--pick" in err


def test_query_not_found_exit_2(mock_fetch, capsys):
    rc = main(["-q", "xyznope"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert "errors" in out


def test_query_pick_first_per_pos(mock_fetch, tmp_path, capsys):
    mock_fetch["run"] = _ok("run")
    out_file = tmp_path / "v.md"
    rc = main(["-q", "run", "--pick", "first-per-pos", "-o", str(out_file)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["written"] == [0, 1]  # noun at 0, verb at 1 in the _ok fixture


def test_query_numeric_pick_out_of_range_silently_filtered(mock_fetch, tmp_path, capsys):
    mock_fetch["foo"] = _ok("foo")
    out_file = tmp_path / "v.md"
    rc = main(["-q", "foo", "--pick", "0,99", "-o", str(out_file)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["written"] == [0]
```

### Step 4.2: Run tests — expect failure

Run: `pytest tests/test_cli_agent.py -v`
Expected: FAIL (agent dispatch not yet wired; calls fall through to the stub from Task 3).

### Step 4.3: Add `run_single` to `dictpro/agent.py`

- [ ] Append to `dictpro/agent.py`:

```python
import json
import sys
from pathlib import Path

from .concurrent import fetch_all
from .renderer import RenderOptions, header as md_header


def _open_md(path: Path, rewrite_header: bool, opts: RenderOptions):
    exists = path.exists()
    f = path.open("a", encoding="utf-8")
    if not exists or rewrite_header:
        f.write(md_header(opts))
    return f


def run_single(
    word: str,
    *,
    pick: str | None,
    output: Path | None,
    rewrite_header: bool,
    opts: RenderOptions,
) -> int:
    """Agent single-query driver. Returns exit code.

    - Writes JSON to stdout.
    - If `output` given but `pick` not, returns 1 with stderr message.
    - Exit 2 when the word was not found (no senses).
    """
    if output is not None and pick is None:
        print(":) -o/--output requires --pick in agent mode", file=sys.stderr)
        return 1

    strategy = None
    if pick is not None:
        try:
            strategy = parse_pick_spec(pick, batch=False)
        except PickSpecError as exc:
            print(f":) invalid --pick: {exc}", file=sys.stderr)
            return 1

    result = fetch_all(word)
    written: list[int] | None = None

    if strategy is not None and output is not None and result.entry is not None:
        indices = select_indices(result.entry, strategy)
        with _open_md(output, rewrite_header, opts) as f:
            written = write_senses(result, indices, f, opts)

    payload = result_to_json(result, written)
    print(json.dumps(payload, ensure_ascii=False))

    return 0 if payload["ok"] else 2
```

### Step 4.4: Wire `run_single` into `cli.main`

- [ ] Replace the agent-stub block in `dictpro/cli.py::main` with a dispatch to `run_single`. Change:

```python
    if args.query is not None or args.batch is not None:
        print(":) agent mode not yet wired (Task 4)", file=sys.stderr)
        return 1
```

to:

```python
    try:
        out_path = resolve_output_path(args.output)
    except FileNotFoundError as exc:
        print(f":) {exc}", file=sys.stderr)
        return 1
    opts = RenderOptions(include_audio=args.audio, include_synonyms=args.synonym)

    if args.query is not None:
        from .agent import run_single
        return run_single(
            args.query,
            pick=args.pick,
            output=out_path,
            rewrite_header=args.rewrite_header,
            opts=opts,
        )
    if args.batch is not None:
        print(":) batch mode not yet wired (Task 5)", file=sys.stderr)
        return 1
```

Then delete the duplicate `resolve_output_path` / `RenderOptions` block further down in `main()` (the interactive path), and restructure `main()` so the two branches share the early parsing. Full replacement of `main()`:

```python
def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        out_path = resolve_output_path(args.output)
    except FileNotFoundError as exc:
        print(f":) {exc}", file=sys.stderr)
        return 1
    opts = RenderOptions(include_audio=args.audio, include_synonyms=args.synonym)

    if args.query is not None:
        from .agent import run_single
        return run_single(
            args.query,
            pick=args.pick,
            output=out_path,
            rewrite_header=args.rewrite_header,
            opts=opts,
        )
    if args.batch is not None:
        print(":) batch mode not yet wired (Task 5)", file=sys.stderr)
        return 1

    # Interactive mode
    if out_path is None:
        name = _prompt(":) Please input the file name: ")
        out_path = Path(f"./{name}.md")
    with _open_output(out_path, args.rewrite_header, opts) as f:
        while True:
            inp = _prompt("word> ")
            if inp.strip() == "/q":
                break
            for word in (w.strip() for w in inp.split(",") if w.strip()):
                _lookup_and_write(word, f, opts)
    return 0
```

### Step 4.5: Run tests — expect pass

Run: `pytest tests/test_cli_agent.py -v && pytest -q`
Expected: all tests pass.

### Step 4.6: Commit

Run:
```bash
git add dictpro/agent.py dictpro/cli.py tests/test_cli_agent.py
git commit -m "feat: add -q agent single-query mode with JSON stdout

Returns 0 on success, 1 on usage error (e.g. -o without --pick), 2 when
the word was not found. JSON is flushed once per call with the schema
defined in docs/superpowers/specs/2026-04-22-agent-cli-mode-design.md."
```

---

## Task 5: Agent batch mode (`-b`) with NDJSON streaming + error handling

**Files:**
- Modify: `dictpro/agent.py` (add `run_batch`)
- Modify: `dictpro/cli.py` (dispatch to `run_batch`)
- Modify: `tests/test_cli_agent.py` (add batch tests)

### Step 5.1: Add failing batch tests

- [ ] Append to `tests/test_cli_agent.py`:

```python
def test_batch_from_file_json_only(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    mock_fetch["beta"] = _ok("beta")
    words_file = tmp_path / "words.txt"
    words_file.write_text("alpha\nbeta\n")
    rc = main(["-b", str(words_file)])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    a, b = (json.loads(line) for line in lines)
    assert a["word"] == "alpha" and a["ok"] is True
    assert b["word"] == "beta" and b["ok"] is True
    assert "written" not in a and "written" not in b


def test_batch_from_stdin_with_pick_writes_md(mock_fetch, tmp_path, capsys, monkeypatch):
    mock_fetch["serendipity"] = _ok("serendipity")
    mock_fetch["epiphany"] = _ok("epiphany")
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("serendipity\nepiphany\n"))
    out_file = tmp_path / "vocab.md"
    rc = main(["-b", "-", "--pick", "first", "-o", str(out_file)])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [json.loads(l)["word"] for l in lines] == ["serendipity", "epiphany"]
    assert all(json.loads(l)["written"] == [0] for l in lines)
    md = out_file.read_text()
    assert "|serendipity|" in md and "|epiphany|" in md


def test_batch_mixed_success_and_notfound(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    # "xyznope" not registered → _nf fallback in mock_fetch
    words_file = tmp_path / "w.txt"
    words_file.write_text("alpha\nxyznope\n")
    rc = main(["-b", str(words_file)])
    assert rc == 0  # at least one success
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["ok"] is True
    assert lines[1]["ok"] is False


def test_batch_all_fail_exit_2(mock_fetch, tmp_path, capsys):
    # No words registered — all fall through to _nf
    words_file = tmp_path / "w.txt"
    words_file.write_text("xyznope1\nxyznope2\n")
    rc = main(["-b", str(words_file)])
    assert rc == 2
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert all(l["ok"] is False for l in lines)


def test_batch_empty_lines_silently_skipped(mock_fetch, tmp_path, capsys):
    mock_fetch["alpha"] = _ok("alpha")
    words_file = tmp_path / "w.txt"
    words_file.write_text("\n\nalpha\n   \n")
    rc = main(["-b", str(words_file)])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["word"] == "alpha"


def test_batch_rejects_numeric_pick(mock_fetch, tmp_path, capsys):
    words_file = tmp_path / "w.txt"
    words_file.write_text("alpha\n")
    rc = main(["-b", str(words_file), "--pick", "0,2", "-o", str(tmp_path / "v.md")])
    assert rc == 1
    assert "numeric" in capsys.readouterr().err


def test_batch_output_without_pick_is_usage_error(mock_fetch, tmp_path, capsys):
    words_file = tmp_path / "w.txt"
    words_file.write_text("alpha\n")
    rc = main(["-b", str(words_file), "-o", str(tmp_path / "v.md")])
    assert rc == 1
    assert "--pick" in capsys.readouterr().err


def test_batch_no_words_is_exit_2(mock_fetch, tmp_path, capsys):
    words_file = tmp_path / "w.txt"
    words_file.write_text("\n\n   \n")
    rc = main(["-b", str(words_file)])
    # No rows produced at all; treat as 'all fail' for agent predictability
    assert rc == 2
    assert capsys.readouterr().out == ""
```

### Step 5.2: Run — expect failure

Run: `pytest tests/test_cli_agent.py -v`
Expected: 8 new FAILs (batch not wired).

### Step 5.3: Implement `run_batch` in `dictpro/agent.py`

- [ ] Append to `dictpro/agent.py`:

```python
from typing import Iterable, TextIO


def _iter_words(source: TextIO) -> Iterable[str]:
    """Yield cleaned word strings. Empty/whitespace-only lines are silently skipped.

    Lines containing ASCII control chars (besides whitespace) trigger a stderr
    warning and are skipped.
    """
    for raw in source:
        line = raw.rstrip("\n").rstrip("\r")
        stripped = line.strip()
        if not stripped:
            continue
        if any(ord(ch) < 0x20 for ch in stripped):
            print(f":) skipping line with control chars: {stripped!r}", file=sys.stderr)
            continue
        yield stripped


def run_batch(
    source_path: str,
    *,
    pick: str | None,
    output: Path | None,
    rewrite_header: bool,
    opts: RenderOptions,
) -> int:
    """Agent batch driver. Reads words from a file or '-' (stdin), streams NDJSON."""
    if output is not None and pick is None:
        print(":) -o/--output requires --pick in agent mode", file=sys.stderr)
        return 1

    strategy = None
    if pick is not None:
        try:
            strategy = parse_pick_spec(pick, batch=True)
        except PickSpecError as exc:
            print(f":) invalid --pick: {exc}", file=sys.stderr)
            return 1

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

    md_file = None
    if strategy is not None and output is not None:
        try:
            md_file = _open_md(output, rewrite_header, opts)
        except OSError as exc:
            print(f":) cannot open output: {exc}", file=sys.stderr)
            if close_source:
                source.close()
            return 1

    any_ok = False
    any_row = False
    try:
        for word in _iter_words(source):
            any_row = True
            result = fetch_all(word)
            written: list[int] | None = None
            if strategy is not None and md_file is not None and result.entry is not None:
                indices = select_indices(result.entry, strategy)
                try:
                    written = write_senses(result, indices, md_file, opts)
                except OSError as exc:
                    print(f":) write failed: {exc}", file=sys.stderr)
                    return 1
            payload = result_to_json(result, written)
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            if payload["ok"]:
                any_ok = True
    finally:
        if md_file is not None:
            md_file.close()
        if close_source:
            source.close()

    if not any_row:
        return 2  # no words processed = treat as all-fail
    return 0 if any_ok else 2
```

### Step 5.4: Wire `run_batch` into `cli.main`

- [ ] In `dictpro/cli.py::main`, replace the batch stub:

```python
    if args.batch is not None:
        print(":) batch mode not yet wired (Task 5)", file=sys.stderr)
        return 1
```

with:

```python
    if args.batch is not None:
        from .agent import run_batch
        return run_batch(
            args.batch,
            pick=args.pick,
            output=out_path,
            rewrite_header=args.rewrite_header,
            opts=opts,
        )
```

### Step 5.5: Run tests — expect pass

Run: `pytest tests/test_cli_agent.py -v && pytest -q`
Expected: all tests pass (originally 5 single tests + 8 new batch tests = 13 in `test_cli_agent.py`).

### Step 5.6: Commit

Run:
```bash
git add dictpro/agent.py dictpro/cli.py tests/test_cli_agent.py
git commit -m "feat: add -b batch mode with NDJSON streaming

Reads one word per line from file or '-' (stdin). Each result is
flushed immediately as an NDJSON line. Empty lines silently skipped;
control-char lines warned to stderr and skipped. Exit 2 when no word
succeeded (including empty input)."
```

---

## Task 6: End-to-end smoke + README update

**Files:**
- Modify: `README.md`
- Create: `tests/test_cli_agent_e2e.py`

### Step 6.1: Add an end-to-end smoke using fixtures

- [ ] Create `tests/test_cli_agent_e2e.py`:

```python
"""End-to-end smoke: feed HTML fixtures through the full stack
(parsers → concurrent → agent → cli) without hitting the network."""
from __future__ import annotations

import json

import pytest

from dictpro import concurrent as dc
from dictpro.cli import main
from dictpro.fetchers import NotFound


@pytest.fixture
def offline_fixtures(monkeypatch, fixtures_dir):
    """Route http_get to local fixture files so the whole stack runs offline."""
    def _fake_get(url: str, **_kw) -> str:
        if "cambridge" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "cambridge" / f"{word}.html"
        elif "wiktionary" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "wiktionary" / f"{word}.html"
        elif "freethesaurus" in url:
            word = url.rsplit("/", 1)[-1]
            path = fixtures_dir / "thesaurus" / f"{word}.html"
        else:
            raise NotFound(url)
        if not path.exists():
            raise NotFound(url)
        return path.read_text(encoding="utf-8")

    monkeypatch.setattr("dictpro.fetchers.http_get", _fake_get)
    # Agents-via-concurrent call these bound names:
    monkeypatch.setattr(dc, "http_get", _fake_get)


def test_e2e_query_swarm(offline_fixtures, capsys):
    rc = main(["-q", "swarm"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["word"] == "swarm"
    assert out["ok"] is True
    assert len(out["senses"]) > 0
    # Cambridge fixture has at least one noun sense
    assert any(s["pos"] == "noun" for s in out["senses"])


def test_e2e_batch_mixed(offline_fixtures, tmp_path, capsys):
    words = tmp_path / "w.txt"
    words.write_text("swarm\nnonexistent_xyz\n")
    rc = main(["-b", str(words)])
    assert rc == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines()]
    assert [l["word"] for l in lines] == ["swarm", "nonexistent_xyz"]
    assert lines[0]["ok"] is True
    assert lines[1]["ok"] is False
```

### Step 6.2: Run e2e test — expect pass

Run: `pytest tests/test_cli_agent_e2e.py -v`
Expected: both tests PASS.

### Step 6.3: Update README.md with agent mode section

- [ ] Open `README.md` and insert a new section after the existing "命令行参数" table (currently around line 77-87). Replace the whole "命令行参数" section with:

```markdown
## 命令行参数

| 参数 | 说明 |
|---|---|
| `-q, --query WORD` | **Agent 模式**：单次查询，输出 JSON 到 stdout |
| `-b, --batch FILE` | **Agent 模式**：批量查询，`FILE` 为路径或 `-`（stdin），每行一个词，NDJSON 输出 |
| `--pick SPEC` | 选哪些义项写入 md。`SPEC` 取值：`0` / `0,2,5`（仅 `-q`）/ `first` / `first-per-pos` / `all`。**缺省 = 不写 md** |
| `-o, --output PATH` | 输出 md 路径。无 `.md` 后缀则自动补；父目录必须存在 |
| `--no-audio` | 不要发音列 |
| `--no-synonym` | 不要同义词列 |
| `--rewrite-header` | 强制重写表头（默认追加时不重复写） |

没给 `-q` 也没给 `-b` 时，进入原交互模式（`word>` / `pick>` 提示符）。

## Agent 使用示例

```bash
# 单查，仅要 JSON
dictpro -q serendipity

# 单查 + 写 md + 同时拿 JSON（含 written 字段）
dictpro -q serendipity --pick 0,2 -o vocab

# 批量，每词取第一条义项，写入 md，流式 NDJSON
dictpro -b words.txt --pick first -o vocab

# 从 stdin 批量
cat words.txt | dictpro -b - --pick first-per-pos -o vocab
```

**Exit code**：`0` = 至少一个词成功；`1` = 用法/IO 错误；`2` = 全部词查不到（帮 agent 区分"网络断了 vs 词不存在"）。
```

Also delete the old `--name`/`--path`/`--head` rows and the "`--name` 和 `--path` 都不给时，启动后会交互式询问文件名。" line (now superseded by "没给 `-q` 也没给 `-b` 时，进入原交互模式").

Also update the existing "60 秒上手" example from `dictpro --name vocab` to `dictpro -o vocab`, and the "常用场景" section: replace `--name gatsby` with `-o gatsby`, `--name quick --no-audio` with `-o quick --no-audio`, `--name gatsby --head` with `-o gatsby --rewrite-header`.

### Step 6.4: Run full suite

Run: `pytest -q`
Expected: all tests pass.

### Step 6.5: Manual smoke

Run:
```bash
dictpro --help
dictpro -q serendipity  # hits live network, expect JSON
```
Expected: help shows `-q`, `-b`, `--pick`, `-o`, `--rewrite-header`; live call returns valid JSON with `ok: true` (or `ok: false` + `errors` if offline).

### Step 6.6: Commit

Run:
```bash
git add README.md tests/test_cli_agent_e2e.py
git commit -m "docs: document agent mode + add e2e smoke via offline fixtures

Replaces --name/--path/--head references with -o/--rewrite-header.
Adds agent mode section with call patterns and exit-code semantics.
E2E test pipes fixture HTML through the full stack to catch wiring
regressions without network."
```

---

## Self-review checklist (run after writing, fix inline)

- ✅ **Spec coverage**:
  - 3 new flags (`-q`/`-b`/`--pick`) → Tasks 3, 4, 5
  - `-o` unification → Task 3
  - `--rewrite-header` rename → Task 3
  - Delete `--name`/`--path`/`--head` → Task 3
  - JSON schema (ok, senses[].i, written, errors, omitted empty keys) → Task 1
  - NDJSON streaming + flush → Task 5
  - Exit codes 0/1/2 → Tasks 4, 5
  - Pick strategies (first, first-per-pos, all, numeric) → Task 2
  - Batch rejects numeric → Task 2, verified Task 5
  - Empty lines silent skip + control-char warning → Task 5
  - Interactive mode preserved → Task 3, 4
  - Agent mode never hangs on stdin (no `_prompt` reachable) → Task 4's `main()` restructure

- ✅ **No placeholders**: every test has real code; every edit shows before→after.
- ✅ **Type consistency**: `PickStrategy`, `PickSpecError`, `parse_pick_spec`, `select_indices`, `result_to_json`, `write_senses`, `run_single`, `run_batch`, `resolve_output_path` — all names match across tasks.
- ✅ **Frequent commits**: one commit per task (6 total).
