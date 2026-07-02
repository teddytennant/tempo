"""Hybrid top-player imitation agent — BC policy net + verified-lethal override.

Normal decisions: rank the engine's legal options with a policy net distilled from the winning
decisions of every 1050+ leaderboard team across ~11 days of ladder play (teacher examples
weighted by the team's current score, so the reigning #1 counts most). Winning turns: a
prize-correct multi-step lethal verifier (agent/lethal.py, native search tree + PrizeTracker
belief) overrides the net whenever a guaranteed game-winning line exists this turn.

This is the "normal turns by policy, winning turns verified by search" paradigm the 1250+
notebooks converge on — with the policy learned from the whole elite field instead of
hand-written for one deck.

Contract: agent(obs_dict) -> list[int]. Deck phase returns the 60 ids. Every path is wrapped
crash-safe (validation plays you vs a copy of yourself; one exception forfeits the rating).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "net"))

from cg.api import to_observation_class  # noqa: E402

try:
    from lethal import lethal_move
except Exception:
    lethal_move = None
try:
    from prize_tracker import PrizeTracker
except Exception:
    PrizeTracker = None


def _read_deck():
    for p in [os.path.join(_HERE, "deck.csv"), "deck.csv", "/kaggle_simulations/agent/deck.csv"]:
        if os.path.exists(p):
            with open(p) as f:
                return [int(x) for x in f.read().splitlines() if x.strip()][:60]
    return []


my_deck = _read_deck()

_net = None
try:
    from net.infer_np import NetPVNumpy  # noqa: E402
    for p in [os.path.join(_HERE, "model.npz"), "model.npz", "/kaggle_simulations/agent/model.npz"]:
        if os.path.exists(p):
            _net = NetPVNumpy(p)
            break
except Exception:
    _net = None

_tracker = None


def _legal_fallback(obs_dict):
    """Always-legal default: the first minCount option indices."""
    try:
        sel = obs_dict.get("select")
        if not sel:
            return []
        n = len(sel.get("option") or [])
        k = max(int(sel.get("minCount") or 0), 0)
        return list(range(min(max(k, 1), n))) if n else []
    except Exception:
        return [0]


def _is_main(obs_dict):
    try:
        sel = obs_dict.get("select") or {}
        return sel.get("context") == 0
    except Exception:
        return False


def agent(obs_dict):
    global _tracker
    # Deck-selection phase: the engine asks once with select == None.
    try:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            _tracker = PrizeTracker(my_deck) if PrizeTracker else None
            return my_deck
    except Exception:
        pass

    obs = None
    try:
        obs = to_observation_class(obs_dict)
        if _tracker is None and PrizeTracker is not None:
            _tracker = PrizeTracker(my_deck)
        if _tracker is not None and obs is not None:
            _tracker.update(obs, obs_dict)   # track our prized cards every frame
    except Exception:
        obs = None

    # Winning turns: play a VERIFIED lethal line the moment one exists (never relies on a card
    # that is actually sitting in the prize zone).
    if lethal_move is not None and my_deck and _is_main(obs_dict):
        try:
            prized = _tracker.prized_cards() if _tracker is not None else None
            lm = lethal_move(obs_dict, my_deck, prized)
            if isinstance(lm, list) and lm:
                return lm
        except Exception:
            pass

    # Normal turns: the top-player policy ranks the legal options.
    try:
        if obs is None:
            return _legal_fallback(obs_dict)
        sel = obs.select
        if sel is None or not sel.option:
            return _legal_fallback(obs_dict)
        n = len(sel.option)
        minc = max(int(getattr(sel, "minCount", 0) or 0), 0)
        maxc = int(getattr(sel, "maxCount", 1) or 1)
        if _net is None:
            return _legal_fallback(obs_dict)
        probs, _ = _net.policy_value(obs)
        if not probs or len(probs) != n:
            return _legal_fallback(obs_dict)
        ranked = sorted(range(n), key=lambda i: probs[i], reverse=True)
        lo = min(max(minc, 1), n)
        hi = min(max(maxc, lo), n)
        # Multi-select: keep every option the net rates above uniform, within [lo, hi].
        k = max(lo, min(hi, sum(1 for i in range(n) if probs[i] >= 1.0 / n)))
        return ranked[:k]
    except Exception:
        return _legal_fallback(obs_dict)
