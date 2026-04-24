# Dictionary Pro

**English** | [简体中文](README_zh.md)

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Version](https://img.shields.io/badge/version-0.2.0-green) ![Agent Ready](https://img.shields.io/badge/agent--ready-skill-purple)

A command-line dictionary that turns the senses you pick into a Markdown vocabulary notebook.

Built for close reading — foreign-language articles, papers, original-language books — when you want to collect words as you go. Look a word up once, pick the senses you care about, and the result is appended straight to a `.md` file. Open it in Obsidian / Typora and you have a tidy vocabulary table.

> Ships with a skill so agents like Claude Code can call it directly. See [Deploying the skill](#deploying-the-skill).

## Why use it

- **Three sources in one shot**: Cambridge (definitions + pronunciation), Wiktionary (inflections / plurals), and FreeThesaurus (synonyms) fetched concurrently — about as fast as hitting one source alone.
- **Only what you want**: senses are grouped by part of speech and listed with indices you pick by hand, so the notebook never fills up with whole dictionary pages.
- **Ready to read**: Markdown tables with clickable IPA-as-audio links and a jump to the Cambridge source page.

## Preview

Terminal interaction:

```
word> serendipity
--------------------
serendipity
noun: 0 the fact of finding interesting or valuable things by chance
pick> 0
word> /q
```

The resulting `vocab.md`:

| Word | Pos | Def | Syn | Verbs | Pron | Web |
|---|---|---|---|---|---|---|
| serendipity | noun | the fact of finding interesting or valuable things by chance | chance; fortune | serendipities | US: [/ˌser.ənˈdɪp.ə.t̬i/](...) | [^_^](https://...) |

## Install

Requires Python 3.10+.

```bash
git clone <repo-url>
cd dictionary_pro
pip install -e .
```

Verify:

```bash
dictpro --help
# or: python main.py --help
```

## 60-second tour

```bash
dictpro -o vocab
```

Then:

1. Type a word at the `word>` prompt and hit enter.
2. When the sense list appears, type the index of the sense(s) you want at the `pick>` prompt (e.g. `0`).
3. Back at `word>`, type the next word, or `/q` to quit.
4. Open `./vocab.md` to see the result.

## Interactive cheatsheet

Two prompts:

- `word> ` — enter a word to look up
- `pick> ` — enter the sense index(es) to save

| Prompt | Input | Meaning |
|---|---|---|
| `word> ` | `word` | Look up one word |
| `word> ` | `w1,w2,w3` | Look up several at once (comma-separated) |
| `word> ` | `/q` | Quit |
| `pick> ` | `0` / `0,2,5` | Save the N-th sense; multi-select with commas |
| `pick> ` | `/x` | Skip the current word, save nothing |

## Command-line options

| Option | What it does |
|---|---|
| `-o, --output PATH` | Output md path. `.md` is auto-appended if missing; the parent directory must already exist. |
| `--no-audio` | Drop the pronunciation column. |
| `--no-synonym` | Drop the synonym column. |
| `--rewrite-header` | Force-write the header row (by default it's written only once when appending to an existing file). |

If you omit `-o`, dictpro asks for a filename interactively at startup.

Want to call it from an agent or script? See [Deploying the skill](#deploying-the-skill) below.

## Output layout

Header fields:

- **Word** — the word
- **Pos** — part of speech
- **Def** — the selected sense
- **Syn** — synonyms for the same part of speech
- **Verbs** — inflections (past tense, plurals, etc.)
- **Pron** — US / UK pronunciations; the IPA text itself is the audio link
- **Web** — jump to the Cambridge source page

You can run `dictpro` against the same file any number of times; the header is written only once.

## Common recipes

```bash
# Build a vocab list for a book
dictpro -o gatsby

# Keep definitions and synonyms, drop pronunciations
dictpro -o quick --no-audio

# Continue appending to an old file, but rewrite the header
dictpro -o gatsby --rewrite-header
```

## Deploying the skill

The project bundles a skill so agents know how to call dictpro.

### Claude Code

```bash
# Link the skill into Claude Code's skills directory
ln -s "$(pwd)/skills/use-dictpro" ~/.claude/skills/use-dictpro
```

After that, any Claude Code session will auto-discover it and use `dictpro -q` / `-b` without you having to explain the interface.

### What the skill covers

Two flags:

| Flag | What it does |
|---|---|
| `-q WORD` | Look up one word; writes a JSON object to stdout. |
| `-b FILE` | Batch lookup. `FILE` is a path or `-` (stdin), one word per line, streamed out as NDJSON. |

Typical invocations:

```bash
# Single word
dictpro -q serendipity

# Batch from a file
dictpro -b words.txt

# Batch from stdin
cat words.txt | dictpro -b -
```

JSON on stdout (for `-q serendipity`):

```json
{
  "word": "serendipity",
  "ok": true,
  "senses": [{"i": 0, "pos": "noun", "text": "the fact of finding ..."}],
  "inflections": {"noun": ["serendipities"]},
  "synonyms": {"noun": ["chance", "fortune"]},
  "pronunciations": {"noun": [[{"region": "US", "ipa": "/...", "audio": "..."}]]}
}
```

The `errors` field appears only when a source fails; `inflections`, `synonyms`, and `pronunciations` are omitted when empty.

Exit codes come in three flavors:

- `0` — at least one word was found
- `1` — IO error
- `2` — no word was found at all (lets the agent tell "word doesn't exist" apart from "network is down")

Batch output is NDJSON and **each line is flushed as soon as its word is ready**, so it can be consumed as a stream. stdout is always machine-readable (JSON / NDJSON); human-readable diagnostics go to stderr.

## Troubleshooting

**`Word not found`**
None of the three sources had it. Check the spelling, or the word may be a proper noun / internet slang.

**Network timeout**
Retries are built in; transient failures usually clear up on the next try. If failures persist, check your proxy.

**Too many senses to pick from**
Indices are globally continuous and span parts of speech, so you can mix them: to save both `noun: 0` and `verb: 3`, type `0,3`.

## Project layout

```
dictpro/
  cli.py          # interactive entry / argument dispatch
  agent.py        # JSON output for -q / -b
  fetchers.py     # HTTP layer with retries
  concurrent.py   # concurrent fan-out across the three sources
  parsers/        # cambridge / wiktionary / thesaurus parsers
  renderer.py     # Markdown table rendering
  models.py       # data structures
```

Adding a data source: drop a new parser into `parsers/` and register it in `concurrent.py`.
