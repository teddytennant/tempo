# Forward Model — Spec (revised: use the engine's native search API)

**Resolved (see 07-derisk-findings.md): the engine ships its own forward model.** We do NOT
reimplement the rules. The public field's MCTS failed because they stubbed a simulator; the official
`cg/api.py` already exposes a native, determinized search interface backed by `libcg.so`.

## The native search API

```python
root = search_begin(obs, your_deck, your_prize,
                    opponent_deck, opponent_prize, opponent_hand, opponent_active,
                    manual_coin=False)         # -> SearchState{observation, searchId}
nxt  = search_step(search_id, select)          # advance a hypothetical line
search_release(search_id);  search_end()       # memory reuse
```

- **Determinization is first-class:** you supply *predicted* opponent hidden cards (deck/prize/
  hand/active). Sample a world → `search_begin` → branch with `search_step` from `searchId`s.
- **Chance is controllable** via `manual_coin`.
- `obs.search_begin_input` (carried on every agent observation) is the required handle into
  `search_begin`.
- Engine error codes are explicit (invalid id, released, battle ended, count/range/dup violations).

## MCTS design (on top of the native API)

Determinized PUCT-MCTS:
1. Sample N determinizations of opponent hidden info (belief from logs + card-counting).
2. For each, `search_begin`, then expand/select with `search_step`, net priors+value at leaves.
3. Aggregate option values across determinizations; pick the best legal selection.
Time-budget the whole thing against the 10-min clock with a heuristic fallback.

## Rust role (optional, profile-gated)

`search_step` returns JSON decoded via `json.loads` + reflective `to_dataclass` — heavy per node.
Build MCTS in Python first (correct), profile sims/move, then move the hot loop to a Rust driver
calling the C ABI directly (extracting only needed fields) if per-node overhead caps strength.
Compiled `.so` in the submission is confirmed allowed (the engine itself is one).

## Belief / determinization quality

The weak link is *which* hidden worlds we sample. Start uniform over unseen legal cards consistent
with the opponent's deck-count and observed plays; improve with card-counting from `logs`
(MOVE_CARD/DRAW/PLAY/ATTACH) and meta priors over likely decklists. Better beliefs > more sims.

## Self-play

Full games already run via `battle_start`/`battle_select` (see `arena/selfplay.py`). Self-play RL
uses the same loop; the search API provides the per-move lookahead for AlphaZero-style targets.
