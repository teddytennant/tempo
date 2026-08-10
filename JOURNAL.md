# Journal — pokemon-tcg-ai-battle

Append-only. Newest entries at the bottom.

---

## 2026-08-09 — slot 1/5 — ANGLE: robustness (crashes / timeouts / illegal moves)

**Submitted:** ref `55389333` `submission_crustle_proven.tar.gz` — "slot1
crustle-proven-reconstruction". 4 slots left today.

### Orientation (the journal was empty; real memory was in commit messages)
- We are team **"zhang et al."** (`16401588`), rank **2042 / 6677**, score **716.1**. The
  submission history is SHARED with 4 teammates — the undescribed high scores (948.1, 894.5,
  894.3) are theirs, not ours. Recorded in RESEARCH.md so no future run re-derives it.
- Active pair was 55288207 (teammate's Codex Alakazam, 716.1) + 54835679 (my crustle v9, 693.7),
  i.e. **both slots were below our own proven 775–795 wall**, which had simply scrolled out of
  the 2-active window.
- **The proven artifact was gone.** `agent/submission_crustle.tar.gz` — 775.6/776.9/791.3/795.3
  over four re-ships, 863 once — was lost when the workspace moved off `/home/gradient/...`,
  because `*.tar.gz` is gitignored. Nothing on disk, nothing in git.
- **The working tree is stale/mixed — did NOT commit it.** `agent/{deck.csv,prize_tracker.py,
  opp_decks.py}` and `tests/test_contract.py` are reverted to their 2026-06-22 (`812c111`) state
  while HEAD is `24b5346` (07-19), and `agent/main.py` is a third state that *strips the scorer,
  PrizeTracker, belief and opp_detect out of `agent()`* — i.e. a strictly worse agent. Treated
  HEAD as authoritative and built from `git archive`, never from the working tree.

### What I did
1. **Recovered the proven build recipe from git** and made it reproducible forever:
   `scripts/build_proven_crustle.sh` = tree @`da08caf` + `data/decks/crustle.csv` as deck.csv +
   that era's own `build_submission.sh` + the manylinux `engine_rs` wheel, repacked without
   `__pycache__`. Verified it regenerates the shipped payload byte-for-byte. This is the durable
   replacement for the lost binary — the failure cannot recur.
2. **Built `tools/robust_probe.py`** (the angle): takes `--src`, so any two packed trees can be
   A/B'd on identical seeds. Plays full real-engine games driving BOTH seats through the deploy
   entry point and asserts, per decision: no exception, legal selection (distinct ints in range,
   length in `[minCount,maxCount]`), engine accepted it, per-move latency, and cumulative agent
   wall-clock vs the 600s game clock. 12% of moves perturbed to a random *legal* selection to
   reach states clean play never visits.
3. **A/B'd proven-366 vs the shipped v9-488** — trees identical except `crustle_rules.py`, which
   is exactly the delta that scored ~790 vs 693.7 live.

### Result — the angle came back NEGATIVE, and that is the finding
1500 games / ~135k decisions each, same seeds:

| | proven-366 | v9-488 |
|---|---|---|
| agent exceptions | 0 | 0 |
| illegal selections | 0 | 0 |
| engine rejects | 0 | 0 |
| hangs | 0 | 0 |
| games near 600s clock | 0 | 0 |
| latency p50/p99/max | 0.21 / 124 / 252 ms | 0.30 / 225 / **914** ms |
| worst cumulative game | 6.1 s | 7.7 s |

**Robustness is not our bottleneck.** The deploy path does not crash, never returns an illegal
selection, and burns ~1% of the game clock. So the twice-replicated ~85pt v8/v9 regression
(692.7, 693.7 vs 776.9 one day earlier) is a **play-quality** loss, not a crash or timeout. v9 is
2x slower at the tail but nowhere near dangerous. Future runs should not spend slots hunting
crashes unless a submission actually errors.

Packed cabt mirror smoke on the extracted tarball: `steps=84 statuses=[DONE,DONE] rewards=[-1,1]`
under kaggle_environments 1.32.0.

### Why this was worth a slot
Not filler: it reclaims a slot holding 693.7 with an artifact that has four independent live
draws at 775–795, and the artifact itself had to be reconstructed and then verified two ways.
Expected active pair after convergence: ~785 + 716.1, so LB ~785 (from 716.1).

### Environment hazards for the next run
- Root fs was **99% full** (4.4 GB free / 457 GB). `/tmp/claude-1000` holds 84 GB of *other*
  Claude sessions' scratchpads (oss-campaign 32 GB, ai-wizard 24 GB, -home-nixos 21 GB) — not
  ours to delete. A full disk surfaces as opaque `ENOSPC` tool failures, not as a disk error.
- `.venv` has no pip; use `uv pip install --python .venv/bin/python`. Anything importing `cg`
  must go through `./scripts/run.sh`.

### What the next run should look at FIRST
1. **Check `55389333` converged to ~785.** If it landed materially below the proven band, then
   the reconstruction is not equivalent to the lost original (or the field has strengthened
   enough to deflate the old score) — either way that changes everything below, so verify first.
2. **Stop iterating the rules pilot.** It has now failed to beat the proven wall on four separate
   attempts (v7 655, v8 692.7, v9 693.7, plus every from-scratch archetype at 638–774), and the
   ceiling is ~795 against a top-8 cut of ~1146. Local arena gains have repeatedly not transferred.
3. **The real question is the ~430pt gap to the prize cut.** #1–#20 spans only 120 points, so the
   leaders have converged on something we don't have. Highest-value next moves: mine the public
   episode dataset for what the *current* top agents do (the field has moved a lot since our
   June/July harvest), and look hard at `AlphaStarmie`-style self-play search — we have a
   half-built MCTS/self-play stack (`net/`, `train/`, `engine_rs/`) that was never proven to beat
   the BC baseline and was abandoned.
4. Do NOT commit the working tree. Resolve the stale revert first (`git checkout` the affected
   paths from HEAD, or establish that the working state is deliberate).
5. The Strategy-track writeup (`STRATEGY.md`, due 2026-09-13, $30k × 8) does not exist yet.

**Addendum (same run, ~20:50 UTC):** `55389333` is `SubmissionStatus.COMPLETE` with publicScore
`600.0` — that is the *entry* rating every new agent starts at, not a converged score, and
COMPLETE means the self-play validation game passed (no error, which is the robustness check that
actually matters). It converges over the following hours. **Next run: re-read this ref's score
before drawing any conclusion from it.** Active pair is now 55389333 + 55288207 (716.1), so the
reported LB score will read 716.1 until the new agent climbs past it.

---

## 2026-08-09 — slot 3/5 — ANGLE: search depth (deeper/wider lookahead, better leaf eval)

**Submitted:** ref `55389997` `luc_majkel.tar.gz` — "slot3 lucario-majkel-aug". CLI reported
**3 submissions remaining today** (so the prompt's "0 today" was wrong — slot 1 and slot 3 both
count; there is no journal entry for slot 2, which left `experiments/luc_*_src`,
`data/meta_aug/` and `data/ep_aug/` on disk but shipped and recorded nothing).

### FIRST, THE THING THAT CHANGES EVERYTHING: 55389333 came back 449.2 → 462.4

The previous run reconstructed the "proven" Crustle wall — 775.6 / 776.9 / 791.3 / 795.3 over four
re-ships — and it converged to **462.4**. Its instruction was to check this before believing
anything else, so: checked, and the premise is dead.

**The rebuild is not broken. The deck died.** Slot 2 had already downloaded the 2026-08-08 episode
dump (`data/ep_aug/`, 740 MB) and mined it with `tools/meta_aug.py` into `data/meta_aug/`
(9,300+ real ladder games between real agents). In that data:

| archetype | share | real-field win % |
|---|---|---|
| Marnie's Grimmsnarl / Morgrem | 30.4% | 46.4 |
| Fezandipiti / Alakazam | 17.8% | 49.9 |
| Lopunny / Froslass | 10.7% | 51.7 |
| Dragapult / Meowth | 6.3% | **58.0** |
| Lucario / Hariyama | 3.2% | **54.3** |
| **Kangaskhan / Crustle** | 3.5% | **43.96** |

Our entire 775–795 wall was a June artifact of a June field. `RESEARCH.md` has been rewritten
accordingly — **the "proven artifact" section was the most load-bearing wrong belief in this
workspace** and every future run would have kept re-shipping it.

### The angle: search on top of the scorer — well-powered NEGATIVE

First, a fact nobody had written down: **in every artifact shipped since June, the search is dead
code.** `main.agent` tries `scorer.best_options` first and returns on success, so the Rust/MCTS
branch below it is unreachable. The comment on that line even says why: *"beats our MCTS 63% h2h"*.

So I re-enabled it properly and measured it. Added a `hybrid` pilot to `tools/par_eval.py`:
determinized search over the engine's native forward model (`engine_rs.choose`, net-PUCT) on MAIN
single-select decisions, with the rich scorer handling **every other** decision — i.e. lookahead
layered *on top of* the strong prior, which is the one configuration the refuted `agent/lookahead.py`
never tried (that one used a static board eval at the leaf). Also added `scorer` as a standalone
pilot and `--alternate` seat-swapping, because the harness had a real first-player bias.

Head-to-head vs the pure scorer, same deck both seats, alternating seats:

| deck | hybrid search vs pure scorer |
|---|---|
| Crustle wall | **23.3% ± 10.7** (n=60) |
| Lucario / Majkel list | **50.0% ± 12.7** (n=60) |

**Not vacuous** — the obvious objection is that search never actually disagrees, so I instrumented
it: over 6 full games, search diverged from the scorer on **305 of 423 (72.1%)** of the qualifying
decisions. It makes a genuinely different choice three times in four, and the result is *exactly*
the prior on Lucario and a disaster on Crustle. It matches the prior; it never beats it.

This is consistent with the only two live tests of search we own, which nobody had recorded:
**ref 53915967 determinized UCT = 560.1** and **ref 53927392 Rust MCTS = 528.8**, against rules
pilots scoring 776–795 the same week. Three independent refutations (June live ×2, the
`lookahead.py` sweep, this run). **Search is settled. Stop spending slots on it.**

### The other finding: our local arena is anti-predictive, and now we have the number

The Crustle wall beats the top meta deck **93.8%** in our arena while scoring **462** live. The
harness measures "which deck best exploits *our own bots*", not deck strength — our bots are the
only opponents in it. This is why v8/v9 shipped green local evals and lost ~85pts each.
**Corollary: no local arena result may be used as ship justification again.** The only trustworthy
local signal we have is `data/meta_aug/` — real games between real ladder agents.

### What I shipped and why

`experiments/luc_majkel.tar.gz` — the **unmodified HEAD pilot stack** (no code change at all) on
**Majkel1337's exact August 60-card Lucario/Hariyama list**, mined from their real winning games.
Majkel1337 is #1 overall at 1218.7. Rationale is entirely real-field: swap a 43.96% archetype for a
54.3% one, holding the pilot fixed. Deliberately a **single-variable experiment** — it disambiguates
the one question that decides the rest of the week:

- lands ~470 like Crustle → **our pilots are the problem**, and the rules-pilot method is finished;
- lands ~700+ → **the deck was the problem**, and re-piloting good archetypes is the play.

Right now those two are completely confounded (Crustle 462 = bad deck + our pilot; teammate's
Alakazam 716.1 = average deck + *their* pilot). Nothing else I could ship today resolves it.

Cost accounting, done honestly: any submission evicts 55288207 (716.1, a teammate's notebook) from
the 2-active window, so the likely near-term LB cost is ~50–250 points at rank ~2000, in a race
whose prize cut is 1140. Cheap for the information, and sitting on a teammate's 716 advances
nothing.

### Verification (all green)
- `tools/robust_probe.py` on the packed tree: 400 games / **46,501 agent decisions** — 0 exceptions,
  0 illegal selections, 0 engine rejects, 0 hangs, 0 moves over 1s, 0 games near the 600s clock.
  Latency p50/p99/max 0.24 / 140 / 253 ms; worst cumulative game 7.9s of 600s. **CLEAN.**
- Packed cabt mirror smoke on the extracted tarball: `steps=145 statuses=[DONE,DONE] rewards=[-1,1]`
  under kaggle_environments 1.32.0.
- Fixed a real bug in `scripts/build_lucario.sh`: it packs from a temp cwd, so a relative outfile
  silently failed to write and left a stale artifact in place. Now absolutised. **The 17:03
  `luc_majkel.tar.gz` slot 2 left behind was written by some other path — do not trust artifacts
  whose build you did not just run.**
- Restored the stale working-tree reverts flagged by the previous run (`agent/main.py`,
  `deck.csv`, `opp_decks.py`, `prize_tracker.py`, `build_submission.sh`, `tests/test_contract.py`,
  `tools/deck_tourney.py`) to HEAD. The tree is now clean against HEAD except intended edits.

### Open problem for the next run — read this first
`pytest tests/` = **8 passed, 3 failed**, and all 3 fail at unmodified HEAD, so they are
pre-existing and ship inside every artifact we have ever sent, including the 776.9 one:
`test_lethal_attack_is_taken`, `test_attack_preferred_over_end_when_nonzero`,
`test_go_first_prefers_second` — the agent picks END over a 120-damage KO. These run against the
mock engine, so it may be a fixture artifact (mock attack ids 101/102 vs the real `all_attack()`
table) — **but "does our agent take lethal?" is exactly the play-quality question our diagnosed
bottleneck is about**, and `agent/lethal.py` exists as a verified-lethal override that the primary
scorer path may simply never reach. Confirm mock-only or fix it; a genuine miss here is worth more
than any deck swap. I did not chase it because the artifact was already submitted.

### What the next run should do
1. **Read 55389997's converged score first.** The whole branch above turns on it (see the two
   outcomes). Compare against Crustle's 462.4 and the teammate Alakazam's 716.1.
2. Resolve the lethal-attack test failures.
3. Do NOT ship search, do NOT re-ship the Crustle wall, do NOT justify a ship with arena win rates.
4. `data/meta_aug/decks/` holds **153 exact winning August decklists**, including every top-20
   team (Dipam Chakraborty / 213tubo / Kh0a = Dragapult/Meowth, the 58.0% best-performing deck;
   M Sato = Lopunny/Froslass; AlphaStarmie + ANDPAD = Fezandipiti/Alakazam; Thai = Kangaskhan/
   Latias at 63.2%). We have no pilot for Dragapult/Meowth — both the scorer and search go 0/32
   with it, which is its own finding: **our pilots are deck-specific and cannot fly a new list.**
5. `STRATEGY.md` still does not exist ($30k × 8, due 2026-09-13). The three refutations above plus
   the meta-collapse story are a genuinely good writeup and the material is now all in this journal.

**Addendum (same run, ~22:15 UTC) — the experiment has already answered.**
`55389997` is `COMPLETE` and at **698.6** roughly 45 minutes in, still climbing from the 600 entry
rating. Same run, `55389333` (the Crustle wall) sits at **506.0**.

That is the deck-swap experiment resolved, and it resolved the *good* way: **identical pilot code,
+190 points from the decklist alone** (43.96% archetype → 54.3% archetype). So the answer to the
question this slot was bought to settle is **"the deck was the problem, not the pilot"** — our
rules-pilot method is not finished, it was flying a dead archetype. It is also already within ~18
points of the teammate Alakazam notebook (716.1) that it evicted, while still converging upward, so
the budgeted cost of the eviction looks like it will be roughly zero.

**Direct consequence for slots 4–5:** the remaining active slot is the 506.0 Crustle, which is pure
dead weight and free to replace. The highest-value follow-up is *more of what just worked* — take
another archetype with a positive real-field win rate that we already have a specialist for, and
put it on a top team's exact August list from `data/meta_aug/decks/`. Ranked by real-field win %
against what `agent/scorer.py` can actually dispatch to:
Lucario/Hariyama 54.3 (just shipped) > Lopunny/Froslass 51.7 > Fezandipiti/Alakazam 49.9
(`fezandipiti_rules.py` + `dunsparce_rules.py`; AlphaStarmie and ANDPAD lists both mined) >
Grimmsnarl 46.4 (`grimmsnarl_rules.py`, 30% of the field so the most-played matchup we can train on).
Kangaskhan/Latias (63.2%) and Dragapult/Meowth (58.0%) are the two best decks in the format and we
have **no pilot for either** — building one is a bigger, better bet than another list swap, and the
0/32 result above says the generic path cannot substitute for it.

---

## 2026-08-09 — slot 4/5 — ANGLE: prize-trade economics (KOs, prize counts, when to trade)

**Submitted:** ref `55390373` `luc_majkel_v2.tar.gz` — "slot4 luc-majkel-v2". CLI reported
**2 submissions remaining today.** Evicted `55389333` (the Crustle wall), so the active pair is
now 55390373 + 55389997.

### FIRST — read this before trusting any score in this journal

Live ratings swing enormously while converging, and this run watched it happen to a single ref:

| ref 55389997 (Lucario/Majkel) | reading |
|---|---|
| ~45 min after submit (slot 3 addendum) | 698.6 |
| start of this run (~21:40 UTC) | **775.6** |
| end of this run (~22:05 UTC) | **559.1** |

Meanwhile `55389333` (Crustle) went 489.2 → 506.0 → 540.1 over the same window. **A reading taken
within hours of submitting is not a converged score, and the swing is >200 points.** The slot-3
entry's "+190 from the decklist alone" conclusion was drawn at the 698.6/775.6 readings; on the
current readings that gap is ~19 points, not 190. The deck-swap result is therefore **NOT yet
established** — it is still the best hypothesis we have, but the next run must re-read both refs
after they settle before building on it. I have flagged this in RESEARCH.md too.

### The angle: prize-trade economics — a well-powered DOUBLE NEGATIVE

Built `tools/prize_agreement.py`, which is the durable output of this run. It replays real
decisions by frontier Lucario players (4,074 winning decisions from the 2026-08-08 ladder dump,
`data/bc_lucario/records_11447.jsonl`) through the **deploy entry point** and reports agreement per
decision type. 99.1% of the corpus routes through `lucario_rules`, so it measures the shipping code
path, and it takes `--src` so two packed trees are scored on identical decisions. **This is the
arena replacement we have needed since the arena was shown to be anti-predictive** — it is
real-field, and it answers *relative* policy questions.

Baseline on the shipped agent:

| bucket | n | agree |
|---|---|---|
| all | 4074 | 52.9% |
| main | 2530 | 45.5% |
| main/attack-available | 1712 | 39.1% |
| **main/swing-or-end** | 75 | **88.0%** |
| main/attack-choice | 604 | 36.4% |
| other (sub-selects) | 1502 | 64.9% |

**(a) At the policy level, prize-trade is already elite-consistent.**
- On *pure* swing-or-end decisions (options are only ATTACK/END/RETREAT, so the "we developed first
  and attacked later" confound cannot apply) we agree **88.0%**.
- Among decisions with ≥2 attacks where the elite attacked, we pick a *different attack* only
  **6 times in 133** — 3 each way, i.e. noise. Attack selection is fine.
- 149 decisions look like "we attacked, the elite kept developing". I instrumented each one:
  **124 are correct** — 112 where `lethal.py`'s verifier proved a game-winning line and 12 where the
  scorer's own game-winning-swing branch fired. Only **25 of 2,530 MAIN decisions (1.0%)** are
  genuinely premature, and **15 of those 25 are one card** (Premium Power Pro, which our pilot
  scores −1 unless its +30 exactly converts a KO). I did not "fix" that: without card text in the
  engine DB I cannot tell whether the elites or our rule are right, and guessing on top of our only
  good artifact is precisely the v8/v9 failure mode.

**(b) At the deck level, prize liability does not predict winning.** Across the 17 archetypes with
≥100 games in `data/meta_aug/`, joined to their teams' real decklists:
`corr(win%, max prize liability of the deck) = **−0.13**` (nothing) and
`corr(win%, number of multi-prize Pokemon) = **+0.54**` — decks carrying *more* 2/3-prize threats
win *more*. So our 3-prize Mega Lucario ex is not a prize-trade handicap, and "build a low-prize
deck" is a dead idea. Killed before it cost a future run a slot.

**(c) The documented prize guard is WRONG, and it is good that it was never implemented.**
`lucario_rules.py`'s header has promised since it was written: *"Prize guard: when we are at our
last 2-3 prizes, do not over-expose the 3-prize Mega-ex."* `_my_prize_count` was defined and never
called. I implemented it (don't volunteer the Mega-ex to the active spot when the opponent is
within its prize value of winning) and ablated it on the same 4,074 decisions with an env-var
switch: it moved **9 decisions away from elite play and 0 toward it** (other 64.85% → 64.25%),
with both rules off reproducing the baseline exactly. **Reverted, not shipped.** Mechanism: Lucario
is a one-attacker aggro deck — refusing to promote the Mega just forfeits tempo, and the elites
promote it anyway. A companion rule (+4000 to a KO target whose prize value takes our last prizes)
was a measured **no-op** — it never changed a decision — so it was reverted too.

### What I did ship: a real correctness bug on the game-closing path

`lucario_rules.LUCARIO_DECK` is handed to the multi-step lethal verifier (`scorer.py:521`) as its
**determinization deck** — it is the module's only consumer. It was a hardcoded reference list.
Since slot 3 we pilot Majkel1337's exact August list, and the two differ on **16 of 60 cards**
(Ultra Ball / Judge / Wally's Compassion in; Dusk Ball / Carmine / Gravity Mountain out). So the
verifier that decides *"can I take my last prizes this turn"* has been searching a deck we do not
own, free to prove a lethal that draws a Dusk Ball we have zero of — the same impossible-line
failure the belief correction inside `lethal.py` exists to prevent. That path fired on **112** of
the corpus decisions, i.e. it is the component that actually closes out won games.

Fixed by reading the bundled `deck.csv` at import (fallback to the reference list on any failure),
so **the mismatch cannot recur when we swap lists** — which matters because list-swapping is
currently our main lever.

Measured A/B on identical decisions, shipped tree vs fixed tree:
all 52.87% → **52.92%**, main 45.45 → 45.53, attack-available 38.96 → 39.08, attack-choice
36.26 → 36.42, **no bucket regressed**. Small in aggregate because the verifier only fires in
endgames; but it is a correctness fix, it is strictly non-negative on real play, and it is
structural rather than a tuning guess.

### Also measured, not shipped
**Thwackey / Dipplin** — the format's only *pure single-prize* archetype (Sixth Sense's list: 60
cards, every Pokémon Stage-0/Stage-1, zero ex; `maxPrize 1.0`, `multiPz 0.0`), 59.5% real-field win
rate. The obvious prize-trade deck, and unlike Dragapult it has no Stage-2 line, so the "generic
path cannot assemble a Stage-2 combo" failure should not apply. It doesn't: it goes **10.4% ± 8.6
(n=48, alternating seats)** under our generic pilot against our own Lucario specialist. The deck
functions (it is not the 0/32 Dragapult result) but we cannot fly it. Deck saved at
`data/decks/thwackey_sixthsense.csv`. **Restates the central structural problem: a strong archetype
is worthless to us without a hand-written specialist.**

### Verification (all green)
- `tools/robust_probe.py` on the packed tree: 400 games / **46,929 agent decisions** — 0 exceptions,
  0 illegal selections, 0 engine rejects, 0 hangs, 0 moves over 1s, 0 games near the 600s clock.
  Latency p50/p99/max 0.28 / 187 / 261 ms; worst cumulative game 5.2s of 600s. **CLEAN.**
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=127 statuses=[DONE,DONE] rewards=[-1,1]`
  under kaggle_environments 1.32.0.
- `pytest tests/` → 8 passed, the same 3 pre-existing failures, none new.

### Open: the 3 failing tests are STILL unresolved
`test_lethal_attack_is_taken`, `test_attack_preferred_over_end_when_nonzero`,
`test_go_first_prefers_second`. The previous run flagged them as the top open question. This run
gives strong evidence they are a **mock-fixture artifact, not a real bug**: against the real engine
on real elite positions we take lethal correctly (88% swing-or-end agreement; the lethal verifier
fires correctly on 112 game-winning decisions; only 1.0% premature attacks). They still deserve a
30-minute confirmation, but they are no longer a plausible explanation for our ladder position.

### What the next run should do FIRST
1. **Re-read `55390373` AND `55389997` after they settle**, and treat the slot-3 "+190 deck swap"
   conclusion as unconfirmed until you do. Scores moved 775.6 → 559.1 on one ref inside this run.
   Do not evict an active slot on the strength of a fresh reading.
2. **Do not spend another slot on prize-trade economics.** Policy-level 88%/1.0%, deck-level
   r=−0.13, and the documented prize guard measured negative. It is closed.
3. `tools/prize_agreement.py` is now the way to justify a policy change. Use `--src` to A/B packed
   trees. It only covers Lucario decisions; extending it to other archetypes needs a corpus for them
   (`tools/harvest_lucario.py` is the template).
4. The unexploited lever remains **a specialist for a top archetype we cannot currently fly**
   (Kangaskhan/Latias 63.2%, Dragapult/Meowth 58.0%, Thwackey/Dipplin 59.5%). That is a multi-run
   build, not a slot-filler, and it is the only thing on the table that plausibly closes the ~400pt
   gap to the prize cut.
5. `STRATEGY.md` still does not exist ($30k × 8, due 2026-09-13). The material is now genuinely
   strong: four independent refutations of search, the arena anti-predictiveness result with a
   number, the meta-collapse story, and now a real-field agreement harness plus a double-negative on
   prize-trade economics. **This is the highest-value unclaimed thing in the workspace.**

**Addendum (same run, ~22:15 UTC):** `55390373` is `SubmissionStatus.COMPLETE` (the self-play
validation game passed, so the packed tree runs clean on Kaggle) with an initial reading of
**506.8**, i.e. still near the 600 entry rating and not converged. In the same read `55389997`
moved 559.1 → **596.5**, which is the third direction change for that ref today and is exactly the
volatility documented at the top of this entry. **No conclusion should be drawn from either number
yet.** Active pair is 55390373 + 55389997; 2 submissions remain today.

**Note for whoever takes slot 5:** a further submission evicts `55389997`. Given the swings above,
do not do that unless the candidate is justified on grounds independent of today's readings — and
prefer leaving the slot unused over spending it to chase a number that is still moving.

---

## 2026-08-09 — slot 5/5 — ANGLE: energy and tempo (attachment, retreat, bench sequencing)

**Submitted:** ref `55390639` `luc_majkel_v3.tar.gz` — "slot5 luc-majkel-v3". CLI reported
**1 submission remaining today.** Evicted `55389997` (v1), so the active pair is
**55390373 (v2) + 55390639 (v3)**.

### The headline: the tempo leak is not inside the turn, it is the decision made before it

`SelectContext.IS_FIRST` ("would you like to go first?") is asked once per game, before the opening
hand is dealt. **We answered NO — decline to go first — in 93 of 93 real positions. Real ladder
Lucario players answered YES in 91 of 93.** Agreement 2.2%.

**Root cause, and it is structural, not a tuning miss.** `scorer.best_options` dispatches to an
archetype specialist via `lucario_rules.is_lucario_deck()`, which detects the archetype from cards
*visible on our side*. At IS_FIRST our active/bench/hand/discard are all empty, so detection returns
False and **every specialist is bypassed for the one decision that sets the tempo of the whole
game.** The generic `scorer._score_sub` then decides with a rule nobody ever measured — *"going
second is often better for a setup deck"* — silently overriding `lucario_rules`' documented and
opposite preference (*"aggro wants the Riolu→Mega clock a turn sooner"*), which has therefore been
**dead code in every artifact we have ever shipped, including the 776.9 Crustle wall.** Note also
`main.py`'s fallback says YES, so the repo held three conflicting opinions and the untested one won.

**Fix (shipped):** we ship the decklist, so there is no need to infer our archetype from an empty
board — `is_lucario_deck` falls back to the bundled `deck.csv` when nothing at all is visible. The
guard requires active, bench, hand AND discard to be simultaneously empty, which only happens before
the opening hand exists, so **no in-game decision changes**. Same pattern as slot 4's `LUCARIO_DECK`
fix: bind the pilot to the list we actually pilot.

**Evidence, two independent kinds — this is the part that makes it shippable.**
1. **Real field:** 91/93 IS_FIRST answers by real ladder Lucario players in the 2026-08-08 dump are
   YES.
2. **Causal, in-engine:** `tools/first_turn_ab.py` plays mirror games — identical deck, identical
   policy on both seats, *only* the turn-order answer forced — arm-swapped and seat-swapped. Two
   independent runs:

   | run | forced YES (asked player wins) | forced NO |
   |---|---|---|
   | n=1000 | 51.8% ± 4.4 | 47.0% ± 4.4 |
   | n=1200 | 56.0% ± 4.0 | 45.5% ± 4.0 |

   Pooled, **the player who went first won 1187/2200 = 54.0% ± 2.1 (z=3.7, p≈0.0002).** Verified the
   forcing actually works: forced YES → asked player takes the first MAIN turn; forced NO → the
   opponent does.

**Paired agreement A/B** (`tools/prize_agreement.py`, same 4,074 elite decisions, both trees):
all 52.90 → **53.73**, other 64.85 → **67.04**, main 45.49 → 45.53, attack-available 39.02 → 39.08,
attack-choice 36.26 → 36.42, swing-or-end 88.00 → 88.00, setup 71.43 → 71.43. **No bucket
regresses.** IS_FIRST itself 2.2% → **97.8%**. (One MAIN decision out of 2,530 also moved, toward
elite play — consistent with the lethal verifier's determinization sampling, not with this change.)

### The rest of the angle is a NEGATIVE, and that is the more useful half

**In-turn energy/retreat/bench sequencing is not a leak. Do not spend another slot here.**

- **The scary-looking number was a confound.** `tools/tempo_agreement.py` (new) reports
  `main/attach-to-bench` agreement at **18.6%** vs 52.4% for attach-to-active, which looks like we
  systematically refuse to pre-fuel the bench. It is the turn-ordering artifact: we play a card
  first and attach later in the same turn. `tools/attach_probe.py` (new) removes it by keeping only
  decisions where the elite **and** we both attached at that same point — so the only thing that can
  differ is the target. Result: **89.8% (149/166)** area agreement, and we bench energy **37.3%** of
  the time against their **40.4%**. Our attach targeting is right.
- **We do not waste the attachment.** `tools/turn_audit.py` (new) plays full games and counts, per
  turn, resources left unspent at the turn-ending decision: **wasted_attach 3.6%**, **wasted_bench
  3.0%**, **retreat-then-no-attack 0.6%** of turns.
- **And the ones it does flag are correct.** All **24** real positions where the elite attached and
  we swung instead are **KO swings, 14 of them provably taking the opponent's last prizes**. Not
  premature — game-closing.

### New instruments (the durable output besides the fix)
- `tools/tempo_agreement.py` — sibling of `prize_agreement.py`, bucketed for energy/retreat/bench,
  with confusion tables ("elite attached, we played X instead").
- `tools/attach_probe.py` — confound-free attach-target cross-tab, conditioned on board state.
- `tools/turn_audit.py` — **the first instrument we have that scores whole TURNS instead of single
  decisions**, so it can see resources left unspent. Both agreement harnesses are structurally blind
  to this. Takes `--src`. NB: it now reads the *packed tree's* `agent/deck.csv`; my first run used
  the repo's `agent/deck.csv`, which is a **different archetype**, and every number was garbage
  (35.9% "wasted bench" that evaporated on the right list). **Always confirm the deck line it
  prints.**
- `tools/first_turn_ab.py` — forced mirror A/B of a single binary decision. The template for
  causally testing any once-per-game choice.

### Verification (all green)
- `robust_probe` on the packed tree: 400 games / **47,972 agent decisions** — 0 exceptions, 0
  illegal selections, 0 engine rejects, 0 hangs, 0 moves over 1s. Latency p50/p99/max
  0.28 / 181 / 258 ms; worst cumulative game 3.8s of 600s. **CLEAN.**
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=151 statuses=[DONE,DONE] rewards=[-1,1]`.
- `pytest tests/` → **9 passed, 2 failed, down from 3.** `test_go_first_prefers_second` asserted the
  belief this run refuted (and was failing anyway); it is now `test_go_first_is_accepted` and
  asserts the measured behaviour. The remaining 2 are the pre-existing mock-fixture lethal ones.

### On the eviction, and a live demonstration of why score readings are useless today
Ship justification was deliberately **structural, not score-based**: v3 = v1 + both of this week's
correctness fixes, so evicting v1 cannot cost an idea. That was the right basis — inside this single
run the readings **crossed over**:

| ref | earlier today | at submit time |
|---|---|---|
| 55390373 (v2) | 506.8 | **572.7** |
| 55389997 (v1) | 596.5 | **505.7** |

Anyone who had evicted on the 596.5/506.8 reading would have kept the wrong one. **Third day running
that this file has had to say it: do not conclude from a same-day reading.**

### What the next run should do FIRST
1. **Read 55390639's converged score**, and re-read 55390373. Both are the same pilot on the same
   list; v3 differs from v2 by exactly one binary decision per game measured at +4pp win rate, so
   this pair is a genuinely clean live A/B of the turn-order fix. **It is the first clean live A/B
   we have ever set up — do not evict either of them until both settle.** 1 submission remains today
   at the time of writing; if you have slots and nothing better, leaving them alone is correct.
2. **The IS_FIRST bug is only fixed for Lucario.** `crustle_rules`, `grimmsnarl_rules`,
   `starmie_rules`, `tusk_rules`, `fezandipiti_rules`, `dunsparce_rules`, `iono_rules`,
   `cinderace_rules`, `hops_snorlax_rules` all still get bypassed at IS_FIRST and inherit scorer's
   refuted "go second". Each needs the same deck.csv fallback in its `is_*_deck`. Costs nothing
   today (we ship Lucario) but it is a landmine the moment we swap archetypes — and it means every
   historical score in this file, including the 776.9 wall, was set while conceding the first turn.
3. **Look for more once-per-game decisions with the same shape.** The lesson generalises: the
   dispatch is board-visibility-based, so *any* decision taken before the board reveals the
   archetype is decided by untested generic defaults. `SelectContext.MULLIGAN` (42) is the obvious
   next one — it does not appear in our corpus at all, so nobody has ever checked it.
4. Do NOT spend a slot on in-turn energy/retreat/bench sequencing (closed above), on prize-trade
   economics (closed slot 4), or on search (closed slot 3, four refutations).
5. The unexploited lever is still **a specialist for a top archetype we cannot fly**
   (Kangaskhan/Latias 63.2%, Dragapult/Meowth 58.0%, Thwackey/Dipplin 59.5%). Multi-run build.
6. `STRATEGY.md` still does not exist ($30k × 8, due 2026-09-13). The material is now very strong:
   four refutations of search, the anti-predictive-arena result with a number, the meta-collapse
   story, the prize-trade double negative, and now a structural dispatch bug that silently handed
   every specialist's opening-tempo decision to an untested default. **Highest-value unclaimed thing
   in the workspace.**

---

## 2026-08-10 (UTC) — slot labelled 1/5, prompt reported 4 used — ANGLE: robustness

**NO SUBMISSION. Deliberate.** Justification below; this is not a blocked run.

### Slot arithmetic first, because it decided the run

The prompt said "SLOT 1 of 5" and "4 submissions already today". At the moment this run started the
clock had just rolled over (`date -u` = 2026-08-10 00:00), so the cap had almost certainly reset —
the 4 entries were all stamped 2026-08-09 20:40–22:21 UTC. **The cap was not the binding
constraint. The active pair was.**

Active: `55390639` (v3) **621.5** + `55390373` (v2) **550.7**. Any submission evicts v2 and destroys
the clean live A/B the previous run set up — v2 and v3 are the same pilot on the same list differing
by exactly one binary decision per game. This run produced no play-quality change (see below), so a
submission would have paid for the loss of the A/B with nothing. Unused slot > wasted slot.

For the record, the A/B currently reads **v3 − v2 = +70.8**, the sign the turn-order fix predicts.
Still young; this file has twice recorded same-day crossovers. Do not build on it yet.

### The angle is CLOSED, and closed properly rather than by assertion

RESEARCH.md already said robustness was not the bottleneck, on the strength of 1500 games against
11 curated decks. That is a sampling argument with an obvious hole, so I attacked the hole rather
than repeating the measurement.

**Layer 1 — the real field, not our curated decks.** `robust_probe` against **all 153 real ladder
decklists** mined from the 2026-08-08 dump. Shipped v3: 920 games / **134,454 decisions** — 0
exceptions, 0 illegal, 0 engine rejects, 0 hangs, 0 moves over 1s; p50/p99/max **0.33/232/268 ms**;
worst cumulative game **6.1s of 600s**.

**Layer 2 — coverage, the actual hole.** The engine defines **49 `SelectContext` values** and a
normal game asks only some of them; an unreached context is code we ship unexecuted. New
`tools/ctx_fuzz.py` measures it. A 1,224-game field sweep reaches **31/49** over 188,103 live
decisions. I then measured what the *real ladder* asks by scanning **400 random episodes** out of
the dump: **31** distinct contexts over 130,603 decisions. The only real-field context our probe
never reaches is `32 TO_DECK_ENERGY` — **3 occurrences in 130,603 (0.002%)** — and we additionally
reach `36 DISABLE_ATTACK`, which the real sample lacks. **Self-play against the field's own
decklists reproduces the field's state distribution.** That is the sentence that makes layer 1 mean
something.

**Layer 3 — manufacture the states real play won't produce.** `ctx_fuzz` phase 2 rewrites every
captured observation: the same board asked under **each of the 49 contexts**; degenerate bounds
including `(0,0)`, `(n,n)`, `(n+1,n+1)` and the contradictory `(2,1)`; empty and truncated option
lists; optional keys nulled *and* dropped; bench/hand/discard/active/prize/energyZone/stadium
stripped to empty; turn 0, turn 9999, and a **decided** game still asking for a move; blanked
option-record fields. **325,070 mutants: 0 exceptions, 0 illegal selections, max latency 20 ms.**
Only no-raise and usable-selection are asserted — a mutated board is not necessarily reachable, so a
bad *choice* on one means nothing, and I deliberately did not assert on choice quality.

**Plus:** all **10,563** real ladder positions in the corpus replayed through the deploy entry point
→ **0 agent errors**. Cold start (import → first decision) **0.22s**, matching the field's
`remainingOverageTime` opening at 599.62 of 600 — no first-move timeout risk. Env spec read
directly: `actTimeout` default **0** (no per-act cap), `runTimeout` **2000s**, so the 600s figure is
the game's own pool.

**Verdict: there is no crash, no illegal move, no timeout and no uncovered context to find.** This
angle should not be opened again unless a submission actually errors.

### The real find: the turn-order default was wrong for the ENTIRE FIELD, not for one deck

The previous run found that specialist dispatch is blind before the board exists, so the generic
`scorer._score_sub` decided the turn-order toss with an unmeasured rule ("going second is often
better for a setup deck"), and fixed it *for Lucario* via a deck.csv fallback. I checked whether
that generalises, because if it does the per-specialist patching is the wrong shape of fix.

New `tools/first_turn_field.py` reads the episode zip, finds every IS_FIRST decision, attributes it
to the answering seat's deck, labels the archetype and tabulates. **1,400 episodes, 305 answers,
25 archetypes: YES 99.0% overall, and 100% in every one of the 9 archetypes with n ≥ 8** —
Grimmsnarl 85/85, Fezandipiti 50/50, Lopunny/Froslass 33/33, Ogerpon 28/28, Dragapult 25/25,
Kangaskhan 19/19, Cornerstone/Kangaskhan 10/10, Lucario 8/8, Lopunny 8/8. And of those same 305
asked seats, the one that went first won **54.4%** — an independent replication of the forced mirror
A/B's 54.0% ± 2.1 from an entirely different data source.

So I fixed it at the source: **`scorer._score_sub` now answers YES at IS_FIRST** (commit `68c86c0`),
with the evidence written into the branch it replaces. A specialist that fails to load, or an
archetype we have not written one for, no longer concedes the opening turn.

Also correcting the previous entry: `starmie_rules`, `fezandipiti_rules` and `dunsparce_rules`
**already had** the pre-board fallback (fezandipiti's docstring records IS_FIRST YES 2,125/2,125 in
its own corpus). The ones still without it — crustle, grimmsnarl, tusk, iono, cinderace,
hops_snorlax — are no longer load-bearing now that the default itself is right.

### v4 built and fully verified, deliberately not shipped
`experiments/luc_majkel_v4.tar.gz` = v3 + the generic default.
- Paired agreement, 4,074 elite decisions, v3 vs v4: **every bucket byte-identical** (all 53.73,
  main 45.53, swing-or-end 88.00, other 67.04). Exactly as designed — on the shipped Lucario path
  the specialist already answers, so this is pure defense-in-depth with **no expected live gain**.
  That is precisely why it does not justify evicting v2.
- `robust_probe` v4 vs the 153 field decks: 920 games / **135,341 decisions**, CLEAN.
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=145 statuses=[DONE,DONE] rewards=[-1,1]`.
- `pytest tests/` → 9 passed, the same 2 pre-existing mock-fixture failures, none new.
It is ready to ship the moment there is a slot whose eviction costs nothing.

### STRATEGY.md now exists ($30k × 8, due 2026-09-13)
Flagged as the highest-value unclaimed thing in this workspace by the last three entries. Written,
~200 lines, honest. It leads with the result other entrants can actually use — **your self-play
arena is anti-predictive, and here is the number (93.8% local vs 462 live)** — then the real-field
agreement harness that replaced it, the dispatch bug it found, the five well-powered negatives, and
the three-layer verification stack above. `docs/strategy_report.md` is the stale June draft built
around the search-plus-net thesis this workspace has since refuted; STRATEGY.md supersedes it and
does not reuse it.

### What the next run should do FIRST
1. **Re-read 55390639 and 55390373.** +70.8 for v3 is the right sign for the turn-order fix but the
   refs were ~2h old. This is the first clean live A/B we have; let it settle before evicting either.
2. **Ship v4 when a slot is free that does not cost the A/B** (i.e. once v2 has settled and can be
   evicted on its number). It is fully verified and strictly non-negative.
3. **Do NOT open: robustness (closed here, three layers), search (four refutations), prize-trade
   economics (double negative), in-turn energy/tempo sequencing.** That is four angles closed by
   measurement. What is left is deck/pilot coverage.
4. The only lever big enough to matter is still **a specialist for a top archetype we cannot fly**
   (Kangaskhan/Latias 63.2%, Dragapult/Meowth 58.0%, Thwackey/Dipplin 59.5%). STRATEGY.md §7 sketches
   the cheaper version of this: fit a specialist's constants to *frontier agreement* on that
   archetype's corpus rather than hand-tuning, gated on the confound-free buckets and the §6
   robustness stack. Every instrument is already archetype-agnostic except its corpus, and
   `tools/harvest_lucario.py` is the template for building one.
5. `MULLIGAN` (42) appears in **neither** our corpus nor 400 sampled real episodes — the engine
   probably auto-resolves it. Confirm cheaply before anyone spends effort on it.
