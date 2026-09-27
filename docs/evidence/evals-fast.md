# Eval report: mode `fast`

Run 2026-09-27 20:21 UTC · `uv run python scripts/run_evals.py --mode fast --repeat 5` · seed 7 · temperature 0.0

| Metric | Value |
|---|---|
| Mean rubric score | 10.00 / 10 |
| Level correct | 20/20 |
| Route correct | 20/20 |
| Cases sent to System 2 (Groq) | 0/20 |
| System 2 unavailable (held for review) | 0/20 |
| Same level and comments across 5 runs | 20/20 |
| Latency p50 / p95, System 1 path (ms) | 0.047 / 0.082 |
| Latency p50 / p95, System 2 path (ms) | no Groq calls |
| Tokens per Groq call, mean in / out | no Groq calls |
| Estimated cost per 1,000 assessments (USD) | pass --price-in and --price-out |

| Case | Title | Expected | Got | Path | Score | Latency (ms) | Same across runs |
|---|---|---|---|---|---|---|---|
| CHG-01 | Cut checkout's payment timeout to 500 ms | high | high | system1 | 10/10 | 0.131 | yes |
| CHG-02 | Promo banner behind a flag | low | low | system1 | 10/10 | 0.057 | yes |
| CHG-03 | HTTP client major upgrade in payment-gateway | high | high | system1 | 10/10 | 0.06 | yes |
| CHG-04 | Shorter access tokens during a freeze | high | high | system1 | 10/10 | 0.054 | yes |
| CHG-05 | Add a nullable column to orders | medium | medium | system1 | 10/10 | 0.078 | yes |
| CHG-06 | Halve notification consumers to save cost | medium | medium | system1 | 10/10 | 0.12 | yes |
| CHG-07 | ORM minor upgrade in inventory | medium | medium | system1 | 10/10 | 0.065 | yes |
| CHG-08 | New payment sheet on mobile during a freeze | high | high | system1 | 10/10 | 0.075 | yes |
| CHG-09 | Help-page copy fixes | low | low | system1 | 10/10 | 0.05 | yes |
| CHG-10 | Rotate checkout's payment API key | medium | medium | system1 | 10/10 | 0.069 | yes |
| CHG-11 | Bigger card-processor connection pool | high | high | system1 | 10/10 | 0.057 | yes |
| CHG-12 | Move orders to a new node pool | medium | medium | system1 | 10/10 | 0.052 | yes |
| CHG-13 | Drop a legacy stock column | high | high | system1 | 10/10 | 0.057 | yes |
| CHG-14 | New sender name on order emails | low | low | system1 | 10/10 | 0.051 | yes |
| CHG-15 | Frontend build tool major upgrade | medium | medium | system1 | 10/10 | 0.05 | yes |
| CHG-16 | Save card for next time | medium | medium | system1 | 10/10 | 0.062 | yes |
| CHG-17 | Structured logs in the email retry handler | low | low | system1 | 10/10 | 0.062 | yes |
| CHG-18 | Low-stock warning behind a flag | low | low | system1 | 10/10 | 0.046 | yes |
| CHG-19 | Longer stock-count cache | medium | medium | system1 | 10/10 | 0.05 | yes |
| CHG-20 | New NAT gateway for card-processor traffic | high | high | system1 | 10/10 | 0.077 | yes |
