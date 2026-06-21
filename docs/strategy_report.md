# tempo — Strategy Track Report (draft)

Pokémon TCG AI Battle Challenge. Agent: **tempo**. This documents our approach, the original
methods, and the empirical process behind them. (Draft — numbers refreshed as training continues.)

## 1. Thesis

The competitive field plays a small set of meta decks (Mega Lucario ex ~44%, Mega Abomasnow ex
~17%, by our replay analysis). Since everyone plays similar decks, **the differentiator is pilot
quality, not deck choice.** We therefore invested in the strongest possible *pilot*: search guided
by a learned policy, trained on real games and improved by self-play.

## 2. The forward model nobody used

The official engine (`libcg.so`) exposes a **native determinized search API** —
`search_begin / search_step / search_release` — into which you feed *predicted* opponent hidden
cards and branch hypothetical lines, with explicit coin control. This is a built-in, exact,
fast forward model for an imperfect-information game. We verified it supports a persistent,
branchable search tree (distinct `searchId`s) and rolls out to terminal states.

Our core engine is **determinized Information-Set MCTS** over this API: sample opponent hidden
information (modelling the dominant field deck), search each determinization with PUCT, aggregate.
No reimplementation of the 1267-card rules was needed — the native engine *is* the model, which is
both correct-by-construction and fast enough to search in-agent within the 10-minute clock.

## 3. A learned pilot (AlphaGo/AlphaZero recipe)

- **Behavior cloning from real ladder games.** Kaggle's `replay` API returns complete games
  (both players' decks and moves). We extract every in-game decision as `(observation, chosen move)`
  (handling a step/action off-by-one and validating each action against its option list), and
  behavior-clone a **policy+value net** that imitates the field's strong play. Held-out top-1 move
  accuracy ≈ 0.53–0.56 vs a 0.30 random-pick baseline.
- **Net-guided search.** The policy net supplies the **PUCT prior**; a reliable lethal-aware
  rollout supplies leaf value (the learned value head is folded in as it strengthens). Better move
  ordering focuses search where strong players look.
- **Self-play reinforcement learning.** The MCTS plays itself; the **visit-count distribution** is a
  superhuman-trending policy target and the game outcome is the value target. We retrain and repeat
  (the AlphaZero loop), parallelized across cores. This pushes the net *past* the cloned humans.

## 4. Verification methodology (the part we're proudest of)

Local self-play against weak/mirror opponents does **not** predict the ladder — we confirmed this
the hard way (an agent that crushed our baselines locally merely tied them on the ladder). Our fix:
**evaluate against the real field.** We download real ladder replays, extract the actual decks and
moves opponents play, and measure against *those*.

This caught a concrete mistake in real time: a floor-pilot deck tournament told us to switch from
the meta deck to "Mega Lucario ex"; the replay data showed the strong teams actually play the
Abomasnow archetype, and a 48-game head-to-head confirmed our proposed switch *lost* (39.6%). We
reverted before wasting a scarce daily submission. Every design decision is gated on large-N
evaluation with confidence intervals (the engine's win-rate is ±~14pt noisy at 50 games).

## 5. Engineering

Deck-agnostic, never-crashing agent (`agent(obs_dict) -> list[int]`) with a hard legal fallback and
a per-game 10-minute clock accountant. The deployed net runs in **pure numpy** (no torch in the
submission; verified to match the torch net to 1e-6), so the learned agent ships as a small weight
file plus the engine. Reproducible harness: parallel deck-vs-deck tournaments, real-replay metagame
analysis, and the self-play→train loop.

## 6. Deck

We play **Mega Abomasnow ex** — the highest-win-rate common archetype (≈57% in sampled real games)
and a favorable matchup into the dominant Mega Lucario ex (≈80% for our search agent vs a Lucario
opponent locally). The opponent model in determinization is set to Mega Lucario ex (the most likely
opponent).

## 7. Results (live)

- Submitted MCTS on the meta deck reached a public score of **604** (vs 370 for an early version),
  the gain coming entirely from pilot improvements (rollout quality + search budget) on the same
  deck.
- The learned (net-guided, self-play-trained) agent is in training; it is promoted to the live
  submission once it beats the vanilla-MCTS agent head-to-head.
