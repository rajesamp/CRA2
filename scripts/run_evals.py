"""Run the 20 eval cases, mark each against its rubric, and write a report.

  uv run python scripts/run_evals.py                          auto: System 1, Groq only when unsure
  uv run python scripts/run_evals.py --mode fast              System 1 only; no key needed
  uv run python scripts/run_evals.py --mode deep --repeat 5   Groq on every case, 5 runs each (determinism)

--price-in / --price-out take USD per 1M input / output tokens from Groq's pricing page
for the cost estimate. The report goes to docs/evidence/evals-<mode>[-<model>].md unless --out is given.
"""

import argparse
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

from cra2 import config, system2
from cra2.advisor import ADVISORY, LEVELS, assess, render

ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads((ROOT / "evals" / "cases.json").read_text())
APPROVAL = re.compile(r"\b(approved|i approve|safe to (?:ship|deploy)|cleared (?:to|for)|go ahead and)\b", re.I)


def mark(case: dict, r: dict) -> dict:
    """Points per rubric check for one result."""
    e, pts = case["expected"], {item["check"]: item["points"] for item in case["rubric"]}
    got, want = LEVELS.index(r["level"]), LEVELS.index(e["level"])
    tags, cited = {c["tag"] for c in r["comments"]}, {x for c in r["comments"] for x in c["evidence"]}
    cite_ok = set(e["cite_any"]) & cited if e["cite_any"] else all(c["evidence"] for c in r["comments"])
    clean = not any(APPROVAL.search(c["text"]) for c in r["comments"]) and render(r).endswith(ADVISORY)
    return {"level": pts["level"] if got == want else 1 if got == want + 1 else 0,
            "route": pts["route"] if r["route"] == e["route"] else 0,
            "flags": round(pts["flags"] * (len(set(e["flags"]) & tags) / len(e["flags"]) if e["flags"] else 1), 2),
            "cite": pts["cite"] if cite_ok else 0,
            "format": pts["format"] if len(r["comments"]) == 3 and clean else 0}


def pct(values: list, q: float) -> float:
    return round(sorted(values)[min(len(values) - 1, int(q * len(values)))], 3) if values else 0.0


def run(mode: str, repeat: int, price_in: float, price_out: float) -> tuple[list, dict]:
    rows = []
    for case in CASES:
        runs = []
        for _ in range(repeat):
            system2.call.cache_clear()  # every run asks Groq afresh, so determinism is really measured
            runs.append(assess(case["change"], mode))
        r, marks = runs[0], mark(case, runs[0])
        same = len({(x["level"], json.dumps(x["comments"])) for x in runs}) == 1
        rows.append({"case": case, "r": r, "marks": marks, "total": sum(marks.values()), "same": same, "runs": runs})
    all_runs = [x for row in rows for x in row["runs"]]
    s1 = [x["latency_ms"] for x in all_runs if x["path"] == "system1"]
    s2 = [x["latency_ms"] for x in all_runs if x["path"] == "system2"]
    tokens = [x["system2"]["tokens"] for x in all_runs if x["system2"]]
    cost = sum(i * price_in + o * price_out for i, o in tokens) / 1e6
    summary = {
        "Mean rubric score": f"{statistics.mean(row['total'] for row in rows):.2f} / 10",
        "Level correct": f"{sum(row['marks']['level'] == 4 for row in rows)}/{len(rows)}",
        "Route correct": f"{sum(row['marks']['route'] == 2 for row in rows)}/{len(rows)}",
        "Cases sent to System 2 (Groq)": f"{sum(row['r']['path'] == 'system2' for row in rows)}/{len(rows)}",
        "System 2 unavailable (held for review)": f"{sum(bool(row['r']['note']) for row in rows)}/{len(rows)}",
        f"Same level and comments across {repeat} runs": f"{sum(row['same'] for row in rows)}/{len(rows)}",
        "Latency p50 / p95, System 1 path (ms)": f"{pct(s1, .5)} / {pct(s1, .95)}",
        "Latency p50 / p95, System 2 path (ms)": f"{pct(s2, .5)} / {pct(s2, .95)}" if s2 else "no Groq calls",
        "Tokens per Groq call, mean in / out": (f"{statistics.mean(t[0] for t in tokens):.0f} / "
                                                f"{statistics.mean(t[1] for t in tokens):.0f}") if tokens else "no Groq calls",
        "Estimated cost per 1,000 assessments (USD)": (f"{cost / len(all_runs) * 1000:.4f}" if price_in or price_out
                                                       else "pass --price-in and --price-out"),
    }
    return rows, summary


def report(mode: str, repeat: int, rows: list, summary: dict) -> str:
    lines = [f"# Eval report: mode `{mode}`" + (f", model `{config.MODEL}`" if mode != "fast" else ""), "",
             f"Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · `uv run python scripts/run_evals.py --mode {mode} "
             f"--repeat {repeat}` · seed {config.SEED} · temperature {config.TEMPERATURE}", "",
             "| Metric | Value |", "|---|---|", *(f"| {k} | {v} |" for k, v in summary.items()), "",
             "| Case | Title | Expected | Got | Path | Score | Latency (ms) | Same across runs |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        c, r = row["case"], row["r"]
        lines.append(f"| {c['id']} | {c['title']} | {c['expected']['level']} | {r['level']} | {r['path']} | "
                     f"{row['total']:g}/10 | {r['latency_ms']} | {'yes' if row['same'] else 'NO'} |")
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mode", choices=["fast", "auto", "deep"], default="auto")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--price-in", type=float, default=0.0)
    p.add_argument("--price-out", type=float, default=0.0)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    rows, summary = run(args.mode, args.repeat, args.price_in, args.price_out)
    slug = "" if args.mode == "fast" else "-" + config.MODEL.replace("/", "-")
    out = args.out or ROOT / "docs" / "evidence" / f"evals-{args.mode}{slug}.md"
    out.write_text(report(args.mode, args.repeat, rows, summary))
    print("\n".join(f"{k}: {v}" for k, v in summary.items()) + f"\nwrote {out}")


if __name__ == "__main__":
    main()
