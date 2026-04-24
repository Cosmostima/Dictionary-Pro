---
name: use-dictpro
description: Use when an agent needs to look up English word definitions, inflections, or synonyms, or needs to build a Markdown vocabulary file programmatically. Covers the non-interactive agent API (-q / -b flags).
---

# Using dictpro

dictpro queries Cambridge, Wiktionary, and FreeThesaurus concurrently and returns structured data. It has two modes: interactive (human REPL) and agent (flags-based). Always use the agent mode.

## Entry points

```bash
dictpro -q WORD        # single word → one JSON object to stdout
dictpro -b FILE        # batch; FILE is a path or - for stdin, one word per line → NDJSON
```

**Never run `dictpro` without `-q` or `-b`.** Without them it starts an interactive REPL and blocks on stdin.

## JSON output

```json
{
  "word": "serendipity",
  "ok": true,
  "senses": [
    {"i": 0, "pos": "noun", "text": "the fact of finding interesting things by chance"}
  ],
  "inflections": {"noun": ["serendipities"]},
  "synonyms":    {"noun": ["chance", "fortune"]},
  "pronunciations": {"noun": [[{"region": "US", "ipa": "/ˌser.ənˈdɪp.ə.t̬i/", "audio": "https://..."}]]},
  "errors":  {"wiktionary": "timeout"}
}
```

Key fields:

- **`ok`** — `true` if Cambridge returned at least one sense. Check before reading `senses`.
- **`senses[].i`** — sense index (stable within one invocation), useful for display or agent reasoning.
- **`errors`** — present only when a source failed; omitted on clean runs.
- **`inflections`**, **`synonyms`**, **`pronunciations`** — omitted when empty.

Batch mode flushes one JSON line per word immediately — safe to consume as a stream.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | At least one word found |
| 1 | Usage error or IO error |
| 2 | All words failed — nothing in the dictionary, or network down |

Exit 2 is not a crash. Distinguish "word doesn't exist" vs "network down" by checking `errors` in the output.

## Typical flows

```bash
# Single lookup — inspect full JSON
dictpro -q serendipity

# Batch — stream NDJSON, one line per word
dictpro -b words.txt

# Batch from stdin
cat words.txt | dictpro -b -
```

dictpro is a pure query tool in agent mode. It returns all available data as JSON; writing to a Markdown vocab file is handled by the interactive mode (human-facing).
