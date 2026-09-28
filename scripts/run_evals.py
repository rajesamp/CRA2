"""Score every evaluation repeat, write evidence, and fail when the quality gate fails.

Fast mode stays offline. Auto/deep modes can send change context to Groq.
Supply both token prices (USD per million) to estimate observed token cost.
"""

import argparse
import hashlib
import json
import math
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

from cra2 import config, system2
from cra2.advisor import ADVISORY, INCIDENTS, LEVELS, assess, context, render

ROOT = Path(__file__).resolve().parent.parent
CASES = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))
APPROVAL = re.compile(
    r"\b(approved|i approve|safe to (?:ship|deploy)|cleared (?:to|for)|go ahead and)\b",
    re.I,
)


def mark(case: dict, result: dict) -> dict:
    """Award rubric points, checking citation membership as well as presence."""
    expected = case["expected"]
    points = {item["check"]: item["points"] for item in case["rubric"]}
    got, want = LEVELS.index(result["level"]), LEVELS.index(expected["level"])
    comments = result["comments"]
    tags = {comment["tag"] for comment in comments}
    cited = {key for comment in comments for key in comment["evidence"]}
    allowed = set(context(case["change"])["evidence"])
    grounded = (
        bool(comments)
        and all(comment["evidence"] for comment in comments)
        and cited <= allowed
    )
    cite_ok = grounded and (
        not expected["cite_any"] or bool(set(expected["cite_any"]) & cited)
    )
    clean = not any(
        APPROVAL.search(comment["text"]) for comment in comments
    ) and render(result).endswith(ADVISORY)
    flags = set(expected["flags"])
    return {
        "level": points["level"] if got == want else 1 if got == want + 1 else 0,
        "route": points["route"] if result["route"] == expected["route"] else 0,
        "flags": round(
            points["flags"] * (len(flags & tags) / len(flags) if flags else 1), 2
        ),
        "cite": points["cite"] if cite_ok else 0,
        "format": points["format"] if len(comments) == len(tags) == 3 and clean else 0,
    }


def pct(values: list, quantile: float) -> float | None:
    """Nearest-rank percentile; absent samples have no measured percentile."""
    if not values:
        return None
    return round(sorted(values)[max(0, math.ceil(quantile * len(values)) - 1)], 3)


def _latency(values: list) -> str:
    return (
        f"{pct(values, 0.5)} / {pct(values, 0.95)} (n={len(values)})"
        if values
        else "not measured (n=0)"
    )


def _validate_options(
    mode: str, repeat: int, price_in: float | None, price_out: float | None
) -> None:
    if mode not in {"fast", "auto", "deep"}:
        raise ValueError("mode must be fast, auto, or deep")
    if isinstance(repeat, bool) or not isinstance(repeat, int) or repeat < 1:
        raise ValueError("repeat must be a positive integer")
    if (price_in is None) != (price_out is None):
        raise ValueError("provide both --price-in and --price-out, or neither")
    if any(
        price is not None and (not math.isfinite(price) or price < 0)
        for price in (price_in, price_out)
    ):
        raise ValueError("token prices must be finite, non-negative numbers")


def _tokens(result: dict) -> list | None:
    """Usage from this request, including any rejected provider response."""
    usage = result.get("system2_failure_usage") or result.get("system2") or {}
    return usage.get("tokens")


def run(
    mode: str,
    repeat: int,
    price_in: float | None = None,
    price_out: float | None = None,
) -> tuple[list, dict]:
    _validate_options(mode, repeat, price_in, price_out)
    if not CASES:
        raise ValueError("evaluation dataset is empty")
    started = datetime.now(timezone.utc)
    rows = []
    for case in CASES:
        runs = []
        for _ in range(repeat):
            # Observe fresh responses for repeatability, not reuse of a cached answer.
            if mode != "fast":
                system2.call.cache_clear()
            runs.append(assess(case["change"], mode))
        marks = [mark(case, result) for result in runs]
        totals = [sum(item.values()) for item in marks]
        signatures = {
            (
                result["level"],
                result["route"],
                json.dumps(result["comments"], sort_keys=True),
            )
            for result in runs
        }
        rows.append(
            {
                "case": case,
                "runs": runs,
                "marks": marks,
                "totals": totals,
                "same": len(signatures) == 1 if repeat > 1 else None,
            }
        )
    ended = datetime.now(timezone.utc)
    all_runs = [result for row in rows for result in row["runs"]]
    all_marks = [item for row in rows for item in row["marks"]]
    totals = [total for row in rows for total in row["totals"]]
    requested = [result for result in all_runs if result["system2_attempted"]]
    attempts = [result for result in all_runs if result["system2_request_attempted"]]
    cached = [result for result in all_runs if result["system2_cache_hit"]]
    failed = [result for result in requested if result["system2"] is None]
    known_tokens = [
        _tokens(result) for result in attempts if _tokens(result) is not None
    ]
    missing_usage = len(attempts) - len(known_tokens)
    cost = (
        None
        if price_in is None
        else sum(i * price_in + o * price_out for i, o in known_tokens) / 1e6
    )
    if not attempts:
        subtotal = estimate = "not applicable: no provider request attempts"
    elif cost is None:
        subtotal = estimate = "unknown: both token prices are required"
    elif not known_tokens:
        subtotal = estimate = "unknown: no request attempt supplied usable token counts"
    else:
        subtotal = (
            f"{cost:.6f} USD ({len(known_tokens)}/{len(attempts)} attempts with usage)"
        )
        estimate = (
            "unknown: request attempts are missing usage"
            if missing_usage
            else f"{cost / len(all_runs) * 1000:.6f} USD (this sample's request mix)"
        )
    summary = {
        "UTC window": f"{started.isoformat(timespec='microseconds')} to {ended.isoformat(timespec='microseconds')}",
        "Cases / repeats / assessments": f"{len(rows)} / {repeat} / {len(all_runs)}",
        "Incident corpus records (synthetic / sanitized samples)": (
            f"{len(INCIDENTS)} ({sum(i['source_dataset'] == 'synthetic' for i in INCIDENTS)} / "
            f"{sum(i['source_dataset'] == 'sanitized_samples' for i in INCIDENTS)})"
        ),
        "Incident corpus SHA256": hashlib.sha256(
            json.dumps(
                sorted(INCIDENTS, key=lambda i: i["incident_id"]), sort_keys=True
            ).encode("utf-8")
        ).hexdigest(),
        "Mean rubric score (all assessments)": f"{statistics.mean(totals):.2f} / 10",
        "Minimum rubric score": f"{min(totals):g} / 10",
        "Level correct (all assessments)": f"{sum(result['level'] == row['case']['expected']['level'] for row in rows for result in row['runs'])}/{len(all_runs)}",
        "Route correct (all assessments)": f"{sum(result['route'] == row['case']['expected']['route'] for row in rows for result in row['runs'])}/{len(all_runs)}",
        "Citation rubric satisfied (all assessments)": f"{sum(item['cite'] == 1 for item in all_marks)}/{len(all_runs)}",
        "System 2 requested / SDK attempts / cache hits / failed": f"{len(requested)} / {len(attempts)} / {len(cached)} / {len(failed)}",
        "SDK attempts with known / missing token usage": f"{len(known_tokens)} / {missing_usage}",
        f"Same level, route and comments across {repeat} repeats": f"{sum(row['same'] for row in rows)}/{len(rows)} cases"
        if repeat > 1
        else "not assessed: one repeat",
        "Latency p50 / p95, no System 2 requested (ms)": _latency(
            [r["latency_ms"] for r in all_runs if not r["system2_attempted"]]
        ),
        "Latency p50 / p95, System 2 requested (ms)": _latency(
            [r["latency_ms"] for r in requested]
        ),
        "Tokens per SDK attempt with usage, mean in / out": (
            f"{statistics.mean(t[0] for t in known_tokens):.1f} / {statistics.mean(t[1] for t in known_tokens):.1f}"
            if known_tokens
            else "not measured"
        ),
        "Input / output price (USD per million tokens)": f"{price_in:g} / {price_out:g}"
        if price_in is not None
        else "not supplied",
        "Observed token-cost subtotal": subtotal,
        "Estimated token cost per 1,000 assessments": estimate,
    }
    return rows, summary


def gate_failures(
    rows: list, min_score: float = 10, require_repeatable: bool = False
) -> list[str]:
    failures = []
    for row in rows:
        case_id = row["case"]["id"]
        for index, (result, total) in enumerate(
            zip(row["runs"], row["totals"]), start=1
        ):
            if total < min_score:
                failures.append(
                    f"{case_id} repeat {index}: score {total:g} < {min_score:g}"
                )
            if result["system2_attempted"] and result["system2"] is None:
                failures.append(
                    f"{case_id} repeat {index}: requested System 2 unavailable"
                )
        if require_repeatable and row["same"] is not True:
            failures.append(f"{case_id}: repeatability requirement unmet")
    return failures


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def report(mode: str, repeat: int, rows: list, summary: dict) -> str:
    lines = [
        f"# Eval report: mode `{mode}`",
        "",
        f"Model setting: `{config.MODEL}` · seed {config.SEED} · temperature {config.TEMPERATURE}.",
        "",
        "All repeats contribute to quality and timing metrics. Provider response caches are cleared before each non-fast assessment.",
        "This synthetic dataset was used to tune the rules; scores measure calibration, not performance on unseen changes.",
        "",
        "Latency covers the in-process assessment, including failed provider attempts; it excludes process startup and report generation.",
        "SDK attempts count client invocations, not proof of delivery to Groq. Token costs use supplied prices and observed usage only.",
        "These are not invoices, verified savings, daily headroom, or Caveman evidence. Missing usage prevents a complete per-1,000 estimate.",
        "No request attempts means no provider-cost sample, not zero application operating cost.",
        "",
        "| Metric | Value |",
        "|---|---|",
        *(f"| {_cell(key)} | {_cell(value)} |" for key, value in summary.items()),
        "",
        "| Case | Title | Expected | Observed levels | Paths | Mean / min score | p50 / p95 ms | Same across repeats |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        case = row["case"]
        levels = ", ".join(sorted({r["level"] for r in row["runs"]}, key=LEVELS.index))
        paths = ", ".join(sorted({r["path"] for r in row["runs"]}))
        same = "not assessed" if row["same"] is None else "yes" if row["same"] else "NO"
        cells = [
            case["id"],
            case["title"],
            case["expected"]["level"],
            levels,
            paths,
            f"{statistics.mean(row['totals']):.2f} / {min(row['totals']):g}",
            _latency([r["latency_ms"] for r in row["runs"]]),
            same,
        ]
        lines.append("| " + " | ".join(_cell(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--mode",
        choices=["fast", "auto", "deep"],
        default="fast",
        help="fast is offline; auto/deep may send context to Groq",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--price-in", type=float, help="USD per million input tokens")
    parser.add_argument("--price-out", type=float, help="USD per million output tokens")
    parser.add_argument(
        "--min-score",
        type=float,
        default=10,
        help="minimum score required for EVERY assessment (default: 10)",
    )
    parser.add_argument(
        "--require-repeatable",
        action="store_true",
        help="fail unless every repeated answer matches",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        _validate_options(args.mode, args.repeat, args.price_in, args.price_out)
        if not math.isfinite(args.min_score) or not 0 <= args.min_score <= 10:
            raise ValueError("--min-score must be finite and between 0 and 10")
        if args.require_repeatable and args.repeat < 2:
            raise ValueError("--require-repeatable needs --repeat of at least 2")
    except ValueError as exc:
        parser.error(str(exc))
    rows, summary = run(args.mode, args.repeat, args.price_in, args.price_out)
    failures = gate_failures(rows, args.min_score, args.require_repeatable)
    command = f"uv run python scripts/run_evals.py --mode {args.mode} --repeat {args.repeat} --min-score {args.min_score:g}"
    if args.require_repeatable:
        command += " --require-repeatable"
    if args.price_in is not None:
        command += f" --price-in {args.price_in:g} --price-out {args.price_out:g}"
    summary["Reproduction command"] = f"`{command}`"
    summary["Quality gate"] = (
        f"{'FAIL' if failures else 'PASS'}: minimum score {args.min_score:g}; repeatability {'required' if args.require_repeatable else 'observed only'}; provider failures forbidden"
    )
    slug = (
        ""
        if args.mode == "fast"
        else "-" + re.sub(r"[^A-Za-z0-9_.-]+", "-", config.MODEL)
    )
    out = args.out or ROOT / "docs" / "evidence" / f"evals-{args.mode}{slug}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    content = report(args.mode, args.repeat, rows, summary)
    if failures:
        content += (
            "\n## Gate failures\n\n"
            + "\n".join(f"- {item}" for item in failures)
            + "\n"
        )
    out.write_text(content, encoding="utf-8")
    print(
        "\n".join(f"{key}: {value}" for key, value in summary.items())
        + f"\nwrote {out}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
