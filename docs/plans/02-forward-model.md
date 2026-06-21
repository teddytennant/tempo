# Forward Model (Rust) — Spec

The forward model is what the public field failed to build (their MCTS `GameSimulator` is a stub),
and it gates all search + self-play. It is the report's headline.

## De-risk first (fact #2)

Before building, determine how `cg` can be used as a forward model:
- **(a) Forkable:** can a mid-game engine state be deep-copied/serialized and advanced by applying a
  chosen option? → cheap search directly on `cg`; Rust optional for speed.
- **(b) Re-simulatable:** can a game be replayed from seed + action history to reproduce "now" and
  branch hypotheticals? → works but slow → Rust reimplementation pays for itself.
- **(c) Neither:** no node-level search → rely on policy + outcome-level self-play (full games only).

Record the answer here once known; it selects the path below.

## Scope

Do **not** model all ~1267 cards. Model only the cards in **our deck + the live meta decks**
(a few dozen distinct effects). Grow coverage as the meta shifts. Card schema and effect text come
from the engine's `all_card_data()` / `all_attack()`.

## Interface (Rust crate `engine_rs`, PyO3 → abi3 wheel)

```
State::clone()            # cheap copy for rollouts
State::legal_options()    # mirror the engine's option enumeration
State::apply(option)      # advance state (handles chance via injected RNG seed)
State::is_terminal() -> winner
State::encode() -> features  # same encoding the net consumes
```

## Parity (non-negotiable)

A `tools/parity.py` harness drives the Rust engine and `cg` on identical action streams and asserts
identical observable state transitions, per card and per interaction. **Never ship a card whose
effect hasn't passed parity** — a divergence is a silently lost ladder game. Determinism via an
explicit injected seed so both engines branch chance identically.

## Throughput probe

Measure games/sec/core for determinized ISMCTS (sims × determinizations × ~60 moves). This number
sets the self-play compute estimate and whether the micro-experiment (03) is affordable.

## Deployment

If de-risk fact #3 (compiled `.so` loads in the agent sandbox) passes, bundle the wheel in
`submission.tar.gz` for in-agent search. If not, the Rust engine stays a **training-time** asset and
the deployed agent ships the policy net only (search done offline to train it).
