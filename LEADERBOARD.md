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
