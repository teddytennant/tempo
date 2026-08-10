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

### THE NOISE FLOOR IS ~150 POINTS — measured on two POLICY-IDENTICAL artifacts (2026-08-10)

v3 `55390639` and v4 `55392668` are **byte-identical in behaviour on the shipped Lucario path** (v4
only changes an `IS_FIRST` default the specialist already answers). Both are now evicted, so both
scores are frozen and final:

| ref | policy | frozen score |
|---|---|---|
| v3 `55390639` | identical to v4 | **648.4** |
| v4 `55392668` | identical to v3 | **493.5** |

**155 points apart on the same policy.** Corroborated by live refs read repeatedly the same night:
v7 `55394411` **491.5 → 663.7 → 523.1** inside 40 minutes; v6 `55393889` **543.1 → 495.7 → 520.0**.

**Rules that follow, and they supersede every live-A/B claim in this file:**
- **A live score cannot resolve a difference smaller than ~150 points.** Do not rank two of our own
  submissions on anything less. "Unresolved" is the correct answer, not "the higher one won".
- **Eviction freezes a transient.** An old "settled" number belonging to an inactive ref is where
  the random walk stopped, not where it converged.
- The live score is still decisive for **catastrophes**: an errored submission, or an archetype
  dying under the field (Crustle 775–795 → 449, a 330-point move).
- Ship decisions therefore come from the offline harnesses (`prize_agreement`, `card_use`,
  `turn_replay`), with the baseline **re-run in the same session** because they are not deterministic.

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

### ...BUT THE *VERIFIED* IN-TURN SEARCH IS DIFFERENT, AND IT WAS THROTTLED (2026-08-10)

The four refutations above all refute the same thing: a **heuristic-eval** search *replacing* the
scorer's ranking. `agent/lethal.py` is not that. It searches the engine's native forward model for a
sequence that wins the game **this turn**, and its leaf value is `state.result` — a proof, not an
estimate. So the "value function is weaker than the scorer's tempo knowledge" mechanism cannot apply
to it. It had never been measured, and two of its four throttles were wrong.

`tools/lethal_probe.py` (new) replays real ladder MAIN decisions under one-axis-at-a-time widenings.
Over 2,500 decisions:

| axis widened | proven wins / 2500 | vs shipped | p99 |
|---|---|---|---|
| shipped (prizes<=2, attack on menu, 600 nodes/0.25s, depth 10) | 86 | — | 140.6 ms |
| `PRIZE_GATE` 2 -> 3 | 108 | +23 | 140.7 ms |
| drop the attack-on-menu requirement | 113 | +28 | 139.5 ms |
| budget -> 4000 nodes / 1.0 s | 95 | +10 | 899.1 ms |
| depth 10 -> 18 | **84** | **-1** | 159.0 ms |
| all four | 148 | +63 | 1000.8 ms |

- **`PRIZE_GATE = 2` was arithmetically wrong.** One knockout is worth up to **3** prizes (a Mega
  ex), so 3 is the largest prize count from which a single KO ends the game. Now `3`.
- **Requiring an ATTACK already on the root menu defeated the point of searching** — the lines worth
  finding are the ones that attach/evolve/use an ability *first*. Now off
  (`lethal.REQUIRE_ATTACK_OPTION = False`, kept as a flag so the probe can A/B the axis).
- Neither is a soundness condition: a positive is an engine-declared terminal win either way, so
  both were only ever cost filters.
- **`_MAX_DEPTH` and the node/time budget are measured NON-binding. Do not tune them.**

**Falsification of the proofs** (they are taken under a determinized deck, so a lucky-draw line could
be a phantom): segmenting the corpus into real games by the turn counter, claims sit at a **median of
0 turns from the end of the game**; 87.1% within one turn for the widened gate vs 90.7% for the
shipped one. The widened claims land where games actually end.

### THE REAL LESSON: A PROOF IS NOT BY ITSELF A REASON TO OVERRIDE THE PRIOR (2026-08-10)

Widening the gates **alone** made the agent worse — `prize_agreement` on the 4,074 elite decisions
went all 53.73 -> 52.95, main 45.53 -> 44.27, attack-choice 36.42 -> 34.77, with robustness clean.
`tools/lethal_cost.py` (new) says why. For every newly-proved position it forks the game, plays **the
shipped agent's own move**, and re-runs the search:

- **63 of 69**: the scorer's move keeps the win provable — the verifier was overriding a strong prior
  on a turn that was **already won**. Pure churn.
- **6 of 69**: the scorer plays a card (`PLAY` x4, `ATTACH` x2) that makes the win **unprovable** —
  it develops the board on the turn it could have won. These are the only real saves.

So `scorer.best_options` now calls the verifier **after** it has produced its own answer and hands
that answer over; `lethal._keeps_the_win()` applies it in the fork and the verifier **stays silent if
a win is still provable**. Prior protection decided by a proof instead of `lookahead.py`'s arbitrary
`SWITCH_MARGIN = 900.0`. Ambiguity (no answer, illegal selection, engine error) counts as
do-not-defer, so the proof wins ties.

Shipped as v6 (`55393889`). Agreement v6 vs v4 on the same 4,074 decisions: **all 53.73 -> 54.52,
main 45.53 -> 46.80, attack-available 39.08 -> 40.83, attack-choice 36.42 -> 37.58**, swing-or-end
88.00 / setup / other unchanged; **elite-attacked 52.13 -> 49.18 and attack-choice+attacked
48.87 -> 45.11 fall** — the elite-attacked slices, where the turn-ordering confound bites, and where
by construction the scorer's line provably wins the same turn. Robustness vs the 153 field decks:
920 games / 140,106 decisions, CLEAN, worst cumulative game 12.1s of 600s.

**The narrow claim to carry forward:** the only search allowed to speak is one whose leaf value is a
proof, and it should speak only when it can prove the prior is wrong. Nothing here reopens search in
general.

### ...AND THE VERIFIER WAS BLIND BELOW THE MAIN MENU (fixed 2026-08-10, shipped v7)

`lethal_move` returned `None` on any context that was not `SelectContext.MAIN`. **Nothing about the
search requires a MAIN menu** — `search_begin` works from any agent observation with a
`search_begin_input` — so that was an assumption, never a requirement. The consequence: the moment
the scorer decided to PLAY a card, the engine's follow-up question (*which* card, *which* target,
*where* to attach) was answered with no check that the answer kept a proven win alive.

`tools/lethal_sub_cost.py` (new) over **3,607 real single-answer sub-selects**:

| | n |
|---|---|
| a win this turn is provable **from the sub-select itself** | 186 |
| the shipped answer **keeps** it (verifier must stay silent) | 174 |
| the shipped answer **throws it away** | **12** |

The 93.5% preservation rate replicates the MAIN-level finding exactly and is the reason the v6 prior
protection is load-bearing here too — without it this would be 186 gratuitous deviations.

**The 12 are corroborated from outside the proof.** The corpus is decisions from games the frontier
player *won*, and in those 12 positions the elite played **the verifier's answer 7 times and our
shipped answer once**. That is external validation the MAIN-level change never had.

Most fire in a specific, high-value shape: the opponent has **no benched Pokémon**, so a knockout of
their Active ends the game outright (`_win_plausible`'s second clause), and the sub-select that
picks the wrong card quietly gives that up. Latency p50 0.13 ms, p99 138 ms.

`lethal.ALLOW_SUB_SELECT = True`; `scorer.best_options` now calls the verifier when
`ctx == MAIN or (maxCount == 1 and n > 1)` — forced and multi-answer selects are skipped because
there is nothing to choose and a padded multi-select is not something a proof can reason about.

## THE DEFENSIVE MIRROR OF THE WIN SEARCH DOES NOT WORK — measured and rejected (2026-08-10)

The obvious next move after v6 is to flip the polarity: instead of proving *we* win this turn, prove
*they* win next turn, and pick a turn-ender that avoids it. That is the whole defensive half of prize
trading, and it is the one thing the "prize-trade is settled" section below never measured.
**It was built (`agent/threat.py`), measured (`tools/threat_probe.py`) and NOT wired in.** Both files
are kept so no future run pays to rediscover this.

Design, for the record: fork at the MAIN decision, apply the scorer's turn-ender, then AND/OR search
the opponent's turn — OR over their selections, AND over ours (promoting after a knockout), leaf
value `state.result`. Their hand and deck are placeholder basics, so inside the fork they can attach,
retreat, use in-play abilities and attack but cannot play a trainer or a gust: a strict *subset* of
their real options, so the model under-approximates and cannot invent a threat.

Over 2,500 real ladder MAIN decisions:

| | our move | **the elite's own move** |
|---|---|---|
| gate opened (they are within one KO of their last prize, or we have no bench) | 170 | 97 |
| the move **provably loses** | 30 (17.6% of gated) | **17 (17.5% of gated)** |
| a provably-safe alternative turn-ender exists | 4 | 1 |

**Three findings, and the third kills it.**

1. **The threats are real, not artifacts.** Re-run with the opponent forbidden to ATTACH inside the
   fork (`--no-opp-attach`, so they may use only energy already on their board): **identical numbers,
   30 and 17.** So no proof depends on the energy zone derived from the placeholder deck.
2. **It describes the position, not the move.** Judged on the *elite's own* move it fires at
   **17.5%** of gated decisions against **17.6%** for ours — statistically the same rate — in games
   the elite went on to **win**. Sequencing the corpus by turn shows why: the positives come in runs
   of consecutive decisions within one turn, and the run still proves losing after the elite's own
   development line and their own attack. The position is lost; the move is not the reason.
3. **There is nothing to do about it.** A provably-safe alternative exists in **4 of 2,500**
   decisions, and the elite played our alternative in **0** of them.

**The durable asymmetry — write this on the wall.** An *offensive* proof is actionable because we
execute it ourselves: "a win exists and your move loses it" names the move to play instead. A
*defensive* proof is about what the **opponent** will do, and proving they have a win does not
produce a move that stops them. Same engine, same leaf value, same discipline, opposite outcome.
**A proof is only worth searching for when we are the one who gets to act on it.**

### Verified-search instruments (2026-08-10, all take `--src`)

| tool | what it answers |
|---|---|
| `tools/lethal_probe.py` | how many game-winning lines each throttle on `lethal.py` hides, attributed per axis, + the falsification check that a claimed win coincides with the game ending |
| `tools/lethal_cost.py` | does the heuristic *keep* the win the search found? forks the game, plays the shipped agent's own move, re-searches |
| `tools/lethal_sub_cost.py` | the same question **below** the MAIN menu: is a win provable from a sub-select, and does the shipped sub-selection preserve it? |
| `tools/threat_probe.py` | the defensive mirror, with two falsifications built in: `--elite-move` judges the frontier player's own move instead of ours, `--no-opp-attach` strips the opponent's energy attachment |

**`--elite-move` is the reusable idea.** Any verifier that flags our decisions should be re-run on the
*elite's* decisions from games they won. If it flags theirs at the same rate, it is measuring the
position and not the policy, and it will not improve play no matter how sound the proof is.

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

### ⚠ THE HARNESS IS NOT DETERMINISTIC WHERE THE VERIFIER RUNS (measured 2026-08-10)

`prize_agreement` was assumed reproducible. It is not, and the error bar is bucket-specific. The
**same tree** (`luc_majkel_v6_src`) on the **same 4,074 records**, run twice:

| bucket | run 1 | run 2 | delta |
|---|---|---|---|
| all | 2222 (54.52%) | 2216 (54.39%) | −6 |
| **main** | **1184 (46.80%)** | **1179 (46.60%)** | **−5** |
| other | 1007 (67.04%) | 1007 (67.04%) | **0** |
| every other bucket | — | — | 0 |

The source is `lethal.py`: the verifier's fork draws from a determinized deck, so the engine's own
randomisation makes a proof appear or vanish across runs. `main` is where it ran in v6, and `other`
is where it did not — which is exactly the split observed.

**Practical rule: a MAIN-bucket delta under ±5 decisions (±0.2 points) is not attributable.** Larger
recorded deltas survive comfortably (v6−v4 was +32 decisions on main), but re-run the baseline in
the same session before believing a small one. Buckets the verifier does not touch are exact.

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

### ⚠ RE-OPENED 2026-08-10 — that section was measured on the WRONG UNIT and the WRONG GAMES

All three bullets above score single decisions, or score turns in **self-play**. Scoring whole turns
**against the frontier's own boards** says something different:

| per turn, 199 real frontier turns | elite | ours (v7) |
|---|---|---|
| attacked | 78.4% | 64.3% |
| **attached energy** | **79.9%** | **58.8%** |
| MAIN actions taken | 6.06 | 5.07 |
| elite swung and we did not | — | 14.6% of turns |

`turn_audit`'s "wasted_attach 3.6%" was measured in **self-play**, where our own bots never build
the boards that make an attach necessary. It does not describe play against the field.
**The 79.9%-vs-58.8% attachment gap is open and is the largest unexplained number on the board.**
It is not the attach *target* (89.8% de-confounded, above) — it is ending turns without attaching.

## THE TURN, NOT THE DECISION, IS THE RIGHT UNIT (2026-08-10)

`tools/turn_replay.py` forks the engine at a turn's **first** decision and drives our own deploy
entry point through the whole turn one `search_step` at a time until control passes to the opponent,
then compares the two turns as **action multisets canonicalised to card identity** (option indices
shift within a turn; card ids do not). Ordering is removed by construction, which is the confound
every other harness here carries.

- **Fidelity control, and it must be re-checked on any tree**: our agent answers the fork's first
  question identically to the live one **199/199**. `dataclasses.asdict` on a forked observation is a
  usable agent input; `search_begin_input` is None inside the fork, so `lethal.py` cannot run there
  (~1% of decisions).
- **The ordering confound is REAL AND LARGE**: identical-turn rate is 8.0% overall but **66.7% in
  the no-draw bucket** vs 3.3% where cards are drawn. Only the no-draw bucket is clean (the fork
  determinizes our deck), and only ~7% of turns qualify — raise `--n` a lot to read it.
- **Two gotchas that cost real time.** The corpus omits zero-valued option fields while `asdict`
  keeps them as `None`, so `opt.get(k, default)` silently yields `None` — use a helper that treats
  `None` as the default, or every descriptor comes out as `PLAY(None)`. And `--src` must be a
  Lucario **source tree**, never the repo root (see the deck.csv hazard below).

### `tools/card_use.py` — the ordering-immune half

Never forks: it asks our agent the identical question on the elite's own menu and scores every
option **offered / elite took / we took**. A row where we are near **zero** cannot be explained by
ordering (re-ordering a turn changes *when* you play a card, never whether you ever do); a row where
we are merely *lower* usually can. Over 4,000 real MAIN decisions on v7:

| option | offered | elite | ours |
|---|---|---|---|
| **PLAY(Premium Power Pro)** | 1618 | 15.8% | **0.2%** ← the only ordering-immune row |
| PLAY(Poké Pad) | 603 | 47.8% | 23.5% |
| PLAY(Dusk Ball) | 581 | 51.8% | 29.8% |
| ABILITY(Lunatone / Lunar Cycle) | 502 | 72.3% | 48.6% |
| EVOLVE(Mega Lucario ex) | 448 | 44.0% | 96.7% |
| EVOLVE(Hariyama) | 663 | 13.1% | 77.4% |

The last two rows are what the ordering confound *looks like* (we evolve early, they evolve late) —
do not chase them without the turn-level fork.

### The fix this produced: Premium Power Pro (shipped v8, `55395183`)

`lucario_rules` gated the +30 {F} damage buff on it **exactly** converting a swing into a KO with the
Active in the Lucario line, `-1.0` otherwise. That guard is satisfied on **83 of 2,552** frontier
offers. `tools/ppp_probe.py` derives the frontier's real rule from its own 2,552 offers:

| bucket | offers | frontier played it |
|---|---|---|
| attack on menu, +30 converts a KO | 136 | 41.9% |
| attack on menu, does not convert | 386 | 29.0% |
| attack on menu, already lethal | 963 | 23.7% |
| **no attack on menu** | 1067 | **3.3%** |
| Lucario line / Solrock / Hariyama active | 1281 / 675 / 185 | 19.8 / 18.2 / 17.8% |

**"Is an ATTACK on the menu" is the whole rule**; the KO conversion is a ~1.4x tie-break and the
Lucario-line restriction was unjustified (Solrock and Hariyama are {F} too). Shipped: 700 when the
+30 converts, else 500 — both above every non-game-winning ATTACK (max ~450) and **below every
setup/search card**, so the buff is the last thing before the swing.
**A placement at 1520 was measured and REJECTED**: it overshoots (25.8% vs 15.8%) and displaces the
search items (Poké Pad 23.5 → 17.6, Dusk Ball 29.8 → 22.2). Raw agreement v7 46.27 / 1520-variant
46.52 / **shipped 46.67**. Also skipped in wall mode with an ex active, where offered attacks score
below END so "an attack is on the menu" does not mean we swing.

`prize_agreement` v8 vs v7 (v7 run **twice** first — spread 0–3 decisions): all 2223 → **2235**,
main 1183/1180 → **1191**, elite-declined-attack 551/548 → **578**, elite-attacked 150 → **130**,
attack-choice and swing-or-end **unchanged**. Same turn-ordering signature as v6.

## ⚠ THE `agent/deck.csv` FOOTGUN BIT AGAIN — and it fabricates plausible results (2026-08-10)

The repo's `agent/deck.csv` is a **Great Tusk** list, not what we ship. Running the new instruments
with `--src .` routed to the *generic* pilot and returned a completely coherent story: we "never"
fire Lunatone's Lunar Cycle, we attach energy on 30% of turns to the frontier's 83%, we play Great
Tusk 26 times. All of it fiction.

**The tell**: `PLAY(Great Tusk)` in a *Lucario* corpus. A card resolved out of the observation's own
hand cannot be a card that observation's player does not hold — so that single row proved the pilot
was mis-routed before any number was worth reading. **Always pass a real source tree**
(`experiments/luc_majkel_v*_src`), and read the deck path every instrument prints.

## New instruments (2026-08-09, all take `--src` for two-tree A/B)

| tool | what it answers |
|---|---|
| `tools/tempo_agreement.py` | agreement bucketed for energy/retreat/bench + confusion tables |
| `tools/attach_probe.py` | attach-target choice with the turn-ordering confound removed |
| `tools/turn_audit.py` | **whole-TURN** audit: resources left unspent at the turn-ending decision |
| `tools/first_turn_ab.py` | forced mirror A/B of a single binary once-per-game decision |
| `tools/ctx_fuzz.py` | which of the 49 `SelectContext`s real play reaches + adversarial rewriting of captured observations into the ones it does not |
| `tools/first_turn_field.py` | how the real ladder answers a pre-board decision, **split by archetype**, straight from the episode zip |
| `tools/turn_replay.py` (08-10) | **whole-turn** action multisets, ours vs the frontier's, with turn ordering removed by forking and playing the turn out |
| `tools/card_use.py` (08-10) | offered / elite-took / we-took per option on the **identical menu** — the ordering-immune half |
| `tools/ppp_probe.py` (08-10) | derives the frontier's rule for one card by bucketing its own offers; the template for "what is their actual condition?" |

`turn_audit.py` is the first instrument that scores turns rather than single decisions — both
agreement harnesses are structurally blind to "ended the turn without spending the attachment".

**HAZARD:** the repo's `agent/deck.csv` is NOT the list we ship (it is a different archetype), so a
tool that defaults to it silently routes through the *generic* pilot and every number is garbage —
this produced a fake "35.9% of turns waste the bench" that evaporated on the right list.
`turn_audit.py` and `first_turn_ab.py` prefer the packed tree's own `agent/deck.csv` and **print the
deck path they used — check it.**

## DECK CONSTRUCTION IS SETTLED — our list IS the frontier's list (2026-08-10)

**Do not spend another slot rebuilding or teching the decklist.** Five things close it.

1. **The frontier has not changed its list, and we already ship it byte-for-byte.** In the
   2026-08-09 dump **Majkel1337 (rank 1, LB 1203.5) played 23 of 26 games on a list identical to our
   `deck.csv`** (the other 3 on a Kangaskhan/Latias build he is testing). Three more field teams
   ship the identical 60 cards (Marshall_Maximizer, Oleksandr_Savsunenko, 李秉叡_ntumlnoob_); of the
   five Lucario teams only `seven` differs. Imitation has no headroom left.
2. **The deck is not what separates #1 from the field.** Those four teams pilot the *same 60 cards*
   at LB **1203.5 / 892.4 / 879.9 / unrated** — a **320-point spread on an identical list**.
3. **The band meta equals the global meta.** We are LB 654.4, **rank 2932 of 6679, dead median**, so
   matchmaking pairs us mid-ladder. The 550–700 band faces Grimmsnarl 29.1% / Fezandipiti-Alakazam
   22.0% / Lopunny-Froslass 11.9% vs a global 30.4 / 17.8 / 10.7. **No band-specific tech exists.**
4. **The list is fine against that field:** field-share-weighted **57.2%** over 83% of the 08-09
   field. Worst matchup Kangaskhan/Latias 22.5% is ~1% of what we face, and no field player runs a
   tech answer we could copy.
5. **The whole archetype-switch ceiling is ~+3.6 points** (see the de-confounded table below), against
   a documented 0/32 piloting failure on the deck that would earn it.

### Rating-controlled archetype strength — the confound is REAL BUT SMALL (`tools/deck_strength.py`)

The raw archetype win% is confounded by pilot quality, and the seat-banded table exaggerates it
(Grimmsnarl 41.9% at 850–1000 vs 50.7% at 1000+ — but banding the *seat* does not control who it
played; a low-band seat is largely playing up). Fit instead

    P(i beats j) = sigmoid( a·(r_i − r_j)/400 + d[arch_i] − d[arch_j] )

over 4,555 decided games with both pilots' public-LB ratings joined, CIs bootstrapped over **games**
(the two seats of one game are one observation). Rating term on the fresh dump **a = 0.352 (CI
0.212–0.489)** — a 400-point edge is worth 58.7%, so the join works.

**Result: mean |raw − deck-only| = 2.4 points, largest relative reshuffle 4.7. The raw table was
usable after all.** Deck-only win rates (2026-08-09):

| archetype | seats | raw | deck-only | 95% CI |
|---|---|---|---|---|
| Kangaskhan / Latias | 79 | 63.3 | 61.2 | 50.6–68.9 |
| Dragapult / Meowth | 633 | 59.4 | 57.4 | 53.7–60.9 |
| **Lucario / Hariyama** | 331 | 55.9 | **53.8** | 48.4–57.6 |
| Fezandipiti / Alakazam | 1617 | 49.9 | 47.3 | 44.6–50.3 |
| Marnie's Grimmsnarl | 2926 | 46.6 | 44.1 | 41.7–46.3 |
| **Kangaskhan / Crustle** | 332 | 38.9 | **37.3** | 32.4–43.0 |

**The June wall is now the worst deck in the field (37.3%)** — abandoning it was right.

### ⚠ A joined LB rating goes stale fast

Same model on the **08-08** dump joined to the 2026-08-10 LB gives a = 0.185 (CI 0.02–0.37), and the
higher-rated seat wins only 53.7% overall / **50.5% in the n=202 games with a 400+ point gap**. On
the one-day-fresher dump a = 0.352. The LB score reflects a team's *current* 2 active submissions,
not the agent that played a two-day-old episode. **Join ratings to the freshest dump available.**

### Prefix scanning — read a 21 GB dump in ~1 minute (`tools/frontier_deck_watch.py`)

A replay is ~6 MB, but `info.TeamNames`, `rewards` and both 60-card deck registrations all sit in
the first few hundred KB (key order is `configuration, description, id, info, …, rewards, …, steps`,
and the deck registrations are the first actions in `steps`). Reading **512 KB** per file and
regexing out those three things replaces a full JSON parse.
**Validated against the full parse on the 08-08 zip: 4,428 games and 238 LB-join drops, identical to
the byte** (3/4668 replays unusable, a 0.06% sampling loss). `deck_strength.py` uses it by default;
`--slow` restores the full parse.

### Deck/meta instruments (2026-08-10)

| tool | what it answers |
|---|---|
| `tools/frontier_deck_watch.py` | is the player whose list we copy still playing it? diffs their exact registrations against our `deck.csv` |
| `tools/deck_strength.py` | intrinsic archetype strength with pilot rating held fixed; also the fast extractor + `data/meta_aug/seats*.csv` cache |
| `tools/meta_bands.py` | the metagame split by rating band + the field-weighted deck-choice objective |

Fresh dumps: `kaggle datasets download -d kaggle/pokemon-tcg-ai-battle-episodes-YYYY-MM-DD`, published
~00:08 UTC for the previous day. Full LB with ratings:
`kaggle competitions leaderboard -c pokemon-tcg-ai-battle -d -p data/lb_now` (then unzip).

### `robust_probe` invocation gotchas (cost 2 failed runs on 2026-08-10)

- `--src` wants a **source tree** with `agent/` + `search/` (e.g. `experiments/luc_majkel_v4_src`),
  **not** the extracted tarball, whose `deck.csv` is at the root.
- `--opps` is a comma-separated list of deck **names** inside `--decks-dir`, defaulting to a curated
  11. For the real field: ``--opps "$(ls data/meta_aug/decks/*.csv | xargs -n1 basename | sed 's/\.csv$//' | paste -sd,)"``

## Daily cap resets at UTC midnight (confirmed 2026-08-10)

Two runs argued about this. Submitting at 00:40 UTC with 4 entries stamped the previous day
20:40–22:21 returned **"4 submissions remaining today"** — the previous day's entries do not count.
The CLI's remaining-count line is the only reliable read; the harness prompt's count can be stale.
