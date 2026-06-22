"""Independent, published competition bots used as honest opponents.

Each module exposes `best_options(obs_dict) -> list[int]` and a `DECK` (list[int])
and is a faithful, self-contained port of a published Kaggle notebook — none of
them call tempo's own scorer. Used by tools/eval_vs_bots.py to measure our agents
against opponents we did not tune against (the antidote to self-play over-fit).
"""
