"""Opponent archetype detection: read the opponent's revealed cards (board + discard) and match to
the closest known frontier decklist, so the search determinizes the *right* opponent instead of a
fixed guess. The discard/board accumulate over the game, so detection sharpens as the game goes.
"""
try:
    from opp_decks import CANDIDATES
except Exception:
    CANDIDATES = {}

# IDF weights: a card in 1 deck identifies it strongly; a card in every deck (basic energy) is useless.
from collections import Counter as _C
_DF = _C()
for _ids in CANDIDATES.values():
    for _cid in set(_ids):
        _DF[_cid] += 1
_SETS = {id(v): set(v) for v in CANDIDATES.values()}


def detect_opp(obs, default):
    if not CANDIDATES:
        return default
    try:
        yi = obs.current.yourIndex
        op = obs.current.players[1 - yi]
    except Exception:
        return default
    seen = []
    for pk in (list(op.active or []) + list(op.bench or [])):
        if pk is None:
            continue
        seen.append(pk.id)
        for c in getattr(pk, "preEvolution", None) or []:
            if c is not None:
                seen.append(c.id)
    for c in (op.discard or []):
        if c is not None:
            seen.append(c.id)
    if not seen:
        return default
    best, best_score = default, 0.75   # need clear distinctive-card evidence to override default
    for ids in CANDIDATES.values():
        s = _SETS[id(ids)]
        score = sum(1.0 / _DF[cid] for cid in seen if cid in s)
        if score > best_score:
            best_score, best = score, ids
    return best
