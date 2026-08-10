# Leaderboard notes

## Us

**Team "zhang et al."** (teamId `16401588`) — `alancai27, mger10, stepheneshundanquah, thtennant,
tomiwaakingbade`. Submission history is shared across all five.

| date | rank | score | active pair |
|---|---|---|---|
| 2026-08-09 | **2042 / 6677** | 716.1 | 55288207 Codex Alakazam (716.1) + 54835679 crustle v9 (693.7) |

Both active slots were holding entries *below* our own proven 775–795 wall — the wall had simply
scrolled out of the top-2 active window. Submitted 55389333 (proven crustle reconstruction) on
2026-08-09 to reclaim a slot; expect ~785 and a large rank jump if it converges as before.

## Field, 2026-08-09 (top 20 of 6677)

| # | team | score |
|---|---|---|
| 1 | Majkel1337 | 1215.7 |
| 2 | M Sato | 1185.5 |
| 3 | AlphaStarmie | 1180.2 |
| 4 | palsystem | 1179.8 |
| 5 | Dipam Chakraborty | 1172.2 |
| 6 | James Cox & Henry Chao | 1170.7 |
| 7 | Thai | 1154.8 |
| 8 | Raihan Ramadistra | 1146.0 |
| 9 | flg | 1131.7 |
| 10 | Arthurs Torres24 | 1119.0 |
| 11 | sadwat | 1117.8 |
| 12 | 🫣🤧 | 1116.0 |
| 13 | @kdcyberdude | 1110.9 |
| 14 | Pokemon Siuuuu | 1110.6 |
| 15 | LiamK | 1106.5 |
| 16 | vvs | 1106.1 |
| 17 | wwww…w | 1099.9 |
| 18 | KawattaTaido | 1098.7 |
| 19 | Luca | 1097.3 |
| 20 | Octavi Grau | 1096.1 |

**The gap is the story.** Top-8 (the prize cut) is ~1146+. Our best-ever score from any team
member is 948.1 and our best *repeatable* artifact is ~785. The rules-pilot approach that produced
everything in our history tops out around 795 and has now failed to improve four separate times.
Closing ~430 points needs a different method, not another hand-written matchup branch.

Top of the board is dense: #1 to #20 spans only 120 points, so the leaders are likely converging
on similar strong approaches. Worth identifying what `Majkel1337` / `M Sato` / `AlphaStarmie` are
actually doing (`AlphaStarmie` naming hints at an AlphaZero-style Starmie pilot — we have a
half-built self-play/MCTS stack in `net/`, `train/`, `engine_rs/` that was never proven to beat
the BC baseline).

## Update 2026-08-09 (late) — the wall fell out from under us

| date | rank | score | active pair |
|---|---|---|---|
| 2026-08-09 21:20 | 2037 / 6678 | 716.1 | 55389333 crustle-proven (**462.4**) + 55288207 Codex Alakazam (716.1) |
| 2026-08-09 21:30 | — | pending | 55389997 lucario-majkel-aug (**new**) + 55389333 (462.4) |

**The reconstructed "proven" Crustle wall converged to 449.2 → 462.4, not 775–795.** The rebuild is
faithful; the archetype is dead (Kangaskhan/Crustle = 43.96% in the 2026-08-08 real-field dump).
See RESEARCH.md. Submitting 55389997 evicted the 716.1 — a deliberate, budgeted cost to run the
single-variable deck-swap experiment (same pilot, 43.96% archetype → 54.3% archetype).

## Field, 2026-08-09 late (top 10 of 6678) — and what they actually play

| # | team | score | archetype (from the 08-08 dump) |
|---|---|---|---|
| 1 | Majkel1337 | 1218.7 | Lucario / Hariyama |
| 2 | M Sato | 1190.2 | Lopunny / Froslass |
| 3 | AlphaStarmie | 1180.4 | Fezandipiti / Alakazam |
| 4 | palsystem | 1179.8 | Hydrapple / Teal Mask Ogerpon |
| 5 | Dipam Chakraborty | 1174.3 | Dragapult / Meowth |
| 6 | James Cox & Henry Chao | 1166.5 | Kangaskhan / Teal Mask Ogerpon |
| 7 | Thai | 1158.9 | Kangaskhan / Latias |
| 8 | Raihan Ramadistra | 1139.9 | — |
| 9 | flg | 1133.7 | — |
| 10 | @kdcyberdude | 1119.3 | — |

Prize cut (top 8) ≈ **1140**. Field median 628.1; 50th place 1037.1.

**The leaders do not share one deck** — seven different archetypes across the top seven. So the
120-point-wide top of the board is not a deck secret; it is *piloting quality*. Their personal win
rates (Dipam 66.3%, 213tubo 66.7%, M Sato 64.8%, Thai 62.9%) sit far above their own archetype's
field average, i.e. they out-pilot everyone on ordinary decks. That is the gap, and it is not
something a better decklist closes.

`data/meta_aug/decks/` now holds all 153 lists, so any top team's exact deck is one `cp` away.

## 2026-08-09 slot 4 — our own standing, and a caution about reading it

Active pair after this run: `55390373` (luc_majkel_v2, pending) + `55389997` (luc_majkel).
`55389333` (Crustle wall) was evicted at 540.1.

**Our refs move by >200 points within hours of submitting** — `55389997` read 698.6, then 775.6,
then 559.1 inside a single afternoon; `55389333` read 449.2 → 462.4 → 506.0 → 540.1 over the same
window. Any standing recorded here that is less than ~a day old is a snapshot of a converging
rating, not a result. Re-read before comparing two refs, and never evict a slot on a fresh number.

This also means the slot-3 headline ("+190 live from the decklist swap alone") is **unconfirmed**:
it was computed at one ref's transient peak, and at the latest readings the same pair sits ~19
points apart. Still the leading hypothesis, but the next run must re-read both refs after they
settle before building on it.

The note above still stands and is reinforced: the top seven play seven different archetypes, so
the ~400pt gap to the prize cut is piloting quality, not a decklist secret. Confirmed from a second
direction this run — Thwackey/Dipplin (59.5% real-field) goes 10.4% under our *generic* pilot,
i.e. archetype strength does not transfer without a hand-written specialist.

## 2026-08-09 end of day (slot 5)

Active pair: **55390373 (v2)** + **55390639 (v3, PENDING)**. Evicted 55389997 (v1).
Submissions used today: 4 of 5.

Same-day readings crossed over inside a single run — recorded as evidence that these are not
converged:

| ref | ~21:40 UTC | ~22:05 | ~22:15 | ~22:21 |
|---|---|---|---|---|
| 55389997 (v1 Lucario/Majkel) | 775.6 | 559.1 | 596.5 | **505.7** |
| 55390373 (v2, + verifier deck fix) | — | — | 506.8 | **572.7** |
| 55389333 (Crustle wall, evicted) | 489.2 | 506.0 | 540.1 | 540.1 |

v2 and v3 are the same pilot on the same list differing by exactly one binary decision per game
(turn order, measured at +4pp win rate over 2,200 mirror games). **That makes this pair the first
clean live A/B we have set up — let both settle before evicting either.**

## 2026-08-10 ~00:20 UTC — settled-ish readings of the v2/v3 A/B

| ref | build | reading |
|---|---|---|
| 55390639 (v3) | Lucario/Majkel + turn-order fix | **621.5** |
| 55390373 (v2) | Lucario/Majkel + verifier-deck fix | **550.7** |
| 55389997 (v1, evicted) | Lucario/Majkel baseline | 505.7 |
| 55389333 (Crustle wall, evicted) | June wall re-ship | 540.1 |

v3 − v2 = **+70.8** at ~2h age, in the direction the turn-order fix predicts (+4pp win rate). It is
the right sign but these refs are still young and this file has recorded a >200pt swing and a
crossover on same-day readings twice. **Treat +70.8 as encouraging, not established** — re-read
both before building on it. Active pair unchanged: 55390639 + 55390373 (no submission this run).

Top of the ladder for scale: Majkel1337 1203.5, M Sato 1190.8, AlphaStarmie 1189.4; the top-8 /
prize cut sits around **1128**. We are ~500 short, and §2 of STRATEGY.md is the reason: our pilot is
strong on one archetype and unusable on the 58–63% archetypes the leaders fly.
