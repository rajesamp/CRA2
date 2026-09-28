# Eval report: mode `fast`

Model setting: `openai/gpt-oss-20b` · seed 7 · temperature 0.0.

All repeats contribute to quality and timing metrics. Provider response caches are cleared before each non-fast assessment.
These 20 synthetic change cases were used to tune the rules; selected context also includes approved sanitized incident samples. Scores measure calibration, not performance on unseen changes.
Repeatability compares status, score, level, review route, comments, questions, freeze status, effective settings, and surfaced conflicts.

Latency covers the in-process assessment, including failed provider attempts; it excludes process startup and report generation.
SDK attempts count client invocations, not proof of delivery to Groq. Token costs use supplied prices and observed usage only.
These are not invoices, verified savings, daily headroom, or Caveman evidence. Missing usage prevents a complete per-1,000 estimate.
No request attempts means no provider-cost sample, not zero application operating cost.

| Metric | Value |
|---|---|
| UTC window | 2026-09-28T13:46:17.905506+00:00 to 2026-09-28T13:46:17.962515+00:00 |
| Cases / repeats / assessments | 20 / 5 / 100 |
| Incident corpus records (synthetic / sanitized samples) | 46 (16 / 30) |
| Incident corpus SHA256 | a06e2515d81bdad90628018b125ada684ba5675fc418e8223e5d72dc49b75841 |
| Rules SHA256 | 32be90242abb164b2ecd8f0faee32f29854dcf6f551deaf28d65841e40e47865 |
| Catalog SHA256 | a998c4df9345f1955e69c1724bae16b9fd30782db39c67142a68742154251a76 |
| Team settings SHA256 | b9cdbd5e3291a75f8b3965832e9fa8cd3a562a149a0085aef1969695f478b4db |
| Mean rubric score (all assessments) | 10.00 / 10 |
| Minimum rubric score | 10 / 10 |
| Assessed / needs clarification | 100 / 0 |
| Level correct (all assessments) | 100/100 |
| Route correct (all assessments) | 100/100 |
| Citation rubric satisfied (all assessments) | 100/100 |
| System 2 requested / SDK attempts / cache hits / failed | 0 / 0 / 0 / 0 |
| SDK attempts with known / missing token usage | 0 / 0 |
| Same decision context across 5 repeats | 20/20 cases |
| Latency p50 / p95, no System 2 requested (ms) | 0.228 / 0.362 (n=100) |
| Latency p50 / p95, System 2 requested (ms) | not measured (n=0) |
| Tokens per SDK attempt with usage, mean in / out | not measured |
| Input / output price (USD per million tokens) | not supplied |
| Observed token-cost subtotal | not applicable: no provider request attempts |
| Estimated token cost per 1,000 assessments | not applicable: no provider request attempts |
| Reproduction command | `uv run python scripts/run_evals.py --mode fast --repeat 5 --min-score 10 --require-repeatable` |
| Quality gate | PASS: minimum score 10; repeatability required; provider failures forbidden |

| Case | Title | Expected | Observed outcomes | Paths | Mean / min score | p50 / p95 ms | Same across repeats |
|---|---|---|---|---|---|---|---|
| CHG-01 | Cut checkout's payment timeout to 500 ms | high | high | system1 | 10.00 / 10 | 0.217 / 0.672 (n=5) | yes |
| CHG-02 | Promo banner behind a flag | low | low | system1 | 10.00 / 10 | 0.23 / 0.438 (n=5) | yes |
| CHG-03 | HTTP client major upgrade in payment-gateway | high | high | system1 | 10.00 / 10 | 0.223 / 0.23 (n=5) | yes |
| CHG-04 | Shorter access tokens during a freeze | medium | medium | system1 | 10.00 / 10 | 0.206 / 0.213 (n=5) | yes |
| CHG-05 | Add a nullable column to orders | medium | medium | system1 | 10.00 / 10 | 0.26 / 0.402 (n=5) | yes |
| CHG-06 | Halve notification consumers to save cost | medium | medium | system1 | 10.00 / 10 | 0.214 / 0.33 (n=5) | yes |
| CHG-07 | ORM minor upgrade in inventory | medium | medium | system1 | 10.00 / 10 | 0.267 / 0.383 (n=5) | yes |
| CHG-08 | New payment sheet on mobile during a freeze | low | low | system1 | 10.00 / 10 | 0.217 / 0.227 (n=5) | yes |
| CHG-09 | Help-page copy fixes | low | low | system1 | 10.00 / 10 | 0.22 / 0.293 (n=5) | yes |
| CHG-10 | Rotate checkout's payment API key | medium | medium | system1 | 10.00 / 10 | 0.307 / 0.362 (n=5) | yes |
| CHG-11 | Bigger card-processor connection pool | high | high | system1 | 10.00 / 10 | 0.268 / 0.282 (n=5) | yes |
| CHG-12 | Move orders to a new node pool | medium | medium | system1 | 10.00 / 10 | 0.24 / 0.415 (n=5) | yes |
| CHG-13 | Drop a legacy stock column | high | high | system1 | 10.00 / 10 | 0.218 / 0.246 (n=5) | yes |
| CHG-14 | New sender name on order emails | low | low | system1 | 10.00 / 10 | 0.218 / 0.261 (n=5) | yes |
| CHG-15 | Frontend build tool major upgrade | medium | medium | system1 | 10.00 / 10 | 0.224 / 0.244 (n=5) | yes |
| CHG-16 | Save card for next time | medium | medium | system1 | 10.00 / 10 | 0.286 / 0.3 (n=5) | yes |
| CHG-17 | Structured logs in the email retry handler | low | low | system1 | 10.00 / 10 | 0.213 / 0.227 (n=5) | yes |
| CHG-18 | Low-stock warning behind a flag | low | low | system1 | 10.00 / 10 | 0.254 / 0.311 (n=5) | yes |
| CHG-19 | Longer stock-count cache | medium | medium | system1 | 10.00 / 10 | 0.225 / 0.232 (n=5) | yes |
| CHG-20 | New NAT gateway for card-processor traffic | high | high | system1 | 10.00 / 10 | 0.23 / 0.239 (n=5) | yes |
