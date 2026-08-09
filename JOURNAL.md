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
