# tempo — Strategy Track writeup

**Competition:** The Pokémon Company — PTCG AI Battle Challenge
**Agent:** `tempo` — a hand-written archetype specialist over the official engine, with a
verified-lethal endgame solver. No search at play time, no neural net at play time.

This writeup is about **method**, not about a clever card interaction. The single most useful thing
we can hand another entrant is not our decklist — it is the set of measurement instruments we built
after discovering that the obvious way to evaluate a PTCG agent is actively misleading, and the
five well-powered negative results those instruments produced.

---

## 1. The one-paragraph summary

We started where most entrants start: build a forward-model search over the engine, train a policy
net on real ladder games, and let it rip. We shipped that, measured it, and **it lost** — four
separate times, by four independent methods. What replaced it is unglamorous: a deterministic rules
pilot for one archetype, a multi-step lethal verifier for closing games, and a *lot* of
instrumentation. The instrumentation is the contribution. In particular we found that the standard
local evaluation everyone reaches for — self-play win rate in your own arena — is not merely weak
signal in this competition, it is **anti-predictive**, and we can put a number on that. Replacing it
with agreement-against-real-frontier-play found a structural dispatch bug that had been silently
costing us the opening turn of *every game we have ever played*.

---

## 2. The field, and why deck choice is not the lever

We mined the public episode dump for 2026-08-08 (`pokemon-tcg-ai-battle-episodes-2026-08-08`,
~4,670 episodes) into archetype shares, pairwise matchups and **153 exact winning 60-card
decklists** — one per team, including every top-20 team.

| archetype | share | win % |
|---|---|---|
| Marnie's Grimmsnarl / Morgrem | 30.4% | 46.4 |
| Fezandipiti / Alakazam | 17.8% | 49.9 |
| Lopunny / Froslass | 10.7% | 51.7 |
| Dragapult / Meowth | 6.3% | **58.0** |
| Kangaskhan / Latias | 2.7% | **63.2** |
| Thwackey / Dipplin | 2.0% | **59.5** |
| Lucario / Hariyama | 3.2% | 54.3 |

Two things fall out immediately.

**(a) The top of the leaderboard is not a decklist secret.** The top seven teams at the time of
writing play seven *different* archetypes. If a single list were dominant they would converge on it.
The ~400 point gap between us and the prize cut is piloting quality.

**(b) Deck strength does not transfer without a pilot.** We tested this directly rather than
assuming it. Flying the field's *best* deck (Dragapult/Meowth, 58.0% real-field) with our generic
policy scores **0 wins in 32 games** against our own specialist — while the Dragapult *mirror* is
~44%, so the deck itself functions in the engine; we simply cannot assemble a Stage-2 evolution
combo without hand-written guidance. Thwackey/Dipplin (59.5% real-field, no Stage-2 line at all)
does better but still only **10.4% ± 8.6**. Adopting a strong archetype therefore costs an entire
new specialist, and that is the central structural constraint on our method.

This is worth stating plainly because it is the trap the competition is built around: **deck list
and decision policy are one joint problem.** A "better deck" you cannot pilot is a worse deck.

### 2a. The measurement that settles it: 320 leaderboard points on an identical 60 cards

We ship a copy of the rank-1 player's Lucario/Hariyama list. In the 2026-08-09 dump, **Majkel1337
(rank 1, 1203.5) played 23 of his 26 games on a list byte-identical to ours**, so the list is not
stale and not misread. Three further teams ship the *same 60 cards* — and they sit at **892.4,
879.9 and unrated.**

> **The same decklist spans 320 leaderboard points across four teams.** Whatever separates rank 1
> from rank 844, it is not in the deck.

If you are choosing between tuning your list and tuning your policy, that number is the answer.
We have spent slots on both; only one of them has ever moved our score.

### 2b. Archetype win rate is confounded by pilot strength — but less than you would guess

The table above is what everyone computes, and it is not a deck ranking: an archetype's win rate is
partly the deck and partly whoever plays it. Marnie's Grimmsnarl wins **41.9%** among 850–1000 rated
seats and **50.7%** among 1000+ seats, on the same 60 cards.

We de-confounded it properly rather than trusting that band split (which overstates the problem —
banding the *seat* does not control who it played, and a low-band seat is largely playing up). For
each decided game, with `r` the pilots' public-leaderboard ratings, fit

```
P(i beats j) = sigmoid( a·(r_i − r_j)/400 + d[arch_i] − d[arch_j] )
```

over 4,555 games, with confidence intervals bootstrapped over **games** — not seats, since the two
seats of one game are a single observation and resampling seats would halve the interval. `a` is
a built-in sanity check on the rating join: it came out **0.352 (95% CI 0.212–0.489)**, i.e. a
400-point edge is worth 58.7%.

**Verdict: the confound is real but small — mean |raw − deck-only| = 2.4 points, largest relative
reshuffle 4.7.** The naive table was usable after all. That is a negative on our own hypothesis and
we report it as one.

| archetype | seats | raw win% | deck-only win% | 95% CI |
|---|---|---|---|---|
| Kangaskhan / Latias | 79 | 63.3 | 61.2 | 50.6–68.9 |
| Dragapult / Meowth | 633 | 59.4 | 57.4 | 53.7–60.9 |
| Lucario / Hariyama | 331 | 55.9 | **53.8** | 48.4–57.6 |
| Fezandipiti / Alakazam | 1617 | 49.9 | 47.3 | 44.6–50.3 |
| Marnie's Grimmsnarl | 2926 | 46.6 | 44.1 | 41.7–46.3 |
| Kangaskhan / Crustle | 332 | 38.9 | 37.3 | 32.4–43.0 |

Two consequences we act on. The archetype that carried us to 776–795 in the June field
(Kangaskhan/Crustle) is now **the worst deck in the field at 37.3%** — a live score is a rating
against the field *of the day*, and it decays as the field improves. And the **entire ceiling on a
perfect archetype switch is about +3.6 points** of win rate (53.8 → 57.4), against a deck we pilot
at 0/32. The lever everyone reaches for first is smaller than it looks.

### 2c. One caveat if you replicate this: a joined rating goes stale in days

The same model on the *previous* day's dump, joined to the same leaderboard, gives a = 0.185 (CI
0.02–0.37), and the higher-rated seat wins only 53.7% overall and **50.5% in the games with a 400+
point gap**. The leaderboard score reflects a team's *current* two active submissions, not the agent
that played a two-day-old episode. Join ratings to the freshest dump you have, and treat `a` as the
diagnostic that tells you whether your join survived.

### 2d. A practical note: you do not need to parse the dump

The dump is ~21 GB unzipped and a replay is ~6 MB, but `info.TeamNames`, `rewards` and both 60-card
deck registrations all live in the **first few hundred KB** — the key order is
`configuration, description, id, info, …, rewards, …, steps`, and the deck registrations are the
first actions inside `steps`. Reading 512 KB per file and regexing those three things out turns a
20-minute full parse into about a minute, which is the difference between "check the frontier's list
every run" and "check it when there is time." We validated it against the full parse: **4,428 games
and 238 rating-join drops, identical to the byte**, with 3 of 4,668 replays unusable.

---

## 3. The result we would most like other entrants to have: your arena is lying to you

Every agent-vs-agent competition tempts you to build a local arena — your candidate against your
previous build, thousands of games, tight confidence intervals. We built one. It is
**anti-predictive**, and here is the measurement that shows it:

> Our proven Kangaskhan/Crustle control wall beats the field's most popular deck (Grimmsnarl, real
> August list) **93.8%** in our arena — while scoring **462** on the live ladder.

The mechanism is not subtle once you see it: *the only opponents in your arena are your own bots.*
A local win rate therefore measures "which policy best exploits our own heuristics", which is very
nearly the opposite of "which policy is strong against strangers". Every green-local/red-live
regression we suffered has this shape:

| change | local paired eval | live delta |
|---|---|---|
| Crustle pilot v8 | +2.4pp aggregate over 9 arms, 200 games/arm | **−85** |
| Crustle pilot v9 | +9.2pp on its target arm, disjoint CIs | **−85** |
| Crustle pilot v7 (clean rebuild) | green | **−120** |

Three well-powered local wins, three live losses, replicated. We now treat a local arena win rate as
evidence about **robustness and relative determinism only**, never about strength or deck choice.

### What we replaced it with

**Real-field agreement.** We harvest every decision made by *frontier players of our own archetype*
from the public episode dump — 11,447 real observations, 4,074 of them from winning sides — and
replay each one through **the deploy entry point**, bucketed by decision type. This asks a question
the arena cannot: *given the exact board a 1200-rated player faced, do we choose what they chose?*

It is a relative instrument (it compares two builds on identical decisions), it is real-field rather
than self-referential, and it is cheap: 10,563 positions in a couple of minutes. 99.1% of the corpus
routes through the specialist we actually ship, so it measures shipping code.

Baseline for the agent described here:

| bucket | n | agree |
|---|---|---|
| all | 4074 | 53.7% |
| main | 2530 | 45.5% |
| **main/swing-or-end** | 75 | **88.0%** |
| main/attack-choice | 604 | 36.4% |
| sub-selects | 1502 | 67.0% |

**The caveat matters as much as the number.** Single-decision agreement over-penalises benign turn
ordering: if the elite attacked immediately and we play a card first and attack second, that scores
as a disagreement even though the turn is identical. So we judge changes on the confound-free
buckets (`swing-or-end`, where the only options are attack/end/retreat) and on **whether any bucket
regresses** — never on the headline percentage alone. Several apparently alarming numbers dissolved
under this discipline; see §5.

---

## 4. The bug that justifies the whole method: dispatch is blind before the board exists

This is our best single finding, and we would not have found it without real-field agreement.

Our scorer dispatches to an archetype specialist by calling `is_<archetype>_deck(state)`, which
detects the archetype **from the cards visible on our own side of the board**. That is a reasonable
design — until you notice *when* the engine asks the turn-order question.

`SelectContext.IS_FIRST` ("would you like to go first?") is asked **before the opening hand is
dealt.** Active, bench, hand and discard are all empty. Detection returns False. The specialist is
bypassed, and a generic fallback decides — on **93 of 93** real IS_FIRST positions in the dump.

The generic rule it fell through to had never been measured: *"going second is often better for a
setup deck."* Our repo held **three conflicting opinions** on this question — the specialist said
go first, the entry-point fallback said go first, the generic scorer said go second — and the
untested one won every time, because it was the only one on the live path.

We answered **NO in 93 of 93 real positions. Real ladder players of the same archetype answered YES
in 91 of 93.** Agreement: **2.2%**.

Then we tested whether the elites were actually right, rather than assuming it. We built a forced
mirror A/B: identical deck and identical policy on both seats, *only* the turn-order answer forced,
arm-swapped and seat-swapped to cancel any first-player bias in our own harness.

| run | forced YES (asked player wins) | forced NO |
|---|---|---|
| n=1000 | 51.8% ± 4.4 | 47.0% ± 4.4 |
| n=1200 | 56.0% ± 4.0 | 45.5% ± 4.0 |

Pooled: the player who went first won **1187 of 2200 = 54.0% ± 2.1 (z=3.7, p≈0.0002)**.

**The fix is structural, not a tuned constant.** We ship our own decklist inside the submission, so
there is no need to *infer* our archetype from an empty board — we read it. Detection now falls back
to the bundled deck list when nothing at all is visible on our side, guarded so it can only fire
before the opening hand exists. IS_FIRST agreement went 2.2% → 97.8%; on 4,074 elite decisions no
other bucket regressed.

**The transferable lesson is bigger than one decision.** Any decision your agent takes *before the
board reveals which deck you are playing* is being made by whatever generic default your dispatch
falls through to — and that default is, almost by construction, the least-tested code you ship. If
you have archetype dispatch, audit it at `IS_FIRST` and `MULLIGAN` first.

---

## 5. Five negatives, each well powered

Negative results are the bulk of our output and we think they are the honest bulk of anyone's. Each
of these closed a line of work that looked obviously promising.

**(1) Search does not beat the heuristic.** Four independent refutations: a determinized UCT
submission at 6s/move scored **560** live while contemporaneous rules pilots scored 776–795; a
native Rust MCTS core with 10× the simulations scored **529**; a static-leaf lookahead sweep landed
at 38–42% in paired play; and finally, layering net-guided PUCT *on top of* the heuristic prior
(search only on main single-selects, rich heuristic everywhere else) went **23.3% ± 10.7** on one
deck and **50.0% ± 12.7** on the other. That last one is not vacuous — instrumented over full games,
the search **diverges from the heuristic on 72.1% of qualifying decisions** and still only draws.
Mechanism: strategy fusion and phantom lethals from determinized draws, plus a leaf evaluation
weaker than the heuristic's implicit tempo knowledge.

**(2) Prize-trade economics is not our bottleneck — at either level.** Policy level: on pure
swing-or-end decisions we agree with frontier play **88.0%**; among multi-attack decisions we pick a
different attack **6 times in 133** (3 each way — noise); of 149 spots where we attacked and the
elite kept developing, **124 are provably correct** (112 where the lethal verifier proved a
game-winning line, 12 scorer game-winning swings), leaving **25 of 2,530 main decisions (1.0%)**
genuinely premature. Deck level: across the 17 archetypes with ≥100 games joined to real decklists,
`corr(win%, max prize liability) = −0.13` — nothing — and `corr(win%, number of multi-prize
Pokémon) = **+0.54**`. **Decks carrying more 2- and 3-prize threats win more.** "Build a low-prize
deck" is a dead idea, and our 3-prize Mega-ex is not a handicap.

**(3) A documented safety rule was wrong.** Our specialist's header had promised for months: *"when
we are at our last 2–3 prizes, do not over-expose the 3-prize Mega-ex."* The helper was written and
never called. We implemented it and ablated it on 4,074 real decisions behind a switch: it moved
**9 decisions away from frontier play and 0 toward it.** Reverted. A one-attacker aggro deck that
refuses to promote its attacker just forfeits tempo, and the elites promote it anyway. This is the
cleanest example we have of why a plausible-sounding rule needs a measurement before it ships.

**(4) In-turn energy/retreat/bench sequencing is not a leak.** Raw agreement made attach-to-bench
look catastrophic at **18.6%** — pure turn-ordering confound. Conditioning on decisions where the
elite *and* we both attached at that same point, target agreement is **89.8% (149/166)** and we
bench energy 37.3% of the time against their 40.4%. A whole-turn audit (which both agreement
harnesses are structurally blind to) finds we end a turn with the attachment unspent on **3.6%** of
turns, with a benchable Basic still in hand on **3.0%**, and pay a retreat without attacking on
**0.6%**. All 24 real positions where the elite attached and we swung instead are KO swings, 14 of
them provably taking the opponent's last prizes.

**(5) Robustness is not our bottleneck either** — see §6, which is this run's contribution.

The reason we report these is that each one, before measurement, was somebody's confident intuition
about what was wrong with the agent. Four out of five were false.

---

## 6. Verification: what we do before anything ships

A submission that errors scores zero regardless of how well it plays, so this is a gate, not a
nice-to-have. Three layers, all on the **packed artifact** rather than the repo tree — loader
context differs, and we have lost a submission to exactly that (`__file__` undefined under `exec`).

**Layer 1 — real-field play probe.** Full real-engine games driving *both* seats through the deploy
entry point, against **all 153 real ladder decklists** mined from the episode dump, with 12% of
moves perturbed to a random *legal* selection to force pathological states. Every decision is
asserted on: no exception, a legal selection (distinct ints in range, length within
`[minCount, maxCount]`), the engine actually accepted it, per-move latency, and cumulative agent
wall-clock against the 600s game clock.

> 920 games / **134,454 agent decisions**: 0 exceptions, 0 illegal selections, 0 engine rejects,
> 0 hangs, 0 moves over 1s. Latency p50/p99/max **0.33 / 232 / 268 ms**. Worst cumulative game
> **6.1s of 600s** — about 1% of the clock.

**Layer 2 — context coverage.** Layer 1 is a sampling argument, and sampling has a blind spot: the
engine defines **49 `SelectContext` values** and a normal game asks only a fraction of them. Any
context never reached is code shipped unexecuted. So we measure it:

> A 1,224-game field sweep reaches **31 of 49** contexts over **188,103** live decisions. Sampling
> 400 real episodes from the public dump, the actual ladder exhibits **31** distinct contexts over
> 130,603 decisions. The sets differ by two entries at the tail: our probe never reaches
> `TO_DECK_ENERGY` (3 occurrences in 130,603 real decisions, 0.002%), and reaches `DISABLE_ATTACK`,
> which the sample does not contain.

That is the statement we wanted: **self-play against the real field's decklists reproduces the real
field's state distribution**, so Layer 1's clean result is not an artifact of narrow coverage.

**Layer 3 — adversarial observation mutation.** For the contexts real play *doesn't* reach, we
manufacture them. Every captured observation is rewritten into states the engine could hand us but
our games never produced: the same board asked under **each of the 49 contexts**; degenerate
`minCount`/`maxCount` combinations including `(0,0)`, `(n,n)`, `(n+1,n+1)` and the contradictory
`(2,1)`; empty and truncated option lists; optional keys nulled and dropped; bench, hand, discard,
active, prize, energy zone and stadium stripped to empty; turn 0, turn 9999, and a *decided* game
still asking for a move; individual option-record fields blanked.

A mutated board is not necessarily a board the engine would ever produce, so a *bad choice* on one
means nothing and we assert nothing about choice quality. We assert only the two things a submission
is actually killed by: **did it raise**, and **did it return something the harness cannot use**.

> **325,070 mutated observations: 0 exceptions, 0 illegal selections, max latency 20 ms.**

**Plus:** 10,563 real ladder observations replayed through the deploy entry point with 0 agent
errors; cold start (import through first decision) **0.22s**, consistent with the field's
`remainingOverageTime` opening at 599.62 of 600; and a packed mirror smoke test in
`kaggle_environments` on the *extracted tarball* confirming both seats reach `DONE` with real
rewards — which is the same self-play validation game the competition runs on submit.

---

## 7. What we would do with more time, stated honestly

Our agent is a strong pilot of one archetype and a mediocre pilot of every other. The measurements
in §2 say the ceiling on that is real: the field's best decks are 58–63% win rate archetypes we
cannot fly, and closing that gap means writing another specialist, which is weeks of work per deck
and historically lands *below* the specialist it replaces on its first outing.

The direction we believe in — and did not have time to finish — is to make specialist authoring
cheap rather than to author more specialists. Every instrument in §3 and §5 is archetype-agnostic
except for its corpus: the agreement harness needs a set of frontier decisions for the target
archetype, and the episode dump contains those for every deck in the meta. A specialist whose
constants are *fitted to frontier agreement* rather than hand-tuned, then gated on the confound-free
buckets and the §6 robustness stack, is a repeatable pipeline instead of a bespoke effort. We have
the corpus, the harness and the gate; what we do not have is the remaining days.

We also want to flag the failure mode that cost us the most, because it is easy to walk into: we
spent weeks improving an agent against a metric that was pointing the wrong way, and the thing that
finally exposed it was not a better model — it was asking *what did a strong player actually do on
this exact board*, and being willing to publish the answer when it was 2.2%.
