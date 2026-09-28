# Eval report: mode `fast`

Model setting: `openai/gpt-oss-20b` · seed 7 · temperature 0.0.

All repeats contribute to quality and timing metrics. Provider response caches are cleared before each non-fast assessment.
This synthetic dataset was used to tune the rules; scores measure calibration, not performance on unseen changes.

Latency covers the in-process assessment, including failed provider attempts; it excludes process startup and report generation.
SDK attempts count client invocations, not proof of delivery to Groq. Token costs use supplied prices and observed usage only.
These are not invoices, verified savings, daily headroom, or Caveman evidence. Missing usage prevents a complete per-1,000 estimate.
No request attempts means no provider-cost sample, not zero application operating cost.

| Metric | Value |
|---|---|
| UTC window | 2026-09-28T12:57:43.732946+00:00 to 2026-09-28T12:57:43.779819+00:00 |
| Cases / repeats / assessments | 20 / 5 / 100 |
| Incident corpus records (synthetic / sanitized samples) | 46 (16 / 30) |
| Incident corpus SHA256 | a06e2515d81bdad90628018b125ada684ba5675fc418e8223e5d72dc49b75841 |
| Mean rubric score (all assessments) | 10.00 / 10 |
| Minimum rubric score | 10 / 10 |
| Level correct (all assessments) | 100/100 |
| Route correct (all assessments) | 100/100 |
| Citation rubric satisfied (all assessments) | 100/100 |
| System 2 requested / SDK attempts / cache hits / failed | 0 / 0 / 0 / 0 |
| SDK attempts with known / missing token usage | 0 / 0 |
| Same level, route and comments across 5 repeats | 20/20 cases |
| Latency p50 / p95, no System 2 requested (ms) | 0.193 / 0.261 (n=100) |
| Latency p50 / p95, System 2 requested (ms) | not measured (n=0) |
| Tokens per SDK attempt with usage, mean in / out | not measured |
| Input / output price (USD per million tokens) | not supplied |
| Observed token-cost subtotal | not applicable: no provider request attempts |
| Estimated token cost per 1,000 assessments | not applicable: no provider request attempts |
| Reproduction command | `uv run python scripts/run_evals.py --mode fast --repeat 5 --min-score 10 --require-repeatable` |
| Quality gate | PASS: minimum score 10; repeatability required; provider failures forbidden |

| Case | Title | Expected | Observed levels | Paths | Mean / min score | p50 / p95 ms | Same across repeats |
|---|---|---|---|---|---|---|---|
| CHG-01 | Cut checkout's payment timeout to 500 ms | high | high | system1 | 10.00 / 10 | 0.21 / 0.875 (n=5) | yes |
| CHG-02 | Promo banner behind a flag | low | low | system1 | 10.00 / 10 | 0.208 / 0.228 (n=5) | yes |
| CHG-03 | HTTP client major upgrade in payment-gateway | high | high | system1 | 10.00 / 10 | 0.212 / 0.293 (n=5) | yes |
| CHG-04 | Shorter access tokens during a freeze | high | high | system1 | 10.00 / 10 | 0.207 / 0.218 (n=5) | yes |
| CHG-05 | Add a nullable column to orders | medium | medium | system1 | 10.00 / 10 | 0.237 / 0.354 (n=5) | yes |
| CHG-06 | Halve notification consumers to save cost | medium | medium | system1 | 10.00 / 10 | 0.195 / 0.25 (n=5) | yes |
| CHG-07 | ORM minor upgrade in inventory | medium | medium | system1 | 10.00 / 10 | 0.182 / 0.188 (n=5) | yes |
| CHG-08 | New payment sheet on mobile during a freeze | high | high | system1 | 10.00 / 10 | 0.18 / 0.196 (n=5) | yes |
| CHG-09 | Help-page copy fixes | low | low | system1 | 10.00 / 10 | 0.174 / 0.188 (n=5) | yes |
| CHG-10 | Rotate checkout's payment API key | medium | medium | system1 | 10.00 / 10 | 0.237 / 0.306 (n=5) | yes |
| CHG-11 | Bigger card-processor connection pool | high | high | system1 | 10.00 / 10 | 0.208 / 0.238 (n=5) | yes |
| CHG-12 | Move orders to a new node pool | medium | medium | system1 | 10.00 / 10 | 0.186 / 0.223 (n=5) | yes |
| CHG-13 | Drop a legacy stock column | high | high | system1 | 10.00 / 10 | 0.161 / 0.173 (n=5) | yes |
| CHG-14 | New sender name on order emails | low | low | system1 | 10.00 / 10 | 0.186 / 0.199 (n=5) | yes |
| CHG-15 | Frontend build tool major upgrade | medium | medium | system1 | 10.00 / 10 | 0.173 / 0.193 (n=5) | yes |
| CHG-16 | Save card for next time | medium | medium | system1 | 10.00 / 10 | 0.244 / 0.448 (n=5) | yes |
| CHG-17 | Structured logs in the email retry handler | low | low | system1 | 10.00 / 10 | 0.181 / 0.19 (n=5) | yes |
| CHG-18 | Low-stock warning behind a flag | low | low | system1 | 10.00 / 10 | 0.198 / 0.206 (n=5) | yes |
| CHG-19 | Longer stock-count cache | medium | medium | system1 | 10.00 / 10 | 0.177 / 0.191 (n=5) | yes |
| CHG-20 | New NAT gateway for card-processor traffic | high | high | system1 | 10.00 / 10 | 0.18 / 0.194 (n=5) | yes |
