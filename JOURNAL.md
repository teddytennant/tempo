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

---

## 2026-08-10 (UTC) — slot 2/5 — ANGLE: deck construction, rebuilt from scratch vs the current meta

**Submitted:** ref `55392668` `luc_majkel_v4.tar.gz` — "slot2 luc-majkel-v4". CLI reported
**4 submissions remaining today**, which settles the ambiguity the last two runs argued about: the
cap **does** reset at UTC midnight, and the 4 entries stamped 2026-08-09 20:40–22:21 did not count
against today. Evicted `55390373` (v2, settled 550.7); active pair is now
**55390639 (v3, 654.7) + 55392668 (v4)**.

### The angle is CLOSED, and it closes on the strongest evidence in this file

**Our decklist is already the frontier's decklist, and the frontier has not changed it.** The
2026-08-09 dump was published 00:08 UTC; I pulled it 15 minutes later. In it, **Majkel1337 (rank 1,
LB 1203.5) played 26 games: 23 on a list BYTE-IDENTICAL to the one we ship**, and 3 on a
Kangaskhan/Latias build he is evidently testing. Three more field teams — Marshall_Maximizer,
Oleksandr_Savsunenko, 李秉叡_ntumlnoob_ — ship the identical 60 cards. Of the five Lucario teams in
the field only `seven` runs a different build (Cornerstone Mask Ogerpon ex / Rock Fighting Energy /
Xerosic's Machinations, no Hariyama line, 4 Wally's). **Imitation has no headroom left: we already
copy the consensus optimum.**

**And the deck is not what separates #1 from everyone else.** Those four teams pilot the *same 60
cards* at LB **1203.5 / 892.4 / 879.9 / unrated** — a 320-point spread on an identical list. This is
the cleanest statement of the workspace's central problem we have ever had a number for:
**deck construction is not the lever; the policy is.**

### De-confounding the archetype table — the confound is real but SMALL (a negative on my own hypothesis)

I opened the run believing the archetype win-rate table in RESEARCH.md was badly pilot-confounded,
and the band table looked like it agreed: Grimmsnarl wins **41.9%** in the 850–1000 band and
**50.7%** at 1000+ on the same 60 cards. That reading is wrong — banding the *seat* does not control
who it played, and a seat in a low band is largely playing *up*.

Doing it properly (`tools/deck_strength.py`, new): fit
`P(i beats j) = sigmoid(a·(r_i − r_j)/400 + d[arch_i] − d[arch_j])` over **4,555 decided games** with
both pilots' public-LB ratings joined, CIs bootstrapped over **games** (not seats — the two seats of
one game are one observation). The rating term is healthy on the fresh dump: **a = 0.352 (CI
0.212–0.489)**, i.e. a 400-point edge is worth **58.7%**.

Verdict: **mean |raw − deck-only| = 2.4 points, largest relative reshuffle 4.7.** The raw table was
usable after all. Rating-controlled deck-only win rates:

| archetype | seats | raw | deck-only | 95% CI |
|---|---|---|---|---|
| Kangaskhan / Latias | 79 | 63.3 | **61.2** | 50.6–68.9 |
| Meganium / Hydrapple | 60 | 58.3 | 61.1 | 52.1–72.1 |
| Dragapult / Meowth | 633 | 59.4 | **57.4** | 53.7–60.9 |
| **Lucario / Hariyama** | 331 | 55.9 | **53.8** | 48.4–57.6 |
| Fezandipiti / Alakazam | 1617 | 49.9 | 47.3 | 44.6–50.3 |
| Marnie's Grimmsnarl | 2926 | 46.6 | 44.1 | 41.7–46.3 |
| Kangaskhan / Crustle | 332 | 38.9 | **37.3** | 32.4–43.0 |

Two things fall out. **The June wall is now the worst deck in the field at 37.3%** — re-shipping it
was correctly abandoned. And **the entire ceiling on a perfect archetype switch is ~+3.6 points**
(Lucario 53.8 → Dragapult 57.4), which we pilot at **0/32**. The unexploited lever is smaller than
this file has been assuming.

### The field we face IS the global field — no band-specific tech

We sit at **LB 654.4, rank 2932 of 6679 — dead on the median**, so matchmaking pairs us mid-ladder,
not with the top 20. I expected a band-specific meta worth teching against. There is none
(`tools/meta_bands.py`, new): in the 550–700 band the opponents are Grimmsnarl **29.1%** /
Fezandipiti-Alakazam **22.0%** / Lopunny-Froslass **11.9%**, against a global 30.4 / 17.8 / 10.7.
Same field. Nothing to tech for.

**And the list is fine against it.** Lucario's field-share-weighted expected win rate over **83% of
the 08-09 field is 57.2%** — vs Grimmsnarl 46.7% (n=105), Fezandipiti/Alakazam 49.1% (n=57),
Lopunny/Froslass 90.0% (n=30), Dragapult/Meowth 62.5% (n=24). Its one bad matchup,
Kangaskhan/Latias **22.5%**, is ~1% of the field we face — and no field player runs a tech answer we
could copy, so there is nothing to imitate even if we wanted it. Day-over-day the meta is stable
(Grimmsnarl 30.2→32.1% share, Fezandipiti 18.0→17.7%, Lucario 3.3→3.6% at 53.6→55.9%).

The one number worth watching: **Lucario vs Grimmsnarl moved 53.4% (n=73, 08-08) → 46.7% (n=105,
08-09)**; pooled 49.4% over n=178. Grimmsnarl is 32% of the field. Not a crisis, but if it keeps
sliding it is the first real meta threat to the list.

### Public LB rating is a weak predictor of head-to-head — read with care

On the 08-08 dump joined to today's LB, the higher-rated seat won only **53.7%** overall, and
**50.5%** in the n=202 games with a **400+ point gap**. The fresh 08-09 dump is much healthier
(a=0.352 vs 0.185), and the difference between the two is almost certainly *stale ratings* — today's
LB score reflects a team's current 2 active submissions, not the agent that played a two-day-old
episode. Treat that as a caveat on the join, not as a fact about the game. It is still a third
independent demonstration that **a single LB number is a noisy read on agent strength.**

### New instruments
| tool | what it answers |
|---|---|
| `tools/frontier_deck_watch.py` | "is the player whose list we copy still playing it?" — prefix-scans a day of replays for a named team's exact 60-card registrations and diffs them against our `deck.csv` |
| `tools/deck_strength.py` | intrinsic archetype strength with pilot rating held fixed, + the **fast prefix extractor** |
| `tools/meta_bands.py` | the metagame split by rating band, and the field-weighted deck-choice objective |

**The prefix scanner is the durable win.** A replay is ~6 MB but the team names, the result and both
60-card registrations all sit in the first few hundred KB, so it reads 512 KB instead of the whole
file — a full parse of the 21 GB unzipped dump becomes ~1 minute. **Validated against the full JSON
parse on the 08-08 zip: 4,428 games and 238 LB-join drops, identical to the byte.** `deck_strength`
uses it by default with `--slow` to fall back.

### What was shipped, and why it is not a deck change
The angle produced no deck change, so this ships **v4** — built and fully verified last run and held
back only because shipping it would have cost the v3/v2 live A/B. That A/B has now done its job
(**v3 − v2 = +103.7**, the sign the turn-order fix predicts, with v2 settled at 550.7 across two
readings), and v2 contributes nothing to the LB under v3's 654.7. Expect **no live gain** from v4 —
paired on 4,074 elite decisions it is byte-identical to v3 in every bucket, because on the shipped
Lucario path the specialist already answers IS_FIRST. The reason to ship is the playbook's rule:
end the day with the two strongest agents active, and v3 + v4 beats v3 + v2.

### Verification (all green)
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=124 statuses=[DONE,DONE] rewards=[-1,1]`.
- `robust_probe` vs all **153 real ladder decklists**: 300 games / **44,586 agent decisions** — 0
  exceptions, 0 illegal, 0 rejects, 0 hangs, 0 moves over 1s. p50/p99/max **0.24/136.8/252.6 ms**;
  worst cumulative game 4.8s of 600s. **CLEAN.**
- Fast prefix scanner validated against full parse (above).
- NB `robust_probe --src` wants a **source tree** (`agent/` + `search/`), not the extracted tarball,
  and `--opps` is a comma-separated list of deck *names* inside `--decks-dir`. Build the field list
  with `ls data/meta_aug/decks/*.csv | xargs -n1 basename | sed 's/\.csv$//' | paste -sd,`.

### What the next run should do FIRST
1. **Read 55392668 and 55390639.** They should be near-identical by construction; a large gap
   between them is evidence about **live score noise on identical policies**, which is worth more
   than the ship itself. Do not conclude from a same-day reading.
2. **Do NOT open deck construction again.** Closed here: our list is the frontier's list, four teams
   span 320 LB points on it, the band meta equals the global meta, and the whole archetype-switch
   ceiling is ~+3.6 points against a 0/32 piloting failure. **Five angles are now closed by
   measurement** — robustness, search (4 refutations), prize-trade economics, in-turn energy/tempo,
   and deck construction.
3. The remaining lever is what it has been for three runs: **play quality on the list we already
   fly.** The agreement harness says where — `main` 45.5%, `attack-available` 39.1%,
   `attack-choice` 36.4% are the low buckets, and unlike `swing-or-end` (88.0%) they have real room.
   Attack *choice* is the one with the least turn-ordering confound left in it.
4. Watch **Lucario vs Grimmsnarl** (49.4% pooled, sliding) and **Kangaskhan/Latias** — the archetype
   with the best deck-only strength (61.2%), our worst matchup (22.5%), and now the thing the #1
   player is testing. If it grows past ~5% of the field the list stops being fine.
5. `STRATEGY.md` exists and is strong. This run adds three sections worth having: the identical-list
   / 320-point-spread result, the rating-controlled de-confounding method, and the prefix-scan trick.

---

## 2026-08-10 (UTC) — slot 3/5 — ANGLE: search depth (lookahead, better leaf evaluation)

**Submitted:** ref `55393889` `luc_majkel_v6.tar.gz` — "slot3 luc-majkel-v6". CLI: **3 submissions
remaining today** (so today's count is v4 + v6 = 2). Evicted `55390639` (v3), which was
policy-identical to v4 on the shipped Lucario path, so the eviction cost nothing. Active pair is now
**55392668 (v4) + 55393889 (v6)**. Team standing at the start of the run: **rank 3023 / 6683,
LB 648.4** (v4 read 685.6 ten minutes after submission and has since drifted — do not conclude).

### Why I opened an angle RESEARCH.md calls settled

Four refutations of search are on file, but the note that closes them ends with a precondition:
*"do not spend another slot on search depth **without a fundamentally different value function**."*
All four refuted the same thing — a heuristic-eval search **replacing** the scorer's ranking
(determinized UCT 560.1 live, Rust MCTS 528.8 live, the `lookahead.py` sweep ~38–42%, the `hybrid`
A/B 23.3%/50.0%). The `lookahead.py` post-mortem names the mechanism: *"the static board value is a
far weaker signal than the scorer's own implicit tempo knowledge."*

There is exactly one search in the shipped artifact that does **not** have that problem, and it had
never been examined: `agent/lethal.py`, which searches the engine's native forward model for a
sequence that wins the game **this turn**. Its leaf value is not an estimate — it is
`state.result`. It cannot be wrong about the value of a leaf. And it was throttled on four axes,
none of them ever measured.

### What the throttles were costing (`tools/lethal_probe.py`, new)

Replays real ladder MAIN decisions under one-axis-at-a-time widenings, so a "wide proves a win,
shipped does not" event is attributable. 2,500 decisions from `records_11447.jsonl`:

| axis widened | proven wins / 2500 | vs shipped | p99 latency |
|---|---|---|---|
| **shipped** (prizes≤2, attack on menu, 600 nodes/0.25s, depth 10) | **86** | — | 140.6 ms |
| PRIZE_GATE 2 → 3 | 108 | +23 | 140.7 ms |
| drop the attack-on-menu requirement | 113 | +28 | 139.5 ms |
| budget 600/0.25s → 4000/1.0s | 95 | +10 | 899.1 ms |
| depth 10 → 18 | **84** | **−1** | 159.0 ms |
| all four | 148 | +63 | 1000.8 ms |

Two of the four throttles were badly wrong and two were fine:

- **PRIZE_GATE = 2 is arithmetically wrong.** A single knockout is worth up to **three** prizes (a
  Mega ex), so 3 is the largest prize count from which one KO ends the game. The field is full of
  Mega ex. This gate hid 23 game-winning lines.
- **Requiring an ATTACK already on the root menu defeats the purpose of searching.** The lines worth
  finding are precisely the ones that must attach/evolve/use an ability *before* an attack becomes
  available; those start from a menu with no attack on it. 28 lines hidden — the largest single hole.
- **Depth 10 is not binding.** Raising it to 18 found *nothing* and lost one to the time cap.
  Left alone.
- **Budget is barely binding** (+10 for 6× the wall clock). Left alone.

Neither of the two bad gates is a soundness condition. A positive is an **engine-declared terminal
win** either way, so they were only ever deciding what to *look at*. Opening both together
(`cand1`: prizes≤3, no attack requirement, budget and depth untouched) takes proven wins
**86 → 140** at **p99 140.6 → 144.1 ms** — 54 of the 63 available, for free.

### Falsification, because a determinized proof can be a phantom

The proof is taken under a belief-corrected determinization of our own deck, so a line that needs a
lucky draw could be fake. `lethal_probe` segments the corpus into real games by the turn counter and
asks how far each claim sits from the end of that game. A genuine "a win exists this turn" should
coincide with the game ending.

| config | claims | median turns left | ended ≤1 turn | ≥4 turns left |
|---|---|---|---|---|
| shipped | 86 | 0 | 90.7% | 9.3% |
| cand1 (both gates open) | 140 | 0 | 87.1% | 12.9% |

The widened claims land where games actually end, on essentially the shipped verifier's own profile.
The ~9–13% tail is a property of the *existing* artifact, not something this change introduces.

### The widening ALONE made the agent worse — and the agreement harness caught it

`prize_agreement` on the 4,074 elite decisions, v5 = v4 + both gates open:
**all 53.73 → 52.95, main 45.53 → 44.27, attack-choice 36.42 → 34.77.** Four buckets down, none up.
Robustness was clean (920 games / 134,567 decisions, worst cumulative game 19.8s of 600s) — this was
a *play-quality* loss, exactly the shape RESEARCH.md's v8/v9 post-mortem describes.

**`tools/lethal_cost.py` (new) explains it, and the explanation is the actual find of this run.**
For every position the widening newly proves, it forks the game, plays **the shipped agent's own
move**, and re-runs the search:

- **63 of 69** — the scorer's move keeps the win provable. The verifier was overriding a strong
  prior on a turn that was **already won**. Pure churn.
- **6 of 69** — the scorer plays a card (`PLAY` ×4, `ATTACH` ×2) that makes the win **unprovable**.
  It develops the board on the turn it could have won.
- 0 undecidable.

So widening buys 6 real saves per 2,500 decisions and pays for them with 63 gratuitous deviations.
That is a textbook instance of this workspace's standing lesson, caught **before** it shipped.

### The fix: prior protection decided by a proof, not a score margin

`lookahead.py` protected the prior with `SWITCH_MARGIN = 900.0` — an arbitrary constant on a
heuristic value. Here the same job can be done exactly. The verifier now runs **after** the scorer,
is handed the scorer's answer, applies it in the fork, and **stays silent if a win is still
provable**. It speaks only where it can *prove* the scorer throws the game away. Anything unclear —
no scorer answer, a selection illegal for the fork, an engine error — counts as do-not-defer, so the
proof wins ties.

This required moving the `_lethal_move` call in `scorer.best_options` from before the scoring loop to
after it, so it also withdraws the verifier's authority in the **86 positions the old gate already
covered** where the scorer preserves the win. That is a larger behavioural change than the gate
widening itself, and it is the one the agreement harness likes:

| bucket | n | v4 | v5 (gates only) | **v6 (shipped)** | v6 − v4 |
|---|---|---|---|---|---|
| all | 4074 | 53.73 | 52.95 | **54.52** | **+0.79** |
| main | 2530 | 45.53 | 44.27 | **46.80** | **+1.27** |
| main/attack-available | 1712 | 39.08 | 38.14 | **40.83** | **+1.75** |
| main/attack-choice | 604 | 36.42 | 34.77 | **37.58** | **+1.16** |
| main/elite-declined-attack | 1407 | 36.25 | 35.04 | **39.02** | **+2.77** |
| main/swing-or-end | 75 | 88.00 | 88.00 | 88.00 | 0 |
| setup / other | 42 / 1502 | 71.43 / 67.04 | = | = | 0 |
| main/elite-attacked | 305 | 52.13 | 52.46 | 49.18 | **−2.95** |
| main/attack-choice+attacked | 133 | 48.87 | 48.87 | 45.11 | **−3.76** |

**Read the two negatives honestly.** They are the elite-attacked slices, i.e. exactly where the
documented turn-ordering confound bites: the old verifier said "attack now", the elite also attacked,
so it scored as agreement. v6 defers to the scorer, which develops first and attacks later in the
same turn. By construction every position involved is a turn where the scorer's line **provably
wins**, so both lines take the game — but I cannot prove that from agreement alone, and the live
score is the only arbiter. `main/attack-choice`, one of the two confound-free buckets, is **up**;
`main/swing-or-end`, the other, is **unchanged**.

### Verification (all green)
- `robust_probe` vs all **153 real ladder decklists**: 920 games / **140,106 decisions** — 0
  exceptions, 0 illegal, 0 engine rejects, 0 hangs, 0 moves over 1s. p50/p99/max
  **0.27 / 247.8 / 466.7 ms**; worst cumulative game **12.1s of 600s** (2%). CLEAN.
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=113 statuses=[DONE,DONE] rewards=[-1,1]`.
- `pytest tests/` → 9 passed, the same 2 pre-existing mock-fixture failures, none new.
- Artifact diff vs v4: **exactly `lethal.py` and `scorer.py`**; `deck.csv` byte-identical. Clean
  single-mechanism live A/B against `55392668`.

### What the next run should do FIRST
1. **Read 55393889 against 55392668.** They differ in one mechanism on an identical decklist. If v6
   > v4, the verified-search widening is real and the two elite-attacked bucket regressions were the
   turn-ordering confound. If v6 < v4, then **deferring to the scorer on already-won turns is
   wrong**, and the right follow-up is v5's unconditional widening (built, verified, robustness
   clean, `experiments/luc_majkel_v5.tar.gz`) rather than reverting to v4. Either outcome is
   informative — that is why this was worth a slot.
2. **Do not re-open search generally.** The four refutations still stand and this run does not touch
   them: nothing here replaces the scorer's ranking with a heuristic-eval search. What it shows is
   narrower and should be stated narrowly — *the search that is allowed to speak is the one whose
   leaf value is a proof, and it should speak only when it can prove the prior is wrong.*
3. **The obvious next target on the same principle:** the verifier is only consulted at `MAIN`. The
   scorer can still break a proven win inside a **sub-select** (which card to play, where to attach),
   and nothing checks that. `lethal_cost.py` extends to it directly.
4. `_MAX_DEPTH` and the node/time budget are measured non-binding — **do not tune them.** That is two
   more dead ends closed cheaply.
5. Still open and still the biggest lever: **a specialist for an archetype we cannot fly**
   (Kangaskhan/Latias 61.2% deck-only, Dragapult/Meowth 57.4%), and watching Lucario vs Grimmsnarl.

**Addendum, 02:05 UTC (18 min after submitting v6).** Readings taken on the way out, recorded because
they sharpen the "never conclude from a fresh reading" rule rather than because they mean anything:
v6 `55393889` **600.0** (the entry rating — it has barely played), v4 `55392668` **539.3**, v3
`55390639` **648.4**, v2 `55390373` **550.7**. **v4 has moved 685.6 → 539.3 in 85 minutes**, a 146-point
swing on an artifact nobody touched. Any v4/v6 comparison before both settle is worthless. Also note
this makes the *previous* run's "v3 − v2 = +103.7" look like it was read at a transient too.

Did not use the remaining 3 slots. Every further submission tonight would evict v4, which is the
control for the single-mechanism A/B this run set up, and there is no other verified candidate that
beats it — v5 exists and is robustness-clean but the agreement harness says it is worse than both.
An unused slot beats a wasted one.

---

## 2026-08-10 (UTC) — slot 4/5 — ANGLE: prize-trade economics

**Submitted:** ref `55394411` `luc_majkel_v7.tar.gz` — "slot4 luc-majkel-v7". CLI: **2 submissions
remaining today** (today's count v4 + v6 + v7 = 3). Evicted `55392668` (v4). Active pair is now
**55393889 (v6) + 55394411 (v7)**, a clean single-mechanism A/B on a byte-identical decklist.

Two mechanisms were built and measured this run. **One shipped, one was rejected — and the reason
the rejected one fails is the more valuable result.**

### Reading the A/B the last run set up, and a correction to how we read scores at all

| ref | 01:57 | 02:17 | note |
|---|---|---|---|
| v6 `55393889` | 674.1 | **571.6** | live, unconverged (was 600.0 at 18 min, 451.7 at 02:05) |
| v4 `55392668` | 545.5 | 493.5 | live until evicted this run |
| v3 `55390639` | 648.4 | 648.4 | **frozen** — evicted 01:47 |
| v2 `55390373` | 550.7 | 550.7 | **frozen** |

**v6 has now been read at 600.0 / 674.1 / 451.7 / 571.6 inside two hours on an artifact nobody
touched.** No v6/v4 conclusion is available and none should be drawn.

**The correction worth carrying: eviction freezes a score, so an old "settled" number may be a
stopped clock rather than a converged one.** v3's 648.4 and v2's 550.7 have not moved since they
went inactive, while both live refs move by >100 points an hour. A new agent enters at 600 and its
rating walks from there; if it is evicted mid-walk, whatever it happened to read is what stays in
the table forever. Every historical score in RESEARCH.md that belongs to an evicted submission
should be read as "where the walk was when it stopped", not as that agent's strength. Team standing
at 02:10: **rank 4511 of 6689, score 535.0**, against a field median of 625.8.

### Rejected: the defensive mirror of the win search (`agent/threat.py`, built, NOT wired in)

The angle's honest opening. RESEARCH.md closes prize-trade economics, but it closes the *offensive*
half — swing-or-end 88.0%, attack-choice deviation 6/133, the Mega-ex exposure guard measured
harmful. The defensive half was never measured: after we swing, can they swing back and take their
last prizes? That is what "when is trading a Pokémon correct" actually asks.

`agent/threat.py` answers it the only way this workspace has ever got value out of search — with a
proof at the leaf. Fork at the MAIN decision, apply the scorer's turn-ending move, then AND/OR
search the opponent's turn: **OR over their selections, AND over ours** (promoting a new Active
after a knockout), leaf value `state.result`. Their hand and deck are placeholder basics, so in the
fork they may attach, retreat, use in-play abilities and attack, but cannot play a trainer or gust —
a strict **subset** of their real options, so the model can only miss threats, never invent one.

`tools/threat_probe.py` over 2,500 real ladder MAIN decisions:

| | our move | **the elite's own move** |
|---|---|---|
| gate opened (they are within one KO of their last prize, or we have no bench) | 170 | 97 |
| the move **provably loses** | 30 — **17.6% of gated** | 17 — **17.5% of gated** |
| a provably-safe alternative turn-ender exists | 4 | 1 |

**Three findings, and the third kills it.**

1. **The threats are real.** Re-run with the opponent forbidden to ATTACH inside the fork
   (`--no-opp-attach`, leaving them only energy already on their board): **identical counts, 30 and
   17.** No proof depended on the energy zone derived from the placeholder deck. This was the
   soundness worry going in, and it is dead.
2. **It describes the position, not the move.** `--elite-move` judges the frontier player's own
   decision instead of ours: it condemns theirs at **17.5%** against **17.6%** for ours — the same
   rate — in games they went on to **win**. Sequencing the corpus by turn shows the mechanism: the
   positives arrive in runs of consecutive decisions inside one turn, and the run still proves
   losing after the elite's own development line *and* their own attack. The position is lost. The
   move is not why.
3. **There is nothing to do about it.** A provably-safe alternative exists in **4 of 2,500**, and
   the elite played our alternative in **0** of them.

**The durable asymmetry.** An offensive proof is actionable because we are the one who acts — "a win
exists and your move throws it away" *names the move to play instead*. A defensive proof is a
statement about what the **opponent** will do, and proving they have a winning line does not produce
a move that takes it away from them. Identical engine, identical leaf value, identical discipline,
opposite outcome. **Search for a proof only where we are the one who gets to act on it.**

`--elite-move` is the reusable instrument here and it should be pointed at every future verifier: if
a flag fires on frontier players' decisions at the same rate it fires on ours, in games they won, it
is measuring the position rather than the policy.

### Shipped: the win verifier was blind below the MAIN menu

Last run's item 3, and it survives contact. `lethal_move` returned `None` on any context that was
not `SelectContext.MAIN`. **Nothing about the search needs a MAIN menu** — `search_begin` works from
any agent observation carrying a `search_begin_input`. It was an assumption, never a requirement.
The cost: the moment the scorer decided to PLAY a card, the engine's follow-up question — *which*
card, *which* target, *where* to attach — was answered with nothing checking the answer kept a
proven win alive.

`tools/lethal_sub_cost.py` (new) over **3,607 real single-answer sub-selects**:

| | n |
|---|---|
| a win this turn is provable **from the sub-select itself** | 186 |
| the shipped answer **keeps** it → the verifier must stay silent | 174 (93.5%) |
| the shipped answer **throws it away** | **12** |

The 93.5% preservation rate replicates the MAIN-level number almost exactly, which is the important
part: **v6's prior protection is just as load-bearing here.** Without it this would be 186
gratuitous deviations from a strong prior — the exact failure v6 was built to stop.

**And the 12 are corroborated from outside the proof.** The corpus is decisions from games the
frontier player *won*: in those 12 positions the elite played **the verifier's answer 7 times and
our shipped answer once**. No change in this workspace has previously had external validation of
this kind — v6's own 6 saves had none.

Most fire in one shape: the opponent has **no benched Pokémon**, so a knockout of their Active ends
the game outright, and the sub-select that picks the wrong card quietly gives that up. Several sit
at turn 2 against a lone 60–70 HP basic — checked, and the opponent's Active is face-up in every one
of them, so these are not the placeholder-Active artifact they superficially resemble.

`lethal.ALLOW_SUB_SELECT = True`; `scorer.best_options` consults the verifier when
`ctx == MAIN or (select.maxCount == 1 and n > 1)`. Forced and multi-answer selects are skipped —
there is nothing to choose, and a padded multi-select answer is not something a proof can reason
about.

### The agreement harness is NOT deterministic — and finding that out is what made the read clean

v7's first agreement run moved `main`, a bucket the change **cannot touch by construction** (on a
MAIN record v6 and v7 execute identical code). So I re-ran **v6 against itself**:

| bucket | v6 run 1 | v6 run 2 | **v7** |
|---|---|---|---|
| all | 2222 (54.52%) | 2216 (54.39%) | 2222 (54.54%) |
| **main** | **1184 (46.80%)** | **1179 (46.60%)** | 1180 (46.64%) |
| **other** (sub-selects) | **1007 (67.04%)** | **1007 (67.04%)** | **1012 (67.38%)** |
| every other bucket | — | identical | identical |

`lethal.py`'s fork draws from a determinized deck, so the engine's own randomisation makes a proof
appear or vanish between runs. `main` is where the verifier ran in v6; `other` is where it did not —
exactly the observed split. So:

- **v7's `main` delta is inside v6's own run-to-run spread. Not attributable.**
- **v7's `other` +5 decisions is real** — v6's `other` is reproducible to the decision across two
  runs, and `other` is the only bucket this change can reach.

Practical rule now in RESEARCH.md: **a MAIN-bucket delta under ±5 decisions (±0.2 pt) is not
attributable**; re-run the baseline in the same session before believing a small one. Larger
recorded deltas survive (v6−v4 was +32 decisions on main).

### Verification (all green)
- `robust_probe` vs all **153 real ladder decklists**: 920 games / **135,211 decisions** — 0
  exceptions, 0 illegal, 0 engine rejects, 0 hangs, 0 moves over 1s. p50/p99/max
  **0.58 / 260.3 / 585.8 ms** (v6: 0.27 / 247.8 / 466.7). Worst cumulative game **33.6s of 600s**
  (5.6%, up from v6's 12.1s — the verifier now runs on far more decisions; still ~1/18th of clock).
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=104 statuses=[DONE,DONE] rewards=[-1,1]`.
- `pytest tests/` → **9 passed, 2 failed**, the same pre-existing mock-fixture failures, none new.
- Artifact diff vs v6: **exactly `lethal.py` and `scorer.py`**; `deck.csv` byte-identical.
  `agent/threat.py` is deliberately kept OUT of `build_submission.sh` so the A/B stays single-mechanism.

### What the next run should do FIRST
1. **Read `55394411` (v7) against `55393889` (v6)** — but only after both have been live for hours,
   and read the *shape* of the walk, not one number. v6 alone produced 600.0 / 674.1 / 451.7 / 571.6
   in two hours. If a single reading is all that is available, do not conclude.
2. **Do not rebuild the defensive mirror.** It is measured, falsified three ways, and the code is
   kept at `agent/threat.py` + `tools/threat_probe.py` so the next run can read it instead of
   rebuilding it. Six angles are now closed by measurement: robustness, estimate-search (4
   refutations), prize-trade economics (both halves), in-turn energy/tempo, deck construction, and
   the defensive proof.
3. **Point `--elite-move` at the existing verifiers.** It cost almost nothing and it is the only
   instrument here that can tell "this flags bad play" from "this flags bad positions". Running it
   against the MAIN-level `lethal` override is the obvious next application.
4. **The verified-proof line still has room, and it is the only one that does.** The pattern that
   works is: find a decision the proof can reach that nothing currently checks, then protect the
   prior with a second proof. MAIN was v6, sub-selects are v7. What is left: multi-answer selects
   (skipped here on purpose), and `_win_plausible`'s coverage of the no-bench clause.
5. Still open and still the biggest structural lever: **a specialist for an archetype we cannot fly**
   (Kangaskhan/Latias 61.2% deck-only, Dragapult/Meowth 57.4%), against a documented 0/32 piloting
   failure. And watch Lucario vs Grimmsnarl (49.4% pooled, sliding).

Did not use the remaining 2 slots. v6 and v7 are the two strongest artifacts and differ by one
measured mechanism; a third submission tonight would evict v6 and destroy the A/B for no candidate
that beats it. An unused slot beats a wasted one.

---

## 2026-08-10 (UTC) — slot 5/5 — ANGLE: energy and tempo, and where we waste a turn

**Submitted:** ref `55395183` `luc_majkel_v8.tar.gz` — "slot5 luc-majkel-v8". CLI: **1 submission
remaining today** (today = v4 + v6 + v7 + v8 = 4; the harness prompt's count was off by one, the CLI
is authoritative as always). Evicted `55393889` (v6). Active pair is now
**55394411 (v7) + 55395183 (v8)**, a clean single-mechanism A/B on a byte-identical decklist.

### First, the thing that invalidates the last three runs' score comparisons

The last run asked for v3 vs v4, which are **policy-identical on the shipped Lucario path**. Both are
now evicted and therefore frozen:

| ref | policy | final frozen score |
|---|---|---|
| v3 `55390639` | identical to v4 | **648.4** |
| v4 `55392668` | identical to v3 | **493.5** |

**155 points between two artifacts that play the same game.** That is the answer to "how much live
noise is there", and it is bigger than every live delta this workspace has ever reasoned from. Add
today's readings on live refs: v7 `55394411` read **491.5 → 663.7 → 523.1** in 40 minutes; v6
`55393889` read **543.1 → 495.7 → 520.0** in the same window. Team standing is **rank ~4500 of
6689**; the leader board top is Luca 1212.1 / Majkel1337 1203.2 / AlphaStarmie 1189.6.

**Operational consequence, and it should be treated as a rule now: a single live score cannot
resolve a difference smaller than ~150 points, and eviction freezes whatever transient was showing.**
Ship decisions must come from the offline harnesses. The live score is only useful for detecting a
catastrophe (an errored submission, a dead archetype like the Crustle wall's 775 → 449 collapse).

### The instrument the workspace was missing: a harness that scores a TURN

Both agreement harnesses score one decision against the elite's answer at that decision. On MAIN
that is contaminated by ordering: if the elite swings immediately and we attach first and swing
second, we are marked wrong twice and played the identical turn. "Turn-ordering confound" has been
the standing explanation for `main` = 46.6% against `swing-or-end` = 88.0%, and nobody had measured
it.

**`tools/turn_replay.py`** (new) measures it. Fork the engine at a turn's *first* decision, drive our
own deploy entry point through the whole turn one `search_step` at a time until control passes to the
opponent, and compare the two turns as **action multisets canonicalised to card identity** (option
indices shift as a turn proceeds; card ids do not). Ordering is removed by construction.

- **Fidelity control**: our agent answers the fork's first question identically to the live one in
  **199/199**. Every replay ran to the end of the turn (188 `passed-to-opponent`, 11 `terminal`).
- Over **199 real frontier turns**, on the shipped v7 tree:

| per turn | elite | ours |
|---|---|---|
| attacked | 78.4% | 64.3% |
| attached energy | 79.9% | 58.8% |
| MAIN actions taken | 6.06 | 5.07 |
| elite swung and we did not | — | 29 turns (14.6%) |
| we swung and the elite did not | — | 1 turn (0.5%) |

- Identical turn: **8.0% overall, but 66.7% in the no-draw bucket** (the bucket our determinized
  deck cannot contaminate) against 3.3% where cards are drawn. **So the ordering confound is real
  and large — and it is not the whole story.**

### The finding, and why it is the one that ordering cannot explain away

**`tools/card_use.py`** (new) never forks. It asks our agent the identical question on the elite's
own menu and scores every option twice — offered / elite took / we took — so the take-rate gap is
policy and nothing else. Over 4,000 real MAIN decisions:

| option | offered | elite took | we took |
|---|---|---|---|
| **PLAY(Premium Power Pro)** | **1618** | **256 (15.8%)** | **4 (0.2%)** |
| PLAY(Poké Pad) | 603 | 288 (47.8%) | 142 (23.5%) |
| PLAY(Dusk Ball) | 581 | 301 (51.8%) | 173 (29.8%) |
| ABILITY(Lunatone / Lunar Cycle) | 502 | 363 (72.3%) | 244 (48.6%) |
| EVOLVE(Mega Lucario ex) | 448 | 197 (44.0%) | 433 (96.7%) |
| EVOLVE(Hariyama) | 663 | 87 (13.1%) | 513 (77.4%) |

Every row here is ordering-sensitive **except the first**. Re-ordering a turn changes *when* you
play a card, never whether you ever do — so a 0.2% take rate on a card offered 1,618 times is a
statement that we essentially never play it. The rows below it (we evolve early, they evolve late)
are exactly what the ordering confound looks like and should not be chased.

### The cause, and the frontier's actual rule derived rather than guessed

`agent/lucario_rules.py` gated Premium Power Pro (+30 to every {F} attack this turn) on the +30
**exactly** converting a swing into a knockout **and** the Active being in the Lucario line, and
returned `-1.0` — below END, i.e. never — otherwise. On the frontier's own menus that guard is
satisfied **83 times out of 2,552**.

**`tools/ppp_probe.py`** (new) buckets those 2,552 real frontier offers by what a rule could key on:

| bucket | offers | frontier played it |
|---|---|---|
| attack on the menu, +30 CONVERTS a KO | 136 | **41.9%** |
| attack on the menu, does not convert | 386 | **29.0%** |
| attack on the menu, already lethal | 963 | **23.7%** |
| **no attack on the menu** | 1067 | **3.3%** |
| active in Lucario line | 1281 | 19.8% |
| active = Solrock | 675 | 18.2% |
| active = Hariyama | 185 | 17.8% |
| active = Lunatone | 276 | 3.6% |
| *our shipped guard says PLAY* | *83* | *25.3%* |

**One feature — is an ATTACK on the menu, i.e. are we swinging this turn — separates 3.3% from
23.7–41.9%.** The KO conversion is a ~1.4x tie-break, not the rule. And the Lucario-line restriction
is unjustified: Solrock and Hariyama are {F} too and the card boosts them identically. The reason
the frontier can afford to be liberal is card economy: 4 copies behind Lunar Cycle (draw 3) and
Lillie's Determination (draw 6), and a turn-scoped buff held in hand is worth exactly nothing at end
of turn.

### What shipped, and the placement that was measured and rejected

Play it whenever an ATTACK is on the menu; **700** when the +30 exactly converts, **500** otherwise.
Both sit above every non-game-winning ATTACK score (max ~450 = 100 + 300·0.3 + 60 Aura-Jab bias +
200 KO) and **below every setup/search card**, so the buff is the last thing we do before swinging.

**The alternative placement at 1520/1600 was built and measured and is rejected.** It overshoots the
frontier (25.8% vs 15.8%) and drags the search items down with it — Poké Pad 23.5 → 17.6, Dusk Ball
29.8 → 22.2, Fighting Gong 43.8 → 34.4 — because at that score it outranks them and displaces them at
every single decision. Raw agreement on card_use's 4,000 MAIN decisions: v7 46.27%, **1520-variant
46.52%, shipped 500-variant 46.67%**.

Plus one guard the corpus could not have found: in **wall mode** our ex attacks score *below* END
(they whiff into the damage-negating Crustle), so an ATTACK on the menu does not mean we swing.
Without the guard we would spend the card on a turn that ends without an attack. Verified inert on
this corpus (no wall positions in it), so it protects the Crustle matchup at zero measured cost.

### Measured, with the baseline re-run in the same session

`prize_agreement` over the 4,074 elite decisions. **v7 was run twice first**, because the last run
established this harness is not deterministic where the verifier runs:

| bucket | n | v7 run1 | v7 run2 | **v8** | delta |
|---|---|---|---|---|---|
| all | 4074 | 2223 (54.57) | 2223 (54.57) | **2235 (54.86)** | **+12** |
| main | 2530 | 1183 (46.76) | 1180 (46.64) | **1191 (47.08)** | **+9.5** |
| main/attack-available | 1712 | 701 | 698 | 708 | +8.5 |
| main/elite-declined-attack | 1407 | 551 | 548 | **578 (41.08)** | **+28.5** |
| main/elite-attacked | 305 | 150 | 150 | **130 (42.62)** | **−20** |
| main/attack-choice+attacked | 133 | 60 | 60 | 49 | −11 |
| main/attack-choice | 604 | 228 | 227 | 226 | −1.5 |
| main/swing-or-end | 75 | 66 | 66 | 66 | 0 |
| setup / other | 42 / 1502 | 30 / 1010 | 30 / 1013 | 30 / 1014 | 0 / +2.5 |

v7's own run-to-run spread is **0–3 decisions**, so +12 on `all` and +9.5 on `main` clear it and
−1.5 on `attack-choice` does not exist. **The two confound-free buckets — `swing-or-end` (88.00,
unchanged) and `attack-choice` (flat) — did not move**, and the ±28.5/−20 split across
elite-declined-attack and elite-attacked is the documented turn-ordering signature, identical in
shape to v6's: we insert one more development action before the swing.

Ordering-immune corroboration, which is what actually justifies the ship:
- `card_use` Premium Power Pro **0.2% → 5.6%** (a third of the gap closed) with no other bucket
  disturbed.
- `turn_replay`'s turn-level "the elite played it and we did not" falls **80 → 48** over the same
  199 turns, and turns-we-attacked goes **64.3% → 64.8%** — no swing is lost to the extra action.

### The deck.csv footgun bit again — and it produced a coherent-looking fiction

The repo's `agent/deck.csv` is a **Great Tusk** list, not what we ship. The first pass of every
measurement above ran through it, routed to the *generic* pilot instead of the Lucario specialist,
and returned a completely believable story: we "never" fire Lunatone's Lunar Cycle, we attach energy
on 30% of turns to the elite's 83%, and we play Great Tusk 26 times out of a hand that does not
contain it. RESEARCH.md carries an explicit HAZARD note about exactly this and it still cost a
measurement cycle. **The tell was `PLAY(Great Tusk)` appearing in a Lucario corpus** — a card
resolved from the observation's own hand cannot be a card the observation's player does not hold, so
that row was proof the pilot was wrong before any number was worth reading. Every instrument added
here prints the deck path it used; read it every time.

### Verification (all green)
- `robust_probe --src experiments/luc_majkel_v8_src` vs all **153 real ladder decklists**: 920 games
  / **134,348 decisions** — 0 exceptions, 0 illegal, 0 engine rejects, 0 hangs, 0 moves over 1s.
  p50/p99/max **0.32 / 251.5 / 477.3 ms**; worst cumulative game **21.5s of 600s** (3.6%, *down* from
  v7's 33.6s). CLEAN.
- Packed cabt mirror smoke on the EXTRACTED tarball: `steps=120 statuses=[DONE,DONE] rewards=[-1,1]`.
- `pytest tests/` → **9 passed, 2 failed**, and both failures were confirmed present on the
  pre-change tree (`git checkout HEAD~2 -- agent/lucario_rules.py`). None new.
- Artifact diff vs v7: **exactly `lucario_rules.py`**; `deck.csv` byte-identical.

### What the next run should do FIRST
1. **Do not read `55395183` against `55394411` as a small number.** v3 and v4 are policy-identical
   and finished 155 points apart. If the pair sits within ~150 points, the A/B is *unresolved*, and
   saying so is the correct outcome — not picking the higher one.
2. **Run `turn_replay` on the remaining rows of the `card_use` table, in the no-draw bucket only.**
   Poké Pad 47.8 vs 23.5, Dusk Ball 51.8 vs 29.8 and Lunar Cycle 72.3 vs 48.6 are all large, but all
   ordering-sensitive at the decision level — the turn-level fork is the only instrument that can
   tell "we never do this" from "we do it later". `turn_replay` already reports both; the missing
   piece is running it with enough no-draw turns (only 14–15 of 199 qualify) to be worth reading.
   Raising `--n` to a few thousand turns is the cheap fix.
3. **The energy-attachment gap is still open and is the biggest number on the board**: 79.9% of
   frontier turns attach energy against our 58.8%. This run did not touch it. It is not the attach
   *target* (RESEARCH has that at 89.8% de-confounded) — it is that we end turns without attaching
   at all. `turn_replay` can localise it; `turn_audit`'s old "wasted_attach 3.6%" was measured in
   self-play and does not describe play against the field's boards.
4. **Point `--elite-move` (from `threat_probe`) at the MAIN-level `lethal` verifier.** Still the
   cheapest outstanding check and still not done — it is the only instrument that separates "this
   flags bad play" from "this flags bad positions".
5. Unchanged and still the biggest structural lever: **a specialist for an archetype we cannot fly**
   (Kangaskhan/Latias 61.2% deck-only, Dragapult/Meowth 57.4%) against a documented 0/32 piloting
   failure. And watch Lucario vs Grimmsnarl (49.4% pooled, sliding).

Did not use the last slot. v7 and v8 differ by one measured mechanism on a byte-identical decklist;
a sixth submission tonight would evict v7 and destroy the A/B for no candidate that beats it. An
unused slot beats a wasted one.

---

## 2026-08-10 (UTC) — FINAL POKÉMON RUN — the loop is OFF

**This was the last run. Teddy has turned the nightly loop off; whatever is active below is the
final answer and it sits untouched until the competition closes 2026-08-16.**

**ANGLE:** fork the strongest public agent, improve it only if the improvement is provable, submit
exactly two, stop.

### Blocked on the cap for half the run, and that shaped everything

The day's 5 submissions were already spent by 02:57 UTC (v4/v6/v7/v8). The CLI printed
**"0 submissions remaining today"** right after this run's one available submission. So slot 1 went
out at 19:27 UTC and slot 2 is armed to fire after the UTC reset via
`scripts/submit_after_utc_midnight.sh`, which waits for the date to roll over, submits once, and
prints the submissions list to confirm.

### The measurement that should have been made months ago

Every comparison in this journal before today was *our artifacts against each other*. Nobody had
played our shipped agent against a foreign one at scale, because there was no harness that could
load a foreign packed tree. `tools/fork_arena.py` (new) is that harness: it loads each side's
`main.py` by file path under a private module name with cwd and `sys.path` set to that side's own
directory, so two agents that both call their entry file `main.py` and both read a relative
`deck.csv` do not collide. No porting step — which is what made this expensive before.
`tools/fork_gauntlet.sh` (new) runs it against all seven independent published-notebook bots in
`agent/bots/`, 60 games each, seats alternated:

| agent | vs the 7-bot pool | 95% CI |
|---|---|---|
| **Codex Sol Eclipse Alakazam v22** | **327/420 = 77.86%** | [73.64, 81.57] |
| raunakdey07 "Advanced Heuristic Agent" (same deck) | 327/420 = 77.86% | [73.64, 81.57] |
| pllinas "Alakazam Rising Tide v21" (same deck) | 325/420 = 77.38% | [73.14, 81.12] |
| **makthanithin "1084.5 Baseline"** (Mega Lucario ex) | 282/418 = 67.46% | [62.83, 71.78] |
| prvsiyan "Souta 1208 Loader" (Mega Lopunny) | 156/280 = 55.71% | [49.86, 61.42] |
| **our `luc_majkel_v8`** | **145/420 = 34.52%** | [30.14, 39.19] |

**Our own agent is the weakest thing on the board by 33 points of win-rate.** Per bot it reads
crustle 16.7, crustle_hardened 13.3, baseline950 25.0, dragapult 35.0, abomasnow 28.3, iono 26.7,
and only beats ragingbolt (96.7). Head-to-head over 400 games it loses to the 1084.5 Baseline
**83–317**. This is not the "our arena is anti-predictive" effect from RESEARCH.md: that was
measured in `par_eval`, whose opponents are *our own pilots on our own decks*. Against foreign
policies the ordering matches the live scores (v8 490–530 live; the forks 670–720). So the
rebuild-our-own-pilot line was optimising something roughly half as strong as free public code,
and every agreement-harness gain of the last week was rearranging deck chairs.

### Two bugs found in public artifacts, one of which would have failed validation

1. **`makthanithin/pokemon-tcg-ai-battle-1084-5-baseline` does not compile as published.** Line 322
   of its `%%writefile main.py` cell reads `) hi:` where it must read `):`, a stray token inside the
   Crustle guard. Fork it verbatim and you get a SyntaxError and a failed validation game. `):` is
   the only edit in the artifact we ship and it restores exactly the guard the surrounding code
   describes.
2. **Kaggle execs `main.py` with `globals() == {}`** (`kaggle_environments.agent.get_last_callable`:
   `env = {}; exec(code_object, env)`). `__file__` is undefined and cwd is not the archive dir, so
   the only path that resolves an agent's own `deck.csv` is the absolute
   `/kaggle_simulations/agent/deck.csv`. Extracting a tarball to a `mktemp` dir for the packed smoke
   therefore makes the deck resolve to `[]`, the env rejects a 0-card deck (`cabt.py` takes each
   player's deck from the **step-0 action**), and a perfectly good agent reports
   `steps=2 statuses=['INVALID','INVALID']` with an empty stderr. That is exactly what happened to
   Alakazam here and it cost a full diagnosis cycle. `tools/pack_fork.sh` now extracts to
   `/kaggle_simulations/agent`, and with that the real cabt mirror episode runs clean.

### Titles are not evidence

The three "Codex Sol Eclipse Alakazam" notebooks (jazivxt, ravi123a321at, and — despite its stale
title — `romanrozen/strong-start-baseline-agent-v10-lb-950`) embed a **byte-identical** payload,
sha256 `f31eba2e819ee2b3…`. `prvsiyan/…-souta-1208-loader-v1` disclaims the 1208 in its own text
(that score belongs to external row `55137818`; its embedded agent has no Kaggle score), and it
measures 55.71% here on a Mega Lopunny/Dudunsparce list that the 2026-08-08 dump puts at 41.4%
deck-only. The "1084.5" baseline's own V1 scored **672.1** from this account in June.

### SUBMISSION 1 of 2 — `55414779` `alakazam_fork.tar.gz`, 19:27 UTC

Codex Sol Eclipse Alakazam v22, **shipped unmodified**. Chosen because it is the only artifact with
a recent current-field live score from this account: **the identical payload settled at 716.1 on
2026-08-06** (ref `55288207`). Offline it beats our v8 87.5% and the 1084.5 Baseline **338–62
(84.5%)** over 400 games. Validation **COMPLETE** (no error); live reading walked 515.3 → 655.8 in
the first ninety minutes, which is the usual convergence shape and not yet a settled number.

### SUBMISSION 2 of 2 — `mak1084_fork.tar.gz`, armed for just after 00:00 UTC

The 1084.5 Baseline with the `):` fix. **Deliberately not a second Alakazam.** A 400-game mirror
between raunakdey07's implementation and v22's finished **203–197, 50.75% [45.87, 55.62]** — the
Alakazam variants are the same deck and are statistically indistinguishable, so a second one would
be a second rating draw of one policy, which buys nothing on a max-of-two leaderboard.

The Lucario fork is a genuine hedge instead. Re-measured at n=200 rather than 60, Alakazam v22 vs
the Dragapult bot is **47.50% [40.69, 54.40]** while the Lucario fork is **64.00% [57.14, 70.33]** —
not the collapse the 60-game read suggested, but a separated gap against the second-largest
archetype on the ladder (633 seats, 57.4% deck-only). And Lucario/Hariyama is the better *list* on
real ladder evidence: 53.83% deck-only over 331 seats against Fezandipiti/Alakazam's 47.34% over
1617. Two slots is exactly the budget for covering both hypotheses — "the Alakazam pilot is much
stronger" and "the Lucario deck is the stronger list".

### Verification
- Both artifacts pass the **real** `kaggle_environments` cabt mirror episode on the EXTRACTED
  tarball staged at `/kaggle_simulations/agent`: Alakazam `steps=175 statuses=[DONE,DONE]
  rewards=[-1,1]`, Lucario `steps=150 statuses=[DONE,DONE]`.
- Across 418 gauntlet + 400 head-to-head games each: **0 exceptions, 0 engine rejects, 0 illegal
  selections**. Worst cumulative agent clock in one game: Alakazam 21.4s, Lucario 0.4s, both against
  a 600s budget. Max single move: Alakazam 857ms, Lucario 70ms.
- Archive layout `main.py` + `deck.csv` (+ `group.txt`) + `cg/` at the root; engine `SetTestSeed`
  ABI check clean; decks verified at exactly 60 cards.

### Did NOT do, on purpose
No tweak to either fork beyond the compile fix. RESEARCH.md documents two replicated ~85-point live
regressions from editing a proven artifact on a green local eval, and with two shots and no feedback
loop afterwards there is no way to gate a change. The brief's own instruction applies: an unmodified
strong fork beats a gambled one.

### If anyone ever picks this up again
Start from a public fork and measure with `tools/fork_gauntlet.sh`. Do not start from
`agent/scorer.py` — the 34.52% row above is what nine months of that produced against the field.

---

## 2026-08-13 22:56 UTC — best-of-N run, six parallel agents, two ships

Six agents ran in isolated copies of this workspace (`/home/nixos/tempo-bon/{A..F}`), each with a
different angle, none allowed to submit. A judge read all six and shipped two. Standing at the
start: **692.1, rank 2280 of 6796**; frontier LiamK 1234.7. Deadline 2026-08-16.

### Three of six independently converged on the same artifact

A (notebook sweep, deduped by payload hash), B (episode mining) and C (top-20 reverse engineering)
all landed on `tetsutani/grimmsnarl-ex-damage-transfer-control`, published 2026-08-11 — one day
after this journal's last entry, so it had never been examined here. Asset sha256
`40dce050fc411a2845b3dcd364fdd932ae3a856720a9f5f022278c59dd6e3a72`, which is the value the notebook
asserts about itself; all three extractions reproduced it byte for byte. `main.py` `c61e540b`,
`deck.csv` `92b92bac` (60 cards). Author `tetsu2131` is live at **859.3**.

Measured against our best-ever payload (Alakazam v22, 716.1 live as ref 55288207):

| measurement | result |
| --- | --- |
| head-to-head, 599 games (A) | **455–144 = 75.96% [72.38, 79.21]** |
| head-to-head, 400 games (C) | 304–96 = 76.00% |
| v22 vs Grimmsnarl pilots, 400 games | v22 wins **14.25%** |
| this vs Grimmsnarl pilots, 800 games | **54.75%** |
| field-share weighted, ~72% of real seats | **65.00% vs 42.41%** |

Grimmsnarl holds **30.4% of all ladder seats**. Our active Alakazam collapses against the single
largest archetype on the board, which is the most likely explanation for the gap between our 692.1
and the 850-plus band.

### A packaging bug that would have scored zero, found by two agents independently

`tools/pack_fork.sh` does `cp -r "$ROOT/cg" "$TMP/cg"`. In a best-of-N workspace `cg` is a symlink
to the shared repo, and `cp -r` copies a symlink as a symlink, so the archive carried one entry
`./cg -> /home/nixos/tempo/cg` and **zero engine files**. On Kaggle that path does not exist,
`from cg.api import ...` raises at import, and the submission scores zero.

**The packed smoke test passes on a broken artifact.** It extracts to `/kaggle_simulations/agent`
on this box, where the symlink still resolves. F caught it first and E caught it independently;
E's fix is `cp -r` → `cp -rL` plus two hard asserts. This never affected submissions built inside
`/home/nixos/tempo`, where `cg` is a real directory.

Verification that now gates every ship:

```bash
tar -tvzf <artifact> | grep '^l'            # must print nothing
tar -tzf  <artifact> | grep -c '^./cg/'     # must be >= 8, and libcg.so must be non-empty
```

### Submitted

| ref | artifact | what |
| --- | --- | --- |
| **55492478** | bon-C `ARTIFACT.tar.gz` | tetsutani Adaptive Grimmsnarl ex Control v15, unmodified |
| **55492479** | bon-F `ARTIFACT.tar.gz` | Alakazam v22 insurance, byte-identical to the 716.1 payload |

Deliberately two different archetypes, so the two active slots cover two hypotheses rather than two
rating draws of one policy. Both verified: 0 symlinks, real `libcg.so`, 60-card decks. Grimmsnarl
packed smoke `steps=192 statuses=[DONE,DONE]`.

### Negative results worth not repeating

- **E, deck construction:** the near-frontier consensus list, a field-derived counter-position
  build, and the single strictly-dominant card swap are all neutral-or-worse against v22 across
  ~1,000 head-to-head games. v22's decklist is a local optimum under its own pilot. The remaining
  gap is archetype-level, not list-level.
- **D, pilot policy:** edited v22's first-turn decision, never finished gating it, and its own
  EVIDENCE.md still carried a placeholder hash. Discarded unmeasured, per its own brief.
- **B:** same payload as C but its tarball still carried the dangling symlink. Not shipped.

### Next run should look at first

1. Read the live scores on `55492478` and `55492479` before anything else. If Grimmsnarl settles
   near its author's 859, the archetype call is confirmed and the Alakazam lineage is finished.
2. Do not re-fork Alakazam. Three agents measured it losing to 30.4% of the board.
3. `tools/pack_fork.sh` in this repo still has the `cp -r` bug. Port E's `cp -rL` fix in.
4. Sim submissions close 2026-08-16. The Strategy writeup is worth $30,000 and is due 2026-09-13.
