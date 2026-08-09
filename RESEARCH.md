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

## THE PROVEN ARTIFACT IS DEAD — DO NOT RE-SHIP IT (superseded 2026-08-09)

> **Read this before the section below it.** The Crustle wall was re-shipped on 2026-08-09 as ref
> `55389333`, faithfully rebuilt from git, and converged to **449.2 → 462.4** — not the 775–795 it
> had drawn four times. The artifact is fine; **the archetype died.** In the 2026-08-08 ladder dump
> (9,300+ real games, `data/meta_aug/`) Kangaskhan/Crustle wins **43.96%** (n=323). The 775–795 band
> was a property of the *June* field and does not exist any more. Everything below is history.
>
> The general lesson is bigger than one deck: **a live score is a rating against the field of the
> day, so it decays as the field improves.** Any score in this file older than ~2 weeks is an
> upper bound, not a prediction. The whole rules-pilot library (Crustle, Starmie, Grimmsnarl,
> Alakazam, Tusk, Iono...) is calibrated to a June meta.

The best repeatable thing we owned was the **Crustle ex-immune control wall**, 366-line
`crustle_rules.py`. Live scores, same file re-shipped unmodified four times *in the June/July field*:

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

0. Justify the ship from **real-field** evidence (`data/meta_aug/`) or a live score — never from an
   arena win rate — and check which active submission it will evict.
1. Run the relevant ship/build script to produce the tarball, and confirm its mtime is *now*.
   (`scripts/build_proven_crustle.sh` still works but the Crustle wall is a dead archetype.)
2. `./scripts/run.sh -m tools.robust_probe --src <extracted> --games 1500` → must be CLEAN.
3. Packed cabt smoke on the EXTRACTED tarball (catches loader-context bugs a module-import smoke
   cannot — e.g. `__file__` undefined under `exec`, which failed ref 54275057 outright):
   ```python
   env = kaggle_environments.make("cabt", configuration={"runTimeout": 600}, debug=True)
   steps = env.run([f"{d}/main.py", f"{d}/main.py"])   # both DONE, rewards not None
   ```
4. End the day with the **two strongest** agents active, not the two most recent experiments.

## The CURRENT metagame (mined 2026-08-09 from the 2026-08-08 episode dump)

`data/ep_aug/pokemon-tcg-ai-battle-episodes-2026-08-08.zip` (740 MB) → `tools/meta_aug.py` →
`data/meta_aug/{archetypes,matchups,teams}.csv` + `data/meta_aug/decks/` (**153 exact winning
60-card lists, one per team, including every top-20 team**). ~9,300 decided real games between real
ladder agents. **This is the only local signal we have that predicts anything** — see the arena
warning below.

| archetype | share | win % |
|---|---|---|
| Marnie's Grimmsnarl / Morgrem | 30.4% | 46.4 |
| Fezandipiti / Alakazam | 17.8% | 49.9 |
| Lopunny / Froslass | 10.7% | 51.7 |
| **Dragapult / Meowth** | 6.3% | **58.0** |
| Teal Mask Ogerpon / Hero's Cape | 3.7% | 45.7 |
| **Kangaskhan / Crustle** | 3.5% | **43.96** ← our June wall |
| **Lucario / Hariyama** | 3.2% | **54.3** ← Majkel1337 (#1, 1218.7) |
| **Kangaskhan / Latias** | 2.7% | **63.2** ← Thai (#7) |

Dragapult/Meowth is the standout: it beats Grimmsnarl 62.2% and Fezandipiti/Alakazam 69.2%, i.e.
it beats **48% of the field**. Dipam Chakraborty (#5), 213tubo and Kh0a all play it at 66/67/59%
personal win rates. We have **no pilot that can fly it** — see below.

Regenerate after a new dump with:
`./scripts/run.sh -m tools.meta_aug --zip data/ep_aug/*.zip --out data/meta_aug`

## ⚠ OUR LOCAL ARENA IS ANTI-PREDICTIVE — never ship on an arena win rate

Measured 2026-08-09: the Crustle wall beats the top meta deck (Grimmsnarl, real August list)
**93.8%** in `tools/par_eval.py` while scoring **462** live. The arena's only opponents are *our own
bots*, so it measures "which deck best exploits our heuristics", not strength. This is the
mechanism behind every green-local/red-live regression in the section above (v8 −85, v9 −85, v7 −120).

Ship justification must come from **real-field evidence** (`data/meta_aug/`) or from a live score.
`tools/par_eval.py` is still the right tool for *robustness* and for **paired same-deck A/B of two
policies**, which is a relative question — just not for absolute strength or deck choice.
It now also has `--alternate` (seat-swapping; there was a real first-player bias) and two extra
pilots: `scorer` (the prior alone) and `hybrid` (search over the prior).

## SEARCH IS SETTLED — it does not beat the heuristic scorer. Stop trying. (2026-08-09)

**In every artifact shipped since June the search is dead code**: `main.agent` calls
`scorer.best_options` first and returns on success, so the Rust/MCTS branch below is unreachable.
The comment on that line explains it: *"beats our MCTS 63% h2h"*.

Re-enabled and measured properly as the `hybrid` pilot — determinized net-PUCT search over the
engine's native forward model on MAIN single-selects, rich scorer on **every other** decision
(lookahead layered *on top of* the prior; the configuration `agent/lookahead.py` never tried, since
that one used a static board eval at the leaf). Paired, same deck both seats, alternating seats:

| deck | hybrid search vs pure scorer |
|---|---|
| Crustle wall | 23.3% ± 10.7 (n=60) |
| Lucario / Majkel list | 50.0% ± 12.7 (n=60) |

Not vacuous — instrumented over 6 full games, search **diverges from the scorer on 305/423 (72.1%)**
of qualifying decisions. It makes a different choice 3 times in 4 and still only *matches* the prior.

Four independent refutations now:
1. ref `53915967` determinized UCT, 6s/move = **560.1** live (vs 776–795 rules pilots that week)
2. ref `53927392` Rust MCTS core, native 10× sims = **528.8** live
3. the `agent/lookahead.py` sweep (see its docstring — a rigorous negative, ~38–42%)
4. this run's `hybrid` A/B above

Mechanism (from the `lookahead.py` post-mortem, and it still applies): strategy fusion / phantom
lethals from determinized draws, plus a leaf evaluation weaker than the scorer's implicit tempo
knowledge. **Do not spend another slot on search depth without a fundamentally different value
function.**

## Our pilots are deck-SPECIFIC and cannot fly an unfamiliar list (2026-08-09)

Piloting Dipam Chakraborty's real Dragapult/Meowth list (the 58.0% best deck in the field):
scorer **0/32**, hybrid search **0/32**, floor 0/32, random 0/32 vs the scorer on Grimmsnarl —
while the *mirror* is ~44%, so the deck itself functions. Every one of our specialists
(`crustle_rules.py`, `lucario_rules.py`, `starmie_rules.py`, ...) is hand-written for one archetype,
and `scorer.py` dispatches to them by deck detection; with no specialist the generic path cannot
assemble a Stage-2 evolution combo deck. **Adopting a strong new archetype therefore costs a whole
new specialist**, which historically lands 638–776 in the June field. This is the central structural
problem with the method.

## Active-slot arithmetic (easy to get wrong, costs real LB points)

Only the **2 most recent** submissions are active and the LB shows the best of them. So every new
submission **evicts the older of the two currently active**. Before submitting, check what you are
about to evict — on 2026-08-09 a submission evicted `55288207` (716.1, a teammate's Alakazam
notebook we cannot rebuild), leaving the new entry paired with the 462.4 Crustle. Budget this
explicitly; end the day with the two strongest agents active.

## Build-script hazard

`scripts/build_lucario.sh` packs from a temp cwd, so a **relative** outfile silently failed to write
and left a stale artifact in place (fixed 2026-08-09 by absolutising `OUT`). Generally: never trust
a `.tar.gz` whose build you did not just run — check its mtime.

## Known-failing tests (pre-existing at HEAD, ship inside every artifact)

`./scripts/run.sh -m pytest tests/` → **8 passed, 3 failed** at unmodified HEAD:
`test_lethal_attack_is_taken`, `test_attack_preferred_over_end_when_nonzero`,
`test_go_first_prefers_second` — the agent picks END over a 120-damage KO. Runs against the mock
engine (`tests/mock_cg`), so it may be a fixture artifact (mock attack ids 101/102 vs the real
`all_attack()` table) — but it is unresolved, and `agent/lethal.py` (verified-lethal override) may
simply never be reached on the primary scorer path. Worth confirming: play quality is the diagnosed
bottleneck. `pytest` is not in `.venv` by default — `uv pip install --python .venv/bin/python pytest`.
