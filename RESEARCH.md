# Research — pokemon-tcg-ai-battle

Durable facts. Anything learned the expensive way goes here so no future run pays for it twice.

## Identity / standing

- Kaggle user `thtennant` competes as part of **team "zhang et al."** (teamId `16401588`).
  Members: `alancai27, mger10, stepheneshundanquah, thtennant, tomiwaakingbade`.
- **The submission history is SHARED across the whole team.** Undescribed entries
  (`submission.tar.gz`, `submission (2).tar.gz`, "tinkering around", "suck it tomiwa") are
  teammates', not ours. Do not read them as our own past work.
- Leaderboard shows the **best of your 2 most recent (active) submissions**. Older ones stop
  counting entirely — a strong artifact that has scrolled out of the top 2 contributes nothing.

## Submission mechanics (verified working 2026-08-09)

```bash
kaggle competitions submit -c pokemon-tcg-ai-battle -f <tarball> -m "<message>"
kaggle competitions submissions -c pokemon-tcg-ai-battle -v | head -5   # verify + read scores
```
- The CLI prints `N submissions remaining today` on success — the cheapest way to read the cap.
- Daily cap 5. Artifact is a `.tar.gz` whose ROOT contains `main.py`, `deck.csv`, and the `cg/`
  engine (plus any modules `main.py` imports). Built by `agent/build_submission.sh`
  with `CG_LIB_PATH=<repo>/cg`.
- New agents enter matchmaking at 600 and converge over a few hours.

## Local environment (NixOS box, /home/nixos/tempo)

- `./scripts/run.sh` is REQUIRED for anything importing `cg` — it puts `libstdc++.so.6` on
  `LD_LIBRARY_PATH` (the precompiled `libcg.so` needs it; Kaggle's sandbox has it, NixOS does not).
- `.venv` is uv-managed and has **no pip**. Install with
  `uv pip install --python .venv/bin/python <pkg>`.
- `kaggle_environments==1.32.0` is what the ladder runs; installed 2026-08-09.
  `k.make("cabt", ...)` is the competition env and works locally.
- The cg engine exposes 1267 cards. Game API is global/stateful:
  `battle_start(deckA, deckB) -> obs`, `battle_select(indices) -> obs`, `battle_finish()`.
  One game per process — parallelise with `multiprocessing` spawn, not threads.
- **DISK HAZARD:** root fs was 99% full (4.4 GB free of 457 GB) on 2026-08-09. `/tmp/claude-1000`
  held 84 GB of *other* sessions' scratchpads (oss-campaign 32 GB, ai-wizard 24 GB, -home-nixos
  21 GB) — those are not ours to delete. Keep this project's footprint small; a full disk shows up
  as opaque `ENOSPC` tool failures, not as a disk error.

## THE PROVEN ARTIFACT (most important fact in this file)

The best repeatable thing we own is the **Crustle ex-immune control wall**, 366-line
`crustle_rules.py`. Live scores, same file re-shipped unmodified four times:

| ref | date | score |
|---|---|---|
| 54015053 | 2026-06-24 | 791.3 |
| 54041091 | 2026-06-25 | 795.3 |
| 54181814 | 2026-06-29 | 775.6 |
| 54794471 | 2026-07-18 | 776.9 |

...and 863 once, earlier. It converges **775–795**. Variance between identical re-ships is
roughly ±10, so a ~50pt live delta is real signal and a ~10pt one is not.

**The binary was LOST** (workspace moved from `/home/gradient/projects/ai/tempo`; `*.tar.gz` is
gitignored). It is now reproducible from git alone:

```bash
bash scripts/build_proven_crustle.sh          # -> experiments/submission_crustle_proven.tar.gz
```

Recipe, in case that script is ever lost too: `git archive da08caf agent search`, then overwrite
`agent/deck.csv` with `data/decks/crustle.csv` (the deck.csv committed at that commit is a
leftover from a different archetype — the ship scripts always overwrote it), build with that
commit's own `agent/build_submission.sh` and the root manylinux2014 `engine_rs` wheel, then repack
without `__pycache__`. Verified 2026-08-09 to reproduce the shipped payload byte-for-byte.

## What has been TRIED AND FAILED (do not repeat)

- **Editing `crustle_rules.py` on the proven base regresses live, twice, hard.** v8 (ref 54806735)
  = 692.7, v9 (ref 54835679) = 693.7, vs the untouched base's 776.9 one day earlier. Both had
  green local paired evals (v8: aggregate 50.9%→53.3% over 9 arms, 200 games/arm; v9: +9.2pt on
  the Alakazam arm at disjoint CIs). **~85pt live regression, replicated.**
- **Rebuilding the Crustle pilot from the current tree regresses.** v7 (528 lines, ref 54784247)
  = 655.0. Re-ship > rebuild.
- Other from-scratch elite-calibrated rules pilots all landed *below* the proven wall:
  alakazam 638.3, grimmsnarl v2 653.2, grimmsnarl 695.8, tusk 724.8, starmie v11 764.6,
  starmie v10 774.4.
- Public "LB 1100+" notebooks do NOT reproduce their claims from our account:
  "Psychic Anti-Meta V8 | LB 1100+" scored 655.2 and 721.9; "1084.5 Baseline" scored 672.1.
- BC2 imitation policy (1.29M elite decisions, 59.5% held-out move-match) = 649.0.

**Standing lesson: our local arena win-rate is not predictive of live ladder score.** Multiple
changes with clean, large, well-powered local gains lost ~85pts live. Do not trust a local paired
eval as sufficient evidence to ship over the proven base.

## Robustness (established 2026-08-09, `tools/robust_probe.py`)

`./scripts/run.sh -m tools.robust_probe --src <dir with agent/+search/> --games N` plays full
real-engine games driving BOTH seats through the deploy entry point, asserting on every decision:
no exception, legal selection (distinct ints in range, length in `[minCount,maxCount]`), engine
accepted it, per-move latency, and cumulative agent wall-clock vs the 600s game clock. An epsilon
fraction of moves are perturbed to a random *legal* selection to reach pathological states.
Takes `--src`, so two builds can be A/B'd on identical seeds.

Result over 1500 games / ~135k decisions each, identical seeds:

| | proven-366 | v9-488 |
|---|---|---|
| agent exceptions | 0 | 0 |
| illegal selections | 0 | 0 |
| engine rejects | 0 | 0 |
| hangs | 0 | 0 |
| games near 600s clock | 0 | 0 |
| latency p50 / p99 / max | 0.21 / 124 / 252 ms | 0.30 / 225 / 914 ms |
| worst cumulative game | 6.1 s | 7.7 s |

**Conclusion: robustness is NOT our bottleneck.** The deploy path does not crash, does not return
illegal moves, and uses ~1% of the game clock. The v8/v9 regression is a *play-quality* loss.
Do not spend further slots hunting crashes unless a submission actually errors.

## Pre-ship checklist

1. `bash scripts/build_proven_crustle.sh` (or the relevant ship script) to produce the tarball.
2. `./scripts/run.sh -m tools.robust_probe --src <extracted> --games 1500` → must be CLEAN.
3. Packed cabt smoke on the EXTRACTED tarball (catches loader-context bugs a module-import smoke
   cannot — e.g. `__file__` undefined under `exec`, which failed ref 54275057 outright):
   ```python
   env = kaggle_environments.make("cabt", configuration={"runTimeout": 600}, debug=True)
   steps = env.run([f"{d}/main.py", f"{d}/main.py"])   # both DONE, rewards not None
   ```
4. End the day with the **two strongest** agents active, not the two most recent experiments.
