# Tempo Agent — Current Algorithm & Math

A short explainer of what the agent is doing today. The engine is the Pokémon TCG
forward model (`cg`); the agent plays under a 10-minute-per-game clock on CPU.

## TL;DR

We run **determinized UCT** (Monte Carlo Tree Search with UCB1 selection over
sampled hidden-information worlds). Each move, we spend a wall-clock time budget
sampling possible opponent hands/decks, searching our own main-phase decisions,
rolling out to the end of the game with a cheap lethal-aware policy, and picking
the action with the best win rate. If we ever run low on clock, we drop to a fast
heuristic ("floor") agent so we never flag.

## The core: determinized UCT

The game has hidden information (opponent hand, both decks, prizes), so plain MCTS
doesn't apply directly. We use **determinization**: every search iteration samples
one fully-observable "world" consistent with what we can see, then searches that
world with standard UCT. Statistics are pooled across all sampled worlds in one
shared tree keyed on *our* decisions.

Each iteration does four things:

1. **Determinize** — sample the hidden cards.
2. **Select** — descend the tree using the UCB rule below until we hit a node with
   an untried action.
3. **Expand + roll out** — add that action, then simulate to a terminal state with
   the rollout policy.
4. **Backpropagate** — push the result (win/draw/loss) back up the visited path.

After the time budget is exhausted, we play the most-promising root action.

### UCB1 selection rule

For each candidate action *a* at a node we compute

```
U(a) = Q(a) + c · sqrt( ln(N) / n(a) )
```

- `Q(a) = wins(a) / n(a)` — empirical win rate of the action (from our perspective)
- `n(a)` — times we've tried action *a*
- `N` — total visits to the parent node
- `c = 1.4` — exploration constant (the `sqrt(2)` ≈ 1.41 textbook value)

Unvisited actions are taken first (treated as infinite UCB). This is the standard
exploration/exploitation tradeoff: the first term rewards actions that have been
winning, the second rewards actions we haven't explored much.

*Code: `search/mcts.py`, `ucb_pick` and `_iterate`.*

### What we actually search vs. simulate

We only build the tree over decisions where search adds value — **our** main-phase,
single-select decisions with more than one legal option. Everything else
(opponent moves, chance/coin flips, sub-selections, multi-selects) is advanced by
the default policy rather than branched on. This keeps the tree narrow and the
search deep on the decisions that matter.

### Rollout (playout) policy

Once we leave the tree we simulate to the end of the game. The playout policy is
**lethal-aware, otherwise random**:

- On a single-select decision, if any attack would KO the opponent's active
  Pokémon (attack damage ≥ opponent HP), take it.
- Otherwise pick a uniformly random legal action.

Lethal-awareness gives sharper value estimates than pure random without the
pathologies of the heuristic agent (which, interestingly, loses to random in
playouts). Rollouts are capped at **200 steps**; if we hit the cap without a
result we score it as a draw.

*Code: `search/mcts.py`, `_rollout_sel` / `_rollout`.*

### Determinization details

We don't model the opponent's exact list — we sample from the known deck pool using
the counts the engine exposes (deck count, hand count, prize count). A fresh sample
is drawn every iteration, so over thousands of iterations we average over many
plausible worlds. Face-down active Pokémon are filled with a random basic.

*Code: `search/mcts.py`, `_determinize`.*

### Value / backprop

Terminal results are scored from our perspective and averaged up the tree:

| Outcome | Value |
|---------|-------|
| Win     | 1.0   |
| Draw    | 0.5   |
| Loss    | 0.0   |

## Time management

We have a hard 10-minute game clock, so search is time-budgeted, not iteration-budgeted.

| Knob | Value | Why |
|------|-------|-----|
| Game budget | 540 s (9 min) | Reserve ~1 min margin under the 10-min cap |
| Per-move cap | 6 s | No single decision eats the clock |
| Dynamic per-move budget | `min(6 s, 0.05 × remaining)` | Spend 5% of remaining time per move, capped at 6 s |
| Panic threshold | < 2 s remaining | Below this, skip search entirely |
| Max iters | 100,000 | Effectively unbounded; the clock is the real limit |

Each move runs MCTS iterations until either the iteration count or the wall-clock
deadline is hit. The per-game clock resets on a new game (and on detected turn
regression / restart).

*Code: `agent/main.py`, `agent()` wrapper and the time constants.*

## Floor fallback

There's always a guaranteed-legal cheap policy underneath the search. If MCTS is
unavailable, throws, or we're out of clock, we fall back to a deck-agnostic
heuristic that scores options by priority — take lethal attacks first, then
sensible plays (evolve, ability, attach energy where needed, play cards by type),
down to a guaranteed-legal last resort. This guarantees we always return a legal
move and never time out.

*Code: `agent/main.py`, `Policy` / `floor_agent` / `_legal_fallback`.*

## What it is *not* (yet)

Worth being upfront with the team — these are deliberate next steps, not present today:

- No neural-network priors or learned value function — rollouts are lethal-aware random.
- No opponent-list inference / belief modeling — determinization is uniform over the deck pool.
- No multi-determinization weighting — each iteration is one fresh uniform sample.
- Correctness-first Python; Rust hot-path optimization is planned.

## File map

| File | Role |
|------|------|
| `search/mcts.py` | Determinized UCT: UCB selection, determinization, rollouts, backprop |
| `agent/main.py` | Agent entry: time budgeting, clock guard, floor fallback |
| `cg/api.py` | Engine forward-model API (read-only) |
| `arena/selfplay.py` | Self-play evaluation harness |
| `docs/plans/` | Design docs (master plan, agent contract, forward model) |
