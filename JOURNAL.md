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
