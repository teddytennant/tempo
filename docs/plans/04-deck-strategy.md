# Deck Strategy

## Principle

Deck choice dominates ladder results — but a *learned* pilot changes which deck is optimal. The
field's heuristics pick **simple** decks because they pilot complex ones clunkily. Our edge is
largest on a **high-skill-ceiling deck** that heuristics misplay but a trained policy handles.

## Selection

- **Primary:** one high-ceiling deck with strong upside lines (e.g. hand-size / combo scaling, Stage-2
  engines) that reward correct sequencing — exactly what a learned policy provides and a heuristic
  squanders.
- **Meta hedge:** the live meta shifts fast (Crustle-style ex-immunity reached ~50% of the field).
  Carry a non-ex / counter angle so we aren't blanked by immunity tech.
- **Legality:** exactly 60 cards from the organizer-provided pool; standard-format rules with the
  cabt engine's adjustments. `agent/deck.csv` currently holds a placeholder — the real list is chosen
  here in Stage 6 from meta analysis.

## Decide on the ladder, not local sim

Local eval mispredicts ladder rank and is ±14pt noisy. Carry 2–3 candidate decks and A/B them live
(5 submissions/day, latest 2 scored); promote by Elo. Mine the meta from the ladder-episode datasets
(distribution, rock-paper-scissors map) the same way the field did.

## Reference

The public field's meta write-ups (`wmh/ptcg-abc` `docs/strategy/`) are a starting map of the meta
and Trainer-card applications — a baseline to verify against current ladder data, not gospel.
