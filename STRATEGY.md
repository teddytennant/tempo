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

## 5b. The one place search *does* pay, and the condition it has to meet

§5(1) says search does not beat the heuristic, and we stand by every number in it. But all four of
those refutations refute the same object: a search whose leaf is an **estimate**, replacing the
heuristic's ranking. There is a second kind, and it behaves completely differently.

Our agent carries a verifier that searches the engine's own forward model for a sequence of actions
that **wins the game this turn**. Its leaf value is the engine's terminal result. It cannot be wrong
about the value of a leaf, so the mechanism that kills estimate-search — a leaf evaluation weaker
than the heuristic's implicit tempo knowledge — does not apply to it.

We had never measured its coverage. It turned out to be running on a fraction of the positions where
it could have spoken, held back by two cost filters that had never been checked against anything:

- **"Only search when the opponent has ≤2 prizes left."** A single knockout is worth up to **three**
  prizes — any Mega ex. Three, not two, is the largest prize count from which one KO ends the game.
- **"Only search when an attack is already on the menu."** This defeats the purpose. The lines worth
  searching for are exactly the ones that must attach energy, evolve, or fire an ability *before* an
  attack becomes available; those start from a menu with no attack on it.

Replaying 2,500 real ladder decisions with one axis widened at a time: the prize gate hid **23**
game-winning lines, the attack requirement hid **28**, and opening both took proven wins from **86 to
140** with p99 latency essentially unchanged (140.6 → 144.1 ms). Two other axes — search depth and
the node/time budget — we widened just as far and found **nothing** (depth 10 → 18 found *fewer*
lines, losing one to the clock). Worth knowing which knobs are dead.

Because the proof is taken under a determinized model of our own deck, a line needing a lucky draw
could be a phantom. We check that directly: segment the corpus back into real games and ask how far
each claim sits from the end of the game it was made in. **Median: 0 turns.** 87% of widened claims
sit within one turn of the game actually ending, against 90% for the pre-existing gate. The claims
land where games end.

### And then widening it alone made the agent worse

This is the part we think is worth other entrants' attention. Wider search, sound proofs, clean
robustness — and agreement with frontier play **fell** (all 53.7 → 53.0, main 45.5 → 44.3,
attack-choice 36.4 → 34.8).

The diagnostic that explains it is three lines of engine calls. For every position the widening newly
proves, fork the game, play **the agent's own move**, and search again:

| what the heuristic did | count |
|---|---|
| kept the win provable | **63** |
| played a card that made the win unprovable | **6** |
| undecidable | 0 |

The search was right 69 times and *useful* 6 times. In the other 63 it was overriding a strong prior
on a turn that was already won — deviation with no upside, which is precisely the failure mode §5(1)
identifies, arriving through a door we thought was closed to it.

So the fix is not about the search at all. The verifier now runs **after** the heuristic, is handed
the heuristic's answer, applies that answer in the fork, and **stays silent if the win is still
provable**. It speaks only where it can prove the prior is wrong. Agreement with frontier play then
moves the other way: all **53.7 → 54.5**, main **45.5 → 46.8**, attack-choice **36.4 → 37.6**, with
the pure swing-or-end bucket unchanged at 88.0.

**The general form, which is the part that transfers:** a strong hand-built prior deserves protection
from search even when the search is *provably correct*, because most of the time the prior already
achieves what the search proves and the deviation is free downside. Earlier work in this repo tried
to buy that protection with a tuned score margin. A proof buys it exactly, for the cost of one extra
fork.

### And it was blind below the top-level menu

The verifier was asked its question only at the top-level action menu. That was an assumption, not a
requirement — the engine's search API will start from any observation the agent is handed. So the
moment the heuristic decided to *play a card*, the engine's follow-up question (**which** card,
**which** target) was answered with nothing checking that the answer preserved a proven win.

Over 3,607 real single-answer sub-selects: a win this turn is provable from **186** of them, the
shipped answer keeps it in **174**, and throws it away in **12**. The 93.5% preservation rate
replicates the top-level finding exactly — prior protection is load-bearing at every depth.

The 12 come with corroboration from outside the proof. Our corpus is decisions from games the
frontier player **won**, so we can ask what they did in those same positions: they played the
verifier's answer **7 times**, and ours **once**.

## 5c. The mirror image does not work, and the reason generalises

The obvious next step is to flip the polarity. If proving "I win this turn" pays, prove "**they** win
next turn" and avoid it. That is the entire defensive half of prize trading — knowing when a trade is
correct is knowing what they get to do back. We built it, measured it, and did not ship it.

The construction is sound and we would defend every piece. Fork at the decision, apply the move that
ends our turn, then AND/OR search their turn — OR over their choices, AND over ours — with the leaf
value again the engine's terminal result. Their hand is hidden, so inside the fork it is placeholder
basics: they may attach, retreat, use the abilities of Pokémon already in play and attack, but they
cannot play a trainer or gust something up. That is a strict **subset** of their real options, so the
model can only *miss* threats, never invent one.

It found real threats. Re-run with the opponent forbidden to attach energy inside the fork — leaving
them only what is already on their board — the counts do not move at all. Nothing rested on a
mis-modelled energy zone.

And it is useless. Two measurements say so.

**First, run the verifier on the frontier player's own move instead of ours.** It condemns their move
at **17.5%** of the positions it looks at, against **17.6%** for ours — the same rate — in games
those players went on to *win*. Sequence the corpus by turn and the reason is visible: the positives
arrive in runs of consecutive decisions inside a single turn, and the run still proves losing after
the elite's own development and their own attack. The verifier is describing the position. It is not
describing the move.

**Second, there is nothing to do about it.** A provably-safe alternative exists in **4 of 2,500**
decisions, and in none of those 4 did the elite play the alternative.

**The asymmetry is the transferable result.** An offensive proof is actionable because we are the one
who acts: "a win exists, and your move throws it away" *names the move to play instead*. A defensive
proof is a statement about what the opponent will do, and proving that they have a winning line does
not produce a move that takes it away from them. Identical engine, identical leaf value, identical
discipline — and one direction is worth shipping while the other is worth only the measurement.

**A proof is worth searching for only when we are the one who gets to act on it.**

We would also single out the cheap test that produced this, because it applies to any agent that
flags its own decisions: **re-run the flag on strong players' decisions from games they won.** If it
fires on theirs at the same rate it fires on yours, it is measuring the position rather than the
policy, and no amount of soundness will turn it into a better move.

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

## 6b. The unit of measurement was wrong: score the turn, not the decision

Everything in §3 scores a single decision against what a strong player did at that decision. That
measurement has a confound we named early, excused repeatedly, and never actually measured: **turn
ordering**. If the frontier attacks immediately and we attach energy first and attack second, we are
marked wrong twice and we played the *identical turn*. Top-level-menu agreement sitting at 46.6%
while "swing or end the turn" sits at 88.0% is exactly the shape that confound produces, and for
three weeks "it's the ordering confound" was an explanation we had no right to.

So we measured it. `turn_replay` forks the engine at a turn's **first** decision, drives our own
deployed entry point through the entire turn one search step at a time until control passes to the
opponent, and compares the two turns as **action multisets canonicalised to card identity** — play
Dusk Ball, attach a Fighting Energy to the benched Riolu, attack with Aura Jab — rather than to
option indices, which shift as a turn proceeds. Ordering is removed by construction.

Two results, and they point opposite ways.

**The confound is real and large.** Turns where neither side drew a card (the only bucket our
determinized deck cannot contaminate) match as multisets **66.7%** of the time, against 3.3% where
cards were drawn and 8.0% overall. Most of the top-level-menu disagreement genuinely is sequencing.

**And it was still hiding a real loss.** Per turn, over 199 real frontier turns, the frontier
attacks on 78.4% of turns to our 64.3%, attaches energy on 79.9% to our 58.8%, and takes 6.06
actions to our 5.07. Those gaps survive the de-confounding.

The companion instrument is the cheap one and it is the one we would hand to another entrant first.
`card_use` never forks: it asks our agent the *identical question on the strong player's own menu*
and scores every option three ways — **offered / they took / we took**. The discriminator is simple:

> A row where we sit near **zero** cannot be explained by ordering. Re-ordering a turn changes *when*
> you play a card, never whether you ever play it. A row where we are merely *lower* usually can.

On 4,000 real decisions exactly one row was near zero. Premium Power Pro — an item giving every one
of your Fighting Pokémon +30 damage for the turn — was on the menu **1,618 times**. The frontier
played it 256 times (15.8%). We played it **4** (0.2%). Everything else in the table (we evolve
early and they evolve late, at 96.7% against 44.0%) is ordering and should not be chased.

The cause was a guard we had written to look careful: play it only when the +30 *exactly* converts a
swing into a knockout, and only with a specific attacker in the Active spot; otherwise score it
below end-of-turn, i.e. never. On the frontier's own menus that guard is satisfied 83 times out of
2,552.

**Then we did the thing we should have done when we wrote the guard: we derived their rule from
their own behaviour instead of inventing one.** Bucketing those 2,552 offers:

| the position when it was offered | offers | they played it |
|---|---|---|
| an attack is on the menu, and +30 converts a KO | 136 | 41.9% |
| an attack is on the menu, +30 does not convert | 386 | 29.0% |
| an attack is on the menu, already lethal anyway | 963 | 23.7% |
| **no attack on the menu** | 1067 | **3.3%** |
| Active = our main attacker / Solrock / Hariyama | 1281 / 675 / 185 | 19.8% / 18.2% / 17.8% |

One feature — *are we swinging this turn* — separates 3.3% from 23.7–41.9%. The knockout conversion
we had built the entire guard around is a 1.4× tie-break. The attacker restriction is worth nothing:
all three are Fighting Pokémon and the card boosts them identically. And the reason a strong player
can be this liberal is card economy, not damage maths: the deck runs four copies behind two draw
engines, and a buff that expires at end of turn is worth zero in hand.

Two things generalise beyond one card:

1. **Pick the unit of measurement that matches the decision.** A greedy per-decision scorer is
   evaluated per decision, so a whole class of "we never do this at all" errors is invisible to it —
   they look like ordering noise. Only scoring the turn separates them.
2. **When you write a conditional rule, check how often the condition fires on real positions.** Ours
   fired on 3% of the positions the card was offered in. That number was always available, cost
   nothing to compute, and would have caught the bug the day it was written.

The honest scoreboard for the fix: agreement over 4,074 frontier decisions moves 2,223 → 2,235 with
a same-session baseline spread of 0–3 decisions, the two ordering-free buckets do not move, and the
ordering-immune take rate goes 0.2% → 5.6% — a third of the gap, not all of it.

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
