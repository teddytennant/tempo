"""Standalone behavior-cloning agent — pure top-player imitation policy.

Pilots whatever deck.csv holds by ranking the engine's legal options with a policy net distilled
from the 32 top leaderboard teams' winning decisions (train/bc.py on tools/extract_bc_top.py's
corpus; held-out top-1 move-match ~56% vs 27% random). No search, no rules: a clean test of
"does imitating the best players beat our hand-written pilots on the ladder?"

Contract: agent(obs_dict) -> list[int]. Deck phase returns the 60 ids. Every decision is wrapped
crash-safe (validation plays you vs a copy of yourself; one exception forfeits the rating).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "net"))

from cg.api import to_observation_class  # noqa: E402


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


def agent(obs_dict):
    # Deck-selection phase: the engine asks once with select == None.
    try:
        if isinstance(obs_dict, dict) and obs_dict.get("select") is None:
            return my_deck
    except Exception:
        pass
    try:
        obs = to_observation_class(obs_dict)
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
        k = min(max(minc, 1), maxc, n)   # take the net's top-k within [minCount, maxCount]
        return ranked[:k]
    except Exception:
        return _legal_fallback(obs_dict)
