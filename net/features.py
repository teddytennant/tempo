"""Featurize an Observation -> (global vector, per-option matrix). Shared by BC training and the
live agent so train/infer encodings match exactly.

Operates on cg Observation objects. For training, parse replay obs dicts with
cg.api.to_observation_class first, so both paths feed identical objects.
"""
from __future__ import annotations

import numpy as np

from cg.api import all_attack, all_card_data

# ── static card features ─────────────────────────────────────────────────────
_CARDS = {c.cardId: c for c in all_card_data()}
_ATK = {a.attackId: a for a in all_attack()}
CARDF = 17  # per-card static feature width


def _card_vec(cid):
    c = _CARDS.get(cid)
    v = np.zeros(CARDF, np.float32)
    if c is None:
        return v
    ct = int(c.cardType)
    if 0 <= ct < 7:
        v[ct] = 1.0
    v[7] = (c.hp or 0) / 300.0
    v[8] = 1.0 if c.ex else 0.0
    v[9] = 1.0 if c.megaEx else 0.0
    v[10] = 1.0 if c.basic else 0.0
    v[11] = 1.0 if c.stage1 else 0.0
    v[12] = 1.0 if c.stage2 else 0.0
    v[13] = (int(c.energyType) if c.energyType is not None else 0) / 11.0
    v[14] = (c.retreatCost or 0) / 4.0
    dmgs = [(_ATK[a].damage or 0) for a in (c.attacks or []) if a in _ATK]
    costs = [len(_ATK[a].energies or []) for a in (c.attacks or []) if a in _ATK]
    v[15] = (max(dmgs) if dmgs else 0) / 300.0
    v[16] = (max(costs) if costs else 0) / 5.0
    return v


_CARDVEC = {cid: _card_vec(cid) for cid in _CARDS}
_ZERO = np.zeros(CARDF, np.float32)


def _cv(cid):
    return _CARDVEC.get(cid, _ZERO)


# ── enums / dims ─────────────────────────────────────────────────────────────
N_OPTYPE = 17
N_AREA = 13  # AreaType 1..12 -> index by value
CTX_LIST = [0, 7, 21, 8, 4, 1, 3, 22, 30, 41, 2, 5, 13, 37, 35, 11]  # curated common contexts
CTX_IDX = {c: i for i, c in enumerate(CTX_LIST)}
N_CTX = len(CTX_LIST) + 1  # + "other"

GLOBAL_DIM = 1 + 1 + 2 + N_CTX + 4 + 4 + 4 + (1 + CARDF + 2) + (1 + CARDF + 2) + 1
OPT_DIM = N_OPTYPE + N_AREA + CARDF + 1 + 2 + CARDF + 1


def _get_card(obs, area, index, pi):
    try:
        if area is None or index is None or index < 0:
            return None
        st = obs.current
        a = int(area)
        if a == 2:  # HAND
            h = st.players[pi].hand
            return h[index] if h and index < len(h) else None
        if a == 4:  # ACTIVE
            x = st.players[pi].active
            return x[index] if x and index < len(x) else None
        if a == 5:  # BENCH
            x = st.players[pi].bench
            return x[index] if x and index < len(x) else None
        if a == 3:  # DISCARD
            x = st.players[pi].discard
            return x[index] if x and index < len(x) else None
        if a == 1:  # DECK
            x = getattr(obs.select, "deck", None)
            return x[index] if x and index < len(x) else None
        if a == 7:  # STADIUM
            x = st.stadium
            return x[index] if x and index < len(x) else None
    except Exception:
        return None
    return None


def _active_block(player):
    v = np.zeros(1 + CARDF + 2, np.float32)
    act = player.active[0] if (player.active and player.active[0] is not None) else None
    if act is not None:
        v[0] = 1.0
        v[1:1 + CARDF] = _cv(act.id)
        mh = getattr(act, "maxHp", 0) or 1
        v[1 + CARDF] = (act.hp or 0) / max(mh, 1)
        v[2 + CARDF] = len(act.energies or []) / 5.0
    return v


def featurize(obs):
    """obs: cg Observation. Returns (g[GLOBAL_DIM] float32, opts[N, OPT_DIM] float32)."""
    st = obs.current
    sel = obs.select
    yi = st.yourIndex
    me = st.players[yi]
    opp = st.players[1 - yi]

    g = np.zeros(GLOBAL_DIM, np.float32)
    k = 0
    g[k] = (st.turn or 0) / 30.0; k += 1
    g[k] = float(yi); k += 1
    g[k] = (sel.minCount or 0) / 5.0; k += 1
    g[k] = (sel.maxCount or 0) / 5.0; k += 1
    ci = CTX_IDX.get(int(sel.context), len(CTX_LIST))
    g[k + ci] = 1.0; k += N_CTX
    g[k] = float(bool(st.supporterPlayed)); g[k + 1] = float(bool(st.stadiumPlayed))
    g[k + 2] = float(bool(st.energyAttached)); g[k + 3] = float(bool(st.retreated)); k += 4
    g[k] = len(me.prize) / 6.0; g[k + 1] = (me.deckCount or 0) / 60.0
    g[k + 2] = (me.handCount or 0) / 15.0; g[k + 3] = sum(1 for p in me.bench if p) / 5.0; k += 4
    g[k] = len(opp.prize) / 6.0; g[k + 1] = (opp.deckCount or 0) / 60.0
    g[k + 2] = (opp.handCount or 0) / 15.0; g[k + 3] = sum(1 for p in opp.bench if p) / 5.0; k += 4
    g[k:k + 1 + CARDF + 2] = _active_block(me); k += 1 + CARDF + 2
    g[k:k + 1 + CARDF + 2] = _active_block(opp); k += 1 + CARDF + 2
    g[k] = 1.0 if st.stadium else 0.0; k += 1

    opts = np.zeros((len(sel.option), OPT_DIM), np.float32)
    for i, o in enumerate(sel.option):
        j = 0
        t = int(o.type)
        if 0 <= t < N_OPTYPE:
            opts[i, j + t] = 1.0
        j += N_OPTYPE
        if o.area is not None and 0 <= int(o.area) < N_AREA:
            opts[i, j + int(o.area)] = 1.0
        j += N_AREA
        pi = o.playerIndex if o.playerIndex is not None else yi
        card = _get_card(obs, o.area, o.index, pi)
        if card is not None:
            opts[i, j:j + CARDF] = _cv(card.id)
        j += CARDF
        opts[i, j] = 1.0 if (o.playerIndex is not None and o.playerIndex != yi) else 0.0
        j += 1
        if o.attackId is not None and o.attackId in _ATK:
            a = _ATK[o.attackId]
            opts[i, j] = (a.damage or 0) / 300.0
            opts[i, j + 1] = len(a.energies or []) / 5.0
        j += 2
        tgt = _get_card(obs, o.inPlayArea, o.inPlayIndex, yi)
        if tgt is not None:
            opts[i, j:j + CARDF] = _cv(tgt.id)
        j += CARDF
    return g, opts
