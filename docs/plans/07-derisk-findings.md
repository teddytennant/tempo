# De-risk Findings (resolved from the real engine)

Downloaded the official engine + card data (Kaggle `pokemon-tcg-ai-battle`). Key results that
reshape the plan:

## Fact #1 — Forward model: SOLVED by the engine itself ✅

`cg/api.py` exposes a **native determinized-search API** backed by `libcg.so`:
- `search_begin(obs, your_deck, your_prize, opponent_deck, opponent_prize, opponent_hand,
  opponent_active, manual_coin)` → root `SearchState{observation, searchId}`
- `search_step(search_id, select)` → advance a hypothetical line → next `SearchState`
- `search_release(id)` / `search_end()` → memory reuse

You pass **predicted opponent hidden cards** (deck/prize/hand/active) straight in — i.e.
determinization is first-class — and `manual_coin` controls chance. This is exactly the forward
model the public field failed to build (their MCTS `GameSimulator` was a stub). **We do not
reimplement the rules.** The native lib is the fast, exact forward model, and it ships inside the
submission tarball, so search runs in-agent within the 10-min clock.

## Fact #2 — Compiled native code in the sandbox: confirmed ✅

The official sample submission bundles `cg/libcg.so` (and `cg.dll`) and loads it via `ctypes`. So
shipping our own compiled artifact is clearly allowed — **but we likely won't need one for the
engine.** (A compiled MCTS driver is still optional, below.)

## Fact #3 — Ladder-episode dataset for BC: TBD

Kaggle CLI has `competitions episodes` / `replay`. Need to confirm these expose top-player game
trajectories with chosen selections (the BC labels). Next step.

## Refined Rust role (correct-then-fast, per ai/CLAUDE.md)

The rules engine is the `.so`; Rust does **not** reimplement it. Rust's high-value role is a **fast
MCTS driver over the C ABI**: each `search_step` returns JSON that Python decodes via
`json.loads` + reflective `to_dataclass` — heavy per node. At thousands of nodes/move a Rust driver
calling `SearchStep` directly and extracting only needed fields gives many more sims/move →
stronger play within the clock. Build the MCTS in Python first (correct), profile, then move the hot
loop to Rust if per-node overhead dominates.

## Floor-agent baseline (thesis evidence)

Generic heuristic floor agent vs random, official sample deck both sides, real engine:
- floor (p0) vs random: **34.5%** over 200 games; floor (p1): **30.5%**
- random vs random: 51% (harness sane, ~no first-player bias)
- 0 errors / 0 unfinished / ~8 ms per game; floor's games are *shorter* than random's

A rule-based agent piloting a real combo deck plays **worse than random** — the field's "complex
decks piloted clunkily" effect, first-hand. This is the gap the learned policy closes, and a clean
data point for the Strategy Track report.

## MCTS proof-of-signal (Stage 2) ✅

Determinized UCT over the native search API (`search/mcts.py`), 40 iterations/move, random
rollouts, floor fallback for non-main decisions. Official sample deck both sides, real engine:
- MCTS vs random: **10–0 and 12–0 (100%)**, from either seat
- MCTS vs floor: **9–3 (75%)**
- (context: floor vs random = 34.5%, random vs random = 51%)

MCTS dominates both baselines at trivial search depth, 0 errors. The keystone works. Next:
stronger rollout/prior (BC net), more iterations under a time budget, then submit to the ladder.

## Local run note (NixOS)

`libcg.so` needs `libstdc++.so.6`, absent from NixOS's default loader path. `scripts/run.sh` sets
`LD_LIBRARY_PATH` from gcc. Kaggle's Ubuntu sandbox has it; this is dev-only.
