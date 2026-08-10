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

## ⚠ LIVE SCORES SWING >200 POINTS WHILE CONVERGING — never conclude from a fresh reading

Watched on a single ref inside one run (2026-08-09, `55389997`): **698.6 → 775.6 → 559.1** over a
few hours. `55389333` moved 449.2 → 462.4 → 506.0 → 540.1 in the same window. A score read within
hours of submitting is *not* converged.

Consequences, all learned the expensive way:
- **Do not evict an active slot** on the strength of a fresh reading of its replacement.
- **Do not draw an A/B conclusion** from two refs read at different ages. The slot-3 "deck swap is
  worth +190" claim was computed at one ref's transient peak; on later readings the same pair is
  ~19 points apart. It is still the best hypothesis we have, but it is **unconfirmed**.
- RESEARCH.md's older "±10 between identical re-ships" figure was measured on *settled* June
  scores. It does not apply to same-day readings.

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

### ROBUSTNESS IS CLOSED — exhausted 2026-08-10, three independent layers, all clean

The result above was against 11 curated decks. It has now been pushed as far as it can usefully go.
**Do not open this angle again unless a submission actually errors.**

1. **Real field.** `robust_probe --decks-dir data/meta_aug/decks` against **all 153 real ladder
   decklists** (both seats through the deploy path, eps=0.12), on the shipped v3 tree:
   920 games / **134,454 decisions** — 0 exceptions, 0 illegal, 0 engine rejects, 0 hangs, 0 moves
   over 1s. Latency p50/p99/max **0.33 / 232 / 268 ms**; worst cumulative game **6.1s of 600s**.
   v4 re-run: same, clean.
2. **Context coverage** (new `tools/ctx_fuzz.py`). The engine defines **49 `SelectContext` values**;
   a normal game asks only some, and an unreached context is code shipped unexecuted. A 1,224-game
   field sweep reaches **31/49** over 188,103 live decisions. Sampling **400 real episodes** from
   the dump, the actual ladder exhibits **31** distinct contexts over 130,603 decisions. The only
   real-field context our probe never reaches is **32 `TO_DECK_ENERGY` (3 occurrences in 130,603 =
   0.002%)**; we additionally reach `36 DISABLE_ATTACK`, which the sample lacks. **So self-play
   against the field's own decklists reproduces the field's state distribution** — layer 1's clean
   result is not an artifact of narrow coverage.
3. **Adversarial observation mutation** (`ctx_fuzz.py` phase 2). Captured observations rewritten
   into states real play never produced: the same board under **each of the 49 contexts**;
   degenerate bounds `(0,0) (n,n) (n+1,n+1) (2,1)`; empty/truncated option lists; optional keys
   nulled and dropped; bench/hand/discard/active/prize/energyZone/stadium stripped; turn 0, turn
   9999, and a *decided* game still asking; blanked option-record fields.
   **325,070 mutants: 0 exceptions, 0 illegal selections, max latency 20 ms.**
   (Only no-raise + usable-selection is asserted — a mutated board is not necessarily reachable, so
   a bad *choice* on one means nothing. `minCount > n` and `minCount > maxCount` are exempted from
   the legality assert because no legal answer exists.)
4. **Real ladder positions:** all **10,563** records in `records_11447.jsonl` replayed through the
   deploy entry point (`prize_agreement --all-games`) — **0 agent errors**.
5. **Cold start:** import → first decision **0.22 s**, consistent with the field's
   `remainingOverageTime` opening at 599.62 of 600. No first-move timeout risk.

### Kaggle `cabt` env limits (read from the spec 2026-08-10)

`actTimeout` default **0** (no per-act cap enforced by `kaggle_environments`), `runTimeout` default
**2000 s** per episode, `episodeSteps` 10,000,000. The 600 s figure is the *game's own*
`remainingOverageTime` pool, visible in every observation. Our worst game spends 6.1 s across both
seats — ~1%.

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


## Real-field agreement harness — `tools/prize_agreement.py` (built 2026-08-09)

**The replacement for the anti-predictive arena for *relative policy* questions.** Replays real
decisions by frontier players through the deploy entry point and reports agreement per decision
type. Takes `--src`, so two packed trees are scored on identical decisions.

```bash
./scripts/run.sh -m tools.prize_agreement --src experiments/<build>_src --json out.json
```

Corpus: `data/bc_lucario/records_11447.jsonl` = 4,074 *winning* decisions by frontier Lucario
players from the 2026-08-08 dump (harvested by `tools/harvest_lucario.py`). **99.1% of it routes
through `lucario_rules`**, so it measures the shipping code path. It is Lucario-only; another
archetype needs its own corpus.

Shipped-agent baseline: all **52.9%** (n=4074), main 45.5%, attack-available 39.1%,
**swing-or-end 88.0%**, attack-choice 36.4%, sub-selects 64.9%.

Caveat that matters: single-decision agreement **over-penalises benign turn ordering** (playing a
card then attacking scores as a disagreement with an elite who attacked immediately). Judge policy
changes on the confound-free buckets — `main/swing-or-end`, `main/attack-choice` — and on whether
any bucket *regresses*.

## PRIZE-TRADE ECONOMICS IS SETTLED — it is not our bottleneck (2026-08-09)

Measured at both levels; do not spend another slot here.

1. **Policy.** Pure swing-or-end decisions: **88.0%** agreement with elites. Multi-attack decisions:
   we pick a different attack **6 times in 133**. Of 149 "we attacked, elite developed" spots, **124
   are correct** (112 lethal-verifier-proved wins + 12 scorer game-winning swings); only **25 of
   2,530 MAIN decisions (1.0%)** are genuinely premature, **15 of them one card** (Premium Power
   Pro, scored −1 unless its +30 exactly converts a KO — unresolved, the engine DB exposes no card
   text so I could not tell whether our rule or the elites are right).
2. **Deck.** Over the 17 archetypes with ≥100 games joined to real decklists:
   `corr(win%, max prize liability) = −0.13`, `corr(win%, # multi-prize Pokemon) = **+0.54**`.
   Decks with *more* 2/3-prize threats win *more*. "Build a low-prize deck" is dead; our 3-prize
   Mega-ex is not a handicap.
3. **The documented prize guard is wrong.** `lucario_rules.py`'s header promised a guard against
   over-exposing the 3-prize Mega-ex; `_my_prize_count` was defined and never called. Implemented
   and ablated on the 4,074 decisions: **9 decisions moved away from elite play, 0 toward it.**
   Reverted. Lucario is a one-attacker aggro deck — elites promote the Mega anyway. A companion
   "KO that takes our last prizes" bonus was a measured **no-op**.

## Keep a specialist's decklist bound to the deck we actually ship (fixed 2026-08-09)

`lucario_rules.LUCARIO_DECK` is the determinization deck for the multi-step lethal verifier
(`scorer.py:521` — its only consumer). It was hardcoded, so piloting Majkel1337's list left the
verifier searching a deck differing on **16 of 60 cards**, free to prove a lethal that draws a card
we own zero of. Now loaded from the bundled `deck.csv` with a fallback. **Every specialist with a
`*_DECK` constant has this latent bug — check before shipping that archetype on a new list.**

## Thwackey / Dipplin — the pure single-prize deck, and we cannot fly it (2026-08-09)

Sixth Sense's list (`data/decks/thwackey_sixthsense.csv`): 60 cards, every Pokémon Stage-0/Stage-1,
**zero ex**, 59.5% real-field win rate, no Stage-2 line (so the Dragapult failure mode shouldn't
apply). Under the **generic** pilot vs our Lucario specialist: **10.4% ± 8.6 (n=48, alternating
seats)**. It functions — this is not the 0/32 Dragapult result — but the generic path plays it far
below specialist level. Restates the structural problem: **a strong archetype is worthless without a
hand-written specialist**, and that is the only remaining lever big enough to matter.

## ⚠ SPECIALIST DISPATCH IS BLIND BEFORE THE BOARD EXISTS (found 2026-08-09, fixed for Lucario only)

`scorer.best_options` picks an archetype specialist by calling `is_<archetype>_deck(state, me_i)`,
and **every one of those detects the archetype from cards VISIBLE on our side.** At
`SelectContext.IS_FIRST` (41, "would you like to go first?") the question is asked *before the
opening hand is dealt*: active, bench, hand and discard are all empty. Detection returns False, the
specialist is bypassed, and generic `scorer._score_sub` decides.

Measured on the 2026-08-08 dump: this fired on **93 of 93** real IS_FIRST positions.

The generic rule it fell through to was never measured — *"going second is often better for a setup
deck"* — and it is **wrong**:

- **Real field:** real ladder Lucario players answered YES (go first) in **91 of 93** positions.
- **Causal, in-engine** (`tools/first_turn_ab.py`, mirror games, identical deck and policy on both
  seats, only the turn-order answer forced, arm- and seat-swapped): over **2,200 games the player
  who went first won 54.0% ± 2.1 (z=3.7, p≈0.0002)**. Split by arm: asked player won 51.8%/56.0%
  forced-first vs 47.0%/45.5% forced-second.

Worse, the repo held **three conflicting opinions** and the untested one won:
`scorer._score_sub` NO, `lucario_rules.score_sub` YES +150, `main.py` fallback YES. The specialists'
preference was **dead code in every artifact ever shipped, including the 776.9 Crustle wall** — so
every historical score in this file was set while conceding the first turn.

**Fix applied to `lucario_rules.is_lucario_deck` only:** when nothing at all is visible on our side,
fall back to the bundled `deck.csv` (we ship the decklist — there is no need to infer it). The guard
requires active, bench, hand AND discard simultaneously empty, so it can only fire before the
opening hand exists and no in-game decision changes. IS_FIRST agreement 2.2% → **97.8%**; paired on
4,074 elite decisions no bucket regressed (all 52.90 → 53.73).

### GENERALISED AND FIXED AT THE SOURCE (2026-08-10) — going first is right for the WHOLE field

`tools/first_turn_field.py` (new) reads the episode zip directly, finds every IS_FIRST decision,
attributes it to the answering seat's 60-card deck, labels the archetype and tabulates YES/NO.

Over **1,400 episodes / 305 IS_FIRST answers / 25 archetypes**: **YES 99.0% overall, and 100% in
every one of the 9 archetypes with n ≥ 8** (Grimmsnarl 85, Fezandipiti 50, Lopunny/Froslass 33,
Ogerpon 28, Dragapult 25, Kangaskhan 19, Cornerstone/Kangaskhan 10, Lucario 8, Lopunny 8).
Of those same 305 asked seats the one that ended up going first won **54.4%** — an independent
replication of the forced mirror A/B's 54.0% ± 2.1 from a completely different data source.

So this was never a Lucario fact. **`scorer._score_sub`'s IS_FIRST default is now `YES` (+150)**,
committed `68c86c0`. That makes the fix archetype-independent: a specialist that fails to load, or
a list we have not written one for, no longer concedes the opening turn.

Paired A/B on 4,074 elite decisions, v3 vs v4: **every bucket byte-identical** (all 53.73%, main
45.53%, swing-or-end 88.00%, other 67.04%) — confirming it is pure defense-in-depth on the shipped
Lucario path, where the specialist already answers. Do not expect a live gain from it.

Correction to the note above: `starmie_rules`, `fezandipiti_rules` and `dunsparce_rules` **already
had** a pre-board deck.csv fallback (fezandipiti's docstring records IS_FIRST answered YES
2,125/2,125 in its own corpus). Still without one, and now no longer load-bearing: `crustle`,
`grimmsnarl`, `tusk`, `iono`, `cinderace`, `hops_snorlax`.

**The general lesson:** any decision taken before the board reveals the archetype is decided by
untested generic defaults. `SelectContext.MULLIGAN` (42) is the next candidate — it appears in
neither our corpus nor 400 sampled real episodes, so the engine may auto-resolve it; confirm before
spending effort.

## ENERGY / TEMPO SEQUENCING INSIDE THE TURN IS SETTLED — not our bottleneck (2026-08-09)

- **Attach targeting is right.** Raw agreement makes `main/attach-to-bench` look like a disaster at
  **18.6%** — that is the turn-ordering confound (we play a card first, attach later in the turn).
  Restricted to decisions where the elite *and* we both attached at the same point (`tools/
  attach_probe.py`), area agreement is **89.8% (149/166)**; we put energy on the bench **37.3%** of
  the time vs the elites' **40.4%**.
- **We do not waste the once-per-turn resources.** `tools/turn_audit.py` over full games:
  **wasted_attach 3.6%**, **wasted_bench 3.0%**, **retreat-then-no-attack 0.6%** of turns.
- **The attacks that skip an attach are correct.** All **24** real positions where the elite
  attached and we swung are **KO swings, 14 provably taking the opponent's last prizes**.

## New instruments (2026-08-09, all take `--src` for two-tree A/B)

| tool | what it answers |
|---|---|
| `tools/tempo_agreement.py` | agreement bucketed for energy/retreat/bench + confusion tables |
| `tools/attach_probe.py` | attach-target choice with the turn-ordering confound removed |
| `tools/turn_audit.py` | **whole-TURN** audit: resources left unspent at the turn-ending decision |
| `tools/first_turn_ab.py` | forced mirror A/B of a single binary once-per-game decision |
| `tools/ctx_fuzz.py` | which of the 49 `SelectContext`s real play reaches + adversarial rewriting of captured observations into the ones it does not |
| `tools/first_turn_field.py` | how the real ladder answers a pre-board decision, **split by archetype**, straight from the episode zip |

`turn_audit.py` is the first instrument that scores turns rather than single decisions — both
agreement harnesses are structurally blind to "ended the turn without spending the attachment".

**HAZARD:** the repo's `agent/deck.csv` is NOT the list we ship (it is a different archetype), so a
tool that defaults to it silently routes through the *generic* pilot and every number is garbage —
this produced a fake "35.9% of turns waste the bench" that evaporated on the right list.
`turn_audit.py` and `first_turn_ab.py` prefer the packed tree's own `agent/deck.csv` and **print the
deck path they used — check it.**
