from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from .concurrent import LookupResult, fetch_all
from .models import WordEntry
from .renderer import RenderOptions, header, render_row


def _print_senses(entry: WordEntry) -> None:
    """Display senses with global indices grouped by pos."""
    current_pos: str | None = None
    pad = 0
    for idx, sense in enumerate(entry.senses):
        if sense.pos != current_pos:
            current_pos = sense.pos
            pad = len(sense.pos) + 2
            print(f"{sense.pos}: {idx} {sense.text}")
        else:
            print(f"{' ' * pad}{idx} {sense.text}")


def _parse_indices(s: str, max_idx: int) -> list[int]:
    out: list[int] = []
    for piece in s.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            n = int(piece)
        except ValueError:
            print(f":) Invalid index: {piece!r}")
            continue
        if not 0 <= n < max_idx:
            print(f":) Out of range: {n} (valid 0-{max_idx - 1})")
            continue
        out.append(n)
    return out


def _prompt(msg: str) -> str:
    try:
        return input(msg)
    except EOFError:
        return "/q"


def _open_output(path: Path, write_header: bool, opts: RenderOptions):
    exists = path.exists()
    f = path.open("a", encoding="utf-8")
    if not exists or write_header:
        f.write(header(opts))
    return f


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
    for n in indices:
        out_file.write(render_row(result.entry, result.extras, n, opts))
    if indices:
        out_file.flush()
    return True


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
        return run_single(args.query)
    if args.batch is not None:
        from .agent import run_batch
        return run_batch(args.batch)

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


if __name__ == "__main__":
    sys.exit(main())
