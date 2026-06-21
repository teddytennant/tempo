# Winning Plan — Pokémon TCG AI Battle Challenge

> **UPDATE (post-engine-download):** the "forward model is the unsolved wall / reimplement in Rust"
> framing below is **superseded** — the engine ships a native determinized search API
> (`search_begin`/`search_step`). We use it instead of reimplementing rules. See
> `07-derisk-findings.md` and `02-forward-model.md`. The thesis (learned policy pilots a strong deck
> cleanly) is unchanged and now first-hand evidenced: the rule-based floor agent loses to random.

## Context

Kaggle × The Pokémon Company. Two linked tracks: a **Simulation** ladder
(`pokemon-tcg-ai-battle`) and a **Strategy** track (the money: top-8 teams advance, judged
~70% AI approach / 20% deck / 10% report). You submit `submission.tar.gz` = `main.py` +
`deck.csv` + engine `cg/`. The agent is `agent(obs_dict) -> list[int]`: pick indices into the
engine's legal-option list, or return 60 card IDs at deck-selection. The deployed agent runs
**CPU-only, no internet, 10-minute chess clock** — that single constraint rules out any big model
at inference.

Ground truth comes from the leading public repo [`wmh/ptcg-abc`](https://github.com/wmh/ptcg-abc):
its best ladder agent is a **simple heuristic on a simple deck** (Elo 836); its MCTS is an
abandoned stub because nobody could turn `cg` into a forward model; deck choice dominates; the
ladder is the only honest judge (local eval is ±14pt noisy).

## Thesis

**Train a policy that pilots a strong deck cleanly.** The field's heuristics pilot good decks
clunkily — that's their ceiling. A learned policy removes it, and simultaneously earns the 70%
"AI approach" score that a heuristic can't. That is the whole edge. Everything below serves it.

## The agent we ship

A small policy/value net, exported to **ONNX (CPU)**, wrapped in `main.py`:

- Parse `obs_dict` → rank the legal options → return the selection (respecting `minCount/maxCount`).
- A `_legal_fallback` that always returns a legal move, and a clock guard. **Never crashes, never
  times out** — the validation episode rejects anything that does.
- Deck-selection returns the 60-card list.

That's the deliverable. Search and self-play are upgrades layered on the same net, not
prerequisites.

## How we build the policy

1. **Behavior cloning.** Train the net on Kaggle's ladder-episode dataset (top-player games). This
   alone is a strong, fast, clean-piloting agent — the spine, and likely enough to win the ladder.
2. **Self-play RL — only if it proves itself.** Build the Rust forward model, run a cheap micro
   self-play on one deck, and keep it only if it beats the BC agent past the ±14pt noise. If it
   does, scale; if it doesn't, ship BC. No core-weeks spent on faith.

The Rust forward model is the high-value build and the report's headline (it's what the field
couldn't do), but it's downstream of a working BC agent, not blocking it.

## Deck

Pick one **high-ceiling deck** that heuristics misplay but a learned pilot handles — that's where
our edge over the field is largest — with a non-ex / counter angle against the dominant Crustle
meta. Decide between 2–3 candidates on the **live ladder** (5 submissions/day, latest 2 scored),
not local sim.

## Compute

BC fits a **few A100-hours** + local CPU — that's the whole near-term need. Self-play, if validated,
is bottlenecked on **CPU cores** for game generation (rent a high-core host then, not before). No
H200s or LLM teacher unless a cheap pilot first proves they pay. The shipped artifact is a <50 MB
CPU net — GPU size is irrelevant to deployment.

## Establish these three facts first

They decide what's possible; get them before building hard:

1. **Is the ladder-episode dataset downloadable with usable action labels?** (BC depends on it.)
2. **Can `cg` state be forked/re-simulated for search?** (Decides whether MCTS is on the table.)
3. **Does a compiled Rust `.so` load in the agent sandbox?** (Decides Rust-at-deploy vs Rust-as-tool.)

## Execution: docs → tests → code

Every subsystem gets a one-page design doc, then failing tests encoding its acceptance criteria,
then code until green. Build order:

1. **Repo + docs.** Private GitHub repo; `docs/plans/` (agent contract, forward-model spec,
   training, deck, eval); the `obs_dict`/option API doc as source of truth.
2. **Floor agent.** Tests: always-legal, in-budget, never-crash. Code: minimal `main.py` + simple
   deck. **Submit** for a baseline rank and a proven pipeline.
3. **Forward model (Rust).** Tests: state-transition parity vs `cg`. Code: rules engine scoped to
   our deck + meta, PyO3 wheel.
4. **BC spine.** Tests: data schema, ONNX round-trip, CPU latency. Code: ingest episodes → train →
   ONNX → wire into `main.py`. Submit, measure on ladder.
5. **Self-play (gated).** Micro-experiment first; scale only if it beats BC past noise.
6. **Deck A/B + report.**

## Verification

- **Honest arena:** evaluate in the official `cabt` env over hundreds of games with confidence
  intervals; <10pt swings are noise.
- **Parity harness:** Rust engine vs `cg` on identical action streams must match exactly.
- **Deployment smoke test:** load the final tarball in a clean Kaggle-image container; one self-play
  game must finish error-free inside the 10-min clock.
- **Ladder is ground truth.** Stage offline, submit the best 2/day, promote by Elo.

## Strategy Track report

The narrative writes itself from the work: *we built the forward model and learned policy the field
couldn't, and used them to pilot a high-ceiling deck cleanly.* That covers the 70% AI and 20% deck
axes directly.
