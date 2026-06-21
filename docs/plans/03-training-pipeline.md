# Training Pipeline

Three stages, each distilled down to the deployable CPU student. Validate-then-scale: every
expensive arm earns its budget with a cheap proof first.

## 1. Behavior cloning (the spine)

- **Data:** ladder-episode dataset (top-player games). Ingest → `(obs, option_features, chosen_idx,
  game_outcome)` rows. The engine only offers legal options, so the label is "which offered option
  did the strong player pick" — a ranking/classification target over the legal set.
- **Model:** encode `obs.current` (board, hands/prizes counts, energies) + per-option features (type,
  area, card id embedding, attackId, target) → score each legal option → softmax over the legal set.
  Small (few-M params), CPU-fast. A value head predicts the game outcome (aux signal).
- **Why it wins:** it pilots a strong deck *cleanly* — removing the field's "complex deck piloted
  clunkily" ceiling — and is genuinely learned (the Strategy Track's 70% axis).
- **Compute:** a few A100-hours. This alone should beat the rule-based field; ship it and measure.

## 2. Self-play RL (gated)

- **Micro-experiment first:** one simplified deck, short games, low MCTS sim count, a few thousand
  games on CPU + a brief A100 session. Acceptance: win-rate vs the BC baseline rises past ±14pt.
  If it doesn't beat baseline cheaply, **stop** — BC is the deliverable.
- **If it shows signal:** AlphaZero-style. Determinized PUCT-MCTS (net priors + value) over the Rust
  forward model generates games; train policy+value from outcomes; iterate. Use a **league**
  (snapshots + heuristic + meta decks) so we optimize for the real ladder field, not mirror play.
- **Topology:** CPU actors (Rust engine) generate games → GPU learner trains the net. Bottleneck is
  CPU cores, not GPU. Scale cores only after the micro-run shows signal.

## 3. Distillation

- Compress the strongest teacher (MCTS-augmented policy, or an offline LLM teacher) into the small
  ONNX student that ships. **Verify CPU latency** in a clean Kaggle-image container — must finish a
  full game inside the 10-min clock with margin.

## LLM teacher (optional, offline only)

Only if H200-class compute is confirmed. A strong LLM reads serialized game state, reasons, and
generates high-quality play + rationales for distillation — never deployed (can't be served in the
CPU/no-net/10-min sandbox). Use verl/TRL/GRPO, not slime (its Megatron+SGLang scale targets 100B+).
