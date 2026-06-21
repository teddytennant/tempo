# Agent Contract — Source of Truth

Extracted from the official engine usage in `cg.api` (reference: `wmh/ptcg-abc`
`agents/alakazam/main.py`). This is the ground truth every subsystem codes against. If the
real engine disagrees once we have it, **this doc gets corrected, not the code worked around.**

## Submission

`submission.tar.gz` containing, at root:
- `main.py` — defines `agent(obs_dict) -> list[int]`
- `deck.csv` — exactly 60 integer card IDs, one per line
- `cg/` — the official engine (downloaded from Kaggle; `CG_LIB_PATH` points at it; never committed)

Submit: `kaggle competitions submit pokemon-tcg-ai-battle -f submission.tar.gz -m "msg"`.
5 submissions/day; only the latest 2 are scored. A validation episode (agent vs copies of
itself) must pass or the submission errors out.

`deck.csv` is resolved at import from, in order: next to `main.py`, `./deck.csv`,
`/kaggle_simulations/agent/deck.csv`, then `sys.path` entries.

## The function

```python
def agent(obs_dict):
    # Deck-selection phase: engine asks for our deck.
    if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
        return my_deck                      # list[int], exactly 60 card IDs
    obs = to_observation_class(obs_dict)    # -> Observation
    if obs.select is None:
        return my_deck
    return rank_and_select(obs)             # list[int]: indices into obs.select.option
```

**In-game return = a list of indices into `obs.select.option`**, satisfying
`select.minCount`/`select.maxCount`. **Never raise** — always return a legal fallback
(`list(range(min(minCount, n)))`). **Never exceed the 10-minute per-player game clock**
(timeout = loss).

## `cg.api` surface

```python
from cg.api import (
    AreaType, Card, CardType, EnergyType, Observation, OptionType, Pokemon,
    SelectContext, all_card_data, all_attack, to_observation_class,
)
```

### Observation
- `obs.current` — the board `State` (None during some prompts)
- `obs.select` — the decision prompt (None during deck-selection)

### State (`obs.current`)
- `.turn: int`, `.yourIndex: 0|1`
- `.players[0|1]: Player`
- `.stadium: list` (the stadium card, or empty), `.looking: list` (cards currently being viewed)
- `.supporterPlayed: bool`, `.stadiumPlayed: bool`

### Player
- `.hand: list[Card]`, `.active: list[Pokemon]`, `.bench: list[Pokemon]`, `.discard: list[Card]`
- `.prize: list` (prizes remaining), `.deckCount: int`, `.handCount: int`, `.benchMax: int`

### Pokemon
- `.id: int` (card ID), `.hp: int`
- `.energies: list[EnergyType]` (attached energy *types*)
- `.energyCards: list` (attached energy *cards*, each with `.id`)
- `.tools: list`

### Select (`obs.select`)
- `.option: list[Option]` — the legal choices, indexed `0..n-1`
- `.context: SelectContext` — what's being asked
- `.minCount: int`, `.maxCount: int` — how many indices to return
- `.deck: list` — present for DECK-area options (search effects)

### Option (`o`)
- `.type: OptionType`
- `.index: int` — card position within its area
- `.area: AreaType` — HAND/DECK/BENCH/ACTIVE/DISCARD/PRIZE/STADIUM/LOOKING
- `.inPlayArea`, `.inPlayIndex` — target slot (evolve/attach target)
- `.attackId: int` — for ATTACK options
- `.playerIndex: 0|1` — whose card (targeting)
- `.number: int` — for NUMBER options

### Enums
- **OptionType:** `YES, NO, NUMBER, CARD, PLAY, ENERGY, ATTACH, EVOLVE, ABILITY, RETREAT, ATTACK, END`
- **SelectContext:** `IS_FIRST, SWITCH, TO_ACTIVE, SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON,
  TO_BENCH, TO_FIELD, TO_HAND, TO_HAND_ENERGY, ATTACH_TO, ATTACH_FROM, DISCARD,
  DISCARD_CARD_OR_ATTACHED_CARD, DISCARD_ENERGY, DISCARD_ENERGY_CARD, DAMAGE_COUNTER,
  DAMAGE_COUNTER_ANY, TO_DECK, TO_DECK_BOTTOM, TO_PRIZE`
- **AreaType:** `DECK, HAND, DISCARD, ACTIVE, BENCH, PRIZE, STADIUM, LOOKING`
- **CardType:** `POKEMON, ITEM, SUPPORTER, STADIUM, TOOL, BASIC_ENERGY, SPECIAL_ENERGY`
- **EnergyType:** `COLORLESS(0), PSYCHIC(5), ...`

### Card data
- `all_card_data() -> list[Card]`: `.cardId`, `.cardType`, `.skills` (each `.text`), `.attacks`
  (attack IDs), `.weakness`, `.resistance`, `.ex`, `.megaEx`, `.stage1`, `.stage2`, `.energyType`
- `all_attack() -> list`: `.attackId`, `.energies: list[EnergyType]` (cost), `.text`

## Engine note (the key uncertainty)

`to_observation_class` and `all_card_data` are read-only views. There is **no public
clone/step on a mid-game state** — this is why the field's MCTS failed. Whether the engine
can be forked for search is de-risk fact #2 (see `02-forward-model.md`). The agent itself
never constructs moves: **the engine only ever offers legal options; we rank and pick.**
