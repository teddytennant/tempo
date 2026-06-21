# Eval Methodology

The single most important discipline: **the eval must be honest about noise.** The field measured
the same code swinging 60%→38% over 50 games (±~14pt). Naive win-rate chasing overfits to noise.

## Rules

1. **Sample size.** Report win-rate with confidence intervals over **hundreds** of games. Treat
   <10pt swings as noise; only ≥10pt sustained deltas count as signal.
2. **Anomaly-driven, not score-driven.** Track deterministic failure modes, not just win-rate:
   - `attack_no_damage` — attacks landing 0 (mis-scored utility / blocked effects)
   - `no_offense_loss` — losses with ≤1 damaging attack landed (pressure failure)
   - `deckout_loss` — self-milling to deck depletion
   - `error_games` — agent crash / fallback
   A change must reduce anomalies AND not regress win-rate beyond noise.
3. **The real ladder is ground truth.** Local sims (ctypes harness and the official `cabt` env) both
   mispredicted ladder rank for the field. Use offline eval to *filter* candidates and catch
   regressions; make promotion decisions on the live ladder.

## Harness

- `arena/` evaluates an agent in the official `cabt` env (`kaggle_environments.make('cabt')`,
  mirroring `wmh/ptcg-abc` `tools/cabt_eval.py`) vs a set of meta decks / baseline agents.
- `tools/` automates ladder A/B: stage candidates offline, submit the best 2/day (only the latest 2
  are scored), log Elo over time.
- **Deployment smoke test:** load the final `submission.tar.gz` (incl. any `.so`) in a clean
  Kaggle-image container; one self-play validation game must finish error-free within the 10-min clock.

## CI

`pytest` (contract tests vs mock engine) + `cargo test` + the parity harness run on push. Contract
tests gate every agent change: never-crash, always-legal, in-budget.
