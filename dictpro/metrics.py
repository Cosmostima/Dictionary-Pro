"""Quantitative evaluation of Dictionary Pro.

Four metrics:

1. **Parser accuracy** — each golden field check.
2. **End-to-end word-list success rate** — renders a row for each word.
3. **Average latency** — wall-clock fetch_all latency over the wordlist.
4. **Test coverage** — read from coverage.json if present.

Run:
    python -m dictpro.metrics                         # offline only
    python -m dictpro.metrics --online                # live e2e + latency
    python -m dictpro.metrics --online --cov-json coverage.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .concurrent import fetch_all
from .models import Extras, WordEntry
from .parsers import parse_cambridge, parse_thesaurus, parse_wiktionary
from .renderer import RenderOptions, render_row

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"
WORDLIST = ROOT / "tests" / "wordlist.txt"


@dataclass
class CheckResult:
    total: int = 0
    passed: int = 0
    failures: list[str] = field(default_factory=list)

    def check(self, cond: bool, label: str) -> None:
        self.total += 1
        if cond:
            self.passed += 1
        else:
            self.failures.append(label)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


# ---------------------------------------------------------------------------
# Parser accuracy
# ---------------------------------------------------------------------------

def _eval_cambridge(word: str, gold: dict) -> CheckResult:
    r = CheckResult()
    html = (FIXTURES / "cambridge" / f"{word}.html").read_text(encoding="utf-8")
    entry = parse_cambridge(html, word)

    r.check(len(entry.senses) == gold["total_senses"],
            f"{word}/cambridge total_senses={len(entry.senses)} expected={gold['total_senses']}")

    if gold.get("total_senses", 0) > 0:
        pos_counts: dict[str, int] = {}
        for s in entry.senses:
            pos_counts[s.pos] = pos_counts.get(s.pos, 0) + 1
        r.check(pos_counts == gold["pos_counts"],
                f"{word}/cambridge pos_counts={pos_counts} expected={gold['pos_counts']}")

        first: dict[str, str] = {}
        for s in entry.senses:
            first.setdefault(s.pos, s.text)
        for pos, sub in gold["first_def_contains"].items():
            r.check(pos in first and sub.lower() in first[pos].lower(),
                    f"{word}/cambridge first_def[{pos}] missing {sub!r}")
        for pos, ipa in gold.get("us_ipa", {}).items():
            flat = [p for grp in entry.pronunciations.get(pos, []) for p in grp]
            r.check(any(p.region == "US" and p.ipa == ipa for p in flat),
                    f"{word}/cambridge us_ipa[{pos}]={ipa}")
        for pos, ipa in gold.get("uk_ipa", {}).items():
            flat = [p for grp in entry.pronunciations.get(pos, []) for p in grp]
            r.check(any(p.region == "UK" and p.ipa == ipa for p in flat),
                    f"{word}/cambridge uk_ipa[{pos}]={ipa}")
    return r


def _eval_wiktionary(word: str, gold: dict) -> CheckResult:
    r = CheckResult()
    html = (FIXTURES / "wiktionary" / f"{word}.html").read_text(encoding="utf-8")
    infl = parse_wiktionary(html)

    if gold.get("empty"):
        r.check(infl == {}, f"{word}/wiktionary expected empty got {list(infl)}")
        return r

    counts = {k: len(v) for k, v in infl.items()}
    r.check(counts == gold["pos_counts"],
            f"{word}/wiktionary pos_counts={counts} expected={gold['pos_counts']}")
    for pos, expected_words in gold["contains"].items():
        texts = [i.text for i in infl.get(pos, [])]
        for w in expected_words:
            r.check(w in texts, f"{word}/wiktionary {pos}:{w} missing")
    return r


def _eval_thesaurus(word: str, gold: dict) -> CheckResult:
    r = CheckResult()
    html = (FIXTURES / "thesaurus" / f"{word}.html").read_text(encoding="utf-8")
    syn = parse_thesaurus(html)

    pos_present = gold.get("pos_present", [])
    if not pos_present:
        r.check(syn == {}, f"{word}/thesaurus expected empty got {list(syn)}")
    else:
        for pos in pos_present:
            r.check(pos in syn, f"{word}/thesaurus pos {pos} missing")
    for pos, expected_words in gold.get("contains", {}).items():
        for w in expected_words:
            r.check(w in syn.get(pos, []), f"{word}/thesaurus {pos}:{w} missing")
    return r


def parser_accuracy() -> dict:
    per_site = {"cambridge": CheckResult(), "wiktionary": CheckResult(), "thesaurus": CheckResult()}
    for path in sorted(GOLDEN.glob("*.json")):
        gold = json.loads(path.read_text(encoding="utf-8"))
        word = gold["word"]
        for site, evaluator in (
            ("cambridge", _eval_cambridge),
            ("wiktionary", _eval_wiktionary),
            ("thesaurus", _eval_thesaurus),
        ):
            if site in gold:
                sub = evaluator(word, gold[site])
                per_site[site].total += sub.total
                per_site[site].passed += sub.passed
                per_site[site].failures.extend(sub.failures)
    return per_site


# ---------------------------------------------------------------------------
# End-to-end word list
# ---------------------------------------------------------------------------


def _load_from_fixture(word: str) -> tuple[WordEntry, Extras] | None:
    cam = FIXTURES / "cambridge" / f"{word}.html"
    wik = FIXTURES / "wiktionary" / f"{word}.html"
    syn = FIXTURES / "thesaurus" / f"{word}.html"
    if not cam.exists():
        return None
    entry = parse_cambridge(cam.read_text(encoding="utf-8"), word)
    infl = parse_wiktionary(wik.read_text(encoding="utf-8")) if wik.exists() and wik.stat().st_size > 0 else {}
    syn_map = parse_thesaurus(syn.read_text(encoding="utf-8")) if syn.exists() else {}
    return entry, Extras(inflections=infl, synonyms=syn_map)


@dataclass
class E2EOutcome:
    word: str
    passed: bool
    reason: str = ""


def e2e_success(words: list[str], *, online: bool) -> list[E2EOutcome]:
    outcomes: list[E2EOutcome] = []
    opts = RenderOptions(include_audio=True, include_synonyms=True)
    expected_cols = 7

    for word in words:
        entry: WordEntry | None = None
        extras: Extras = Extras()
        loaded = _load_from_fixture(word)
        if loaded is not None:
            entry, extras = loaded
        elif online:
            result = fetch_all(word)
            entry = result.entry
            extras = result.extras
            time.sleep(0.3)
        else:
            outcomes.append(E2EOutcome(word, False, "no fixture, online disabled"))
            continue

        if entry is None or not entry.senses:
            outcomes.append(E2EOutcome(word, False, "no senses"))
            continue
        row = render_row(entry, extras, 0, opts)
        cols = row.rstrip("\n").count("|") - 1
        if cols != expected_cols:
            outcomes.append(E2EOutcome(word, False, f"bad col count {cols}"))
            continue
        outcomes.append(E2EOutcome(word, True))
    return outcomes


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Latency
# ---------------------------------------------------------------------------


@dataclass
class LatencySample:
    word: str
    seconds: float
    ok: bool


def measure_latency(words: list[str], *, pace: float = 0.0) -> list[LatencySample]:
    """Time fetch_all on each word (live network). Small inter-request pacing
    is applied to stay polite; measurements exclude sleep time."""
    samples: list[LatencySample] = []
    for word in words:
        t0 = time.perf_counter()
        result = fetch_all(word)
        elapsed = time.perf_counter() - t0
        ok = result.entry is not None and bool(result.entry.senses)
        samples.append(LatencySample(word=word, seconds=elapsed, ok=ok))
        if pace:
            time.sleep(pace)
    return samples


# ---------------------------------------------------------------------------
# Coverage (read external JSON)
# ---------------------------------------------------------------------------


def read_coverage(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    files = data.get("files", {})
    per_file = []
    total_stmts = total_miss = 0
    for fname, info in files.items():
        s = info["summary"]
        per_file.append((fname, s["num_statements"], s["missing_lines"], s["percent_covered"]))
        total_stmts += s["num_statements"]
        total_miss += s["missing_lines"]
    total_pct = (100.0 * (total_stmts - total_miss) / total_stmts) if total_stmts else 0.0
    return {
        "per_file": sorted(per_file),
        "total_stmts": total_stmts,
        "total_miss": total_miss,
        "total_pct": total_pct,
    }


def format_report(
    per_site: dict,
    e2e: list[E2EOutcome],
    latency: list[LatencySample] | None,
    coverage: dict | None,
    *,
    online_used: bool,
) -> str:
    lines: list[str] = []
    lines.append("# Dictionary Pro — Test & Metrics Report")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    lines.append("")

    total_passed = sum(r.passed for r in per_site.values())
    total_total = sum(r.total for r in per_site.values())
    overall = (total_passed / total_total) if total_total else 0.0

    lines.append("## 1. Parser Accuracy (offline fixtures vs golden)")
    lines.append("")
    lines.append("| Site | Passed | Total | Accuracy |")
    lines.append("| --- | --- | --- | --- |")
    for site, r in per_site.items():
        lines.append(f"| {site} | {r.passed} | {r.total} | {r.rate:.1%} |")
    lines.append(f"| **overall** | **{total_passed}** | **{total_total}** | **{overall:.1%}** |")
    lines.append("")
    all_fail = [f for r in per_site.values() for f in r.failures]
    if all_fail:
        lines.append("### Failures")
        for f in all_fail:
            lines.append(f"- {f}")
        lines.append("")

    passed_e2e = sum(1 for o in e2e if o.passed)
    rate_e2e = passed_e2e / len(e2e) if e2e else 0.0
    mode = "online" if online_used else "offline fixtures"
    lines.append(f"## 2. End-to-End Word-List Success ({mode})")
    lines.append("")
    lines.append(f"- words attempted: {len(e2e)}")
    lines.append(f"- passed: {passed_e2e}")
    lines.append(f"- success rate: **{rate_e2e:.1%}**")
    lines.append("")
    fails = [o for o in e2e if not o.passed]
    if fails:
        lines.append("### Failing words")
        for o in fails:
            lines.append(f"- `{o.word}` — {o.reason}")
        lines.append("")

    # Latency
    lat_mean = lat_median = lat_p95 = lat_max = lat_min = 0.0
    if latency:
        secs = [s.seconds for s in latency]
        lat_mean = statistics.mean(secs)
        lat_median = statistics.median(secs)
        lat_max = max(secs)
        lat_min = min(secs)
        k = max(0, int(round(0.95 * (len(secs) - 1))))
        lat_p95 = sorted(secs)[k]
        ok_ratio = sum(1 for s in latency if s.ok) / len(latency)
        lines.append(f"## 3. End-to-End Latency (n={len(latency)}, online)")
        lines.append("")
        lines.append("| Stat | Seconds |")
        lines.append("| --- | --- |")
        lines.append(f"| mean   | {lat_mean:.3f} |")
        lines.append(f"| median | {lat_median:.3f} |")
        lines.append(f"| p95    | {lat_p95:.3f} |")
        lines.append(f"| min    | {lat_min:.3f} |")
        lines.append(f"| max    | {lat_max:.3f} |")
        lines.append("")
        lines.append(f"Per-word (word : seconds : ok):")
        lines.append("")
        lines.append("```")
        for s in latency:
            flag = "ok " if s.ok else "FAIL"
            lines.append(f"{s.word:<16} {s.seconds:6.3f}  {flag}")
        lines.append("```")
        lines.append(f"(entry-found ratio: {ok_ratio:.1%})")
        lines.append("")

    # Coverage
    cov_total = 0.0
    if coverage:
        cov_total = coverage["total_pct"]
        lines.append("## 4. Test Coverage (core library; cli/metrics excluded)")
        lines.append("")
        lines.append("| Module | Stmts | Miss | Cover |")
        lines.append("| --- | --- | --- | --- |")
        for fname, stmts, miss, pct in coverage["per_file"]:
            lines.append(f"| {fname} | {stmts} | {miss} | {pct:.1f}% |")
        lines.append(
            f"| **TOTAL** | **{coverage['total_stmts']}** | "
            f"**{coverage['total_miss']}** | **{cov_total:.1f}%** |"
        )
        lines.append("")

    lines.append("## 5. Success Criteria")
    lines.append("")
    lines.append(f"- Parser accuracy ≥ 95% → "
                 f"{'PASS' if overall >= 0.95 else 'FAIL'} ({overall:.1%})")
    lines.append(f"- End-to-end ≥ 95% → "
                 f"{'PASS' if rate_e2e >= 0.95 else 'FAIL'} ({rate_e2e:.1%})")
    if latency:
        lines.append(f"- Mean latency ≤ 3.0 s → "
                     f"{'PASS' if lat_mean <= 3.0 else 'FAIL'} ({lat_mean:.3f}s)")
    if coverage:
        lines.append(f"- Core coverage ≥ 85% → "
                     f"{'PASS' if cov_total >= 85.0 else 'FAIL'} ({cov_total:.1f}%)")
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--online", action="store_true",
                   help="For e2e words not in fixtures, hit live sites. Also enables latency.")
    p.add_argument("--out", default=str(ROOT / "TEST_RESULTS.md"),
                   help="Output markdown path.")
    p.add_argument("--cov-json", default=str(ROOT / "coverage.json"),
                   help="Path to coverage.json (produced by pytest --cov-report=json).")
    p.add_argument("--skip-latency", action="store_true",
                   help="Skip latency measurement even when --online is set.")
    p.add_argument("--pace", type=float, default=0.25,
                   help="Seconds to sleep between latency requests (excluded from timing).")
    args = p.parse_args(argv)

    per_site = parser_accuracy()
    words = [w.strip() for w in WORDLIST.read_text().splitlines() if w.strip()]
    seen = set()
    words = [w for w in words if not (w in seen or seen.add(w))]
    e2e = e2e_success(words, online=args.online)

    latency = None
    if args.online and not args.skip_latency:
        latency = measure_latency(words, pace=args.pace)

    coverage = read_coverage(Path(args.cov_json))

    report = format_report(per_site, e2e, latency, coverage, online_used=args.online)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
