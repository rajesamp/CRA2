# Evals

`cases.json` holds 20 changes to the made-up checkout system in `data/`. Each case has:

- `change`: the structured change, exactly what `cra2` takes as input.
- `expected`: the level, the route, the risk areas the three comments must
  flag (`flags`), and the incidents at least one comment should cite
  (`cite_any`).
- `rubric`: how the answer is marked, 10 points in total.

| Check | Points | Full marks when |
|---|---|---|
| level | 4 | The level matches. One level too high (the cautious side) earns 1 point; too low earns 0. |
| route | 2 | The recommended route matches. |
| flags | 2 | The three comments cover the expected areas (points are shared out when only some are covered). |
| cite | 1 | A comment cites one of `cite_any`. When `cite_any` is empty, every comment must cite evidence. |
| format | 1 | Exactly three comments, no approval language, and the advisory line is present. |

Coverage: all 8 services and 7 change types. Expected levels are 5 low,
8 medium and 7 high. The cases include freeze windows (CHG-04, CHG-08), a
degraded dependency (CHG-10, CHG-16), missing rollback plans (CHG-01, CHG-12,
CHG-13, CHG-20), config drift (CHG-01, CHG-11), deploy order (CHG-05, CHG-13,
CHG-19), and repeats of past incidents.

Run `uv run python scripts/run_evals.py --help` for the options. System 1's
weights were tuned with these cases in view, so a perfect `fast` score is a
calibration check. Add unseen cases before you trust how well it generalises.
