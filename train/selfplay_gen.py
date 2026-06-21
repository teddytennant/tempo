"""Generate self-play training data: MCTS plays itself; record (obs, visit-count policy, outcome).

The MCTS visit distribution is a stronger policy target than any single move (AlphaZero), and the
game outcome is the value target. Runs games in parallel across cores. Both seats use the current
net so the data reflects the agent's own play; Abomasnow vs Lucario to learn the real matchup.

Run: ./scripts/run.sh -m train.selfplay_gen --games 200 --iters 40 --workers 14 --pv net/bc_model.pt
"""
from __future__ import annotations

import argparse
import json
import os
import random as _random
import sys
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402


def _read(p):
    return [int(x) for x in open(p).read().splitlines() if x.strip()][:60]


def _agent(deck, opp, iters, pvpath, seed):
    import main as m
    from search.mcts import MctsAgent
    pv = None
    if pvpath:
        from net.infer import NetPV
        pv = NetPV(pvpath)
    return MctsAgent(deck, iters=iters, seed=seed, opp_model=opp, fallback=m.floor_agent, pv=pv)


def _play_and_record(a, b, deck_a, deck_b, max_steps=2000):
    agents = [a, b]
    obs, start = battle_start(deck_a, deck_b)
    if obs is None:
        return []
    recs = []
    try:
        for _ in range(max_steps):
            o = to_observation_class(obs)
            cur = o.current
            if cur is not None and cur.result != -1:
                return [{"obs": od, "policy": pol, "won": (cur.result == ai)} for od, pol, ai in recs]
            if o.select is None:
                return []
            ai = cur.yourIndex if cur is not None else 0
            sel = agents[ai](obs)
            pol = getattr(agents[ai], "last_policy", None)
            if pol is not None:
                recs.append((obs, pol, ai))
            obs = battle_select(sel)
        return []
    finally:
        battle_finish()


def _worker(task):
    seed, cfg = task
    _random.seed(seed)
    a = _agent(cfg["da"], cfg["la"], cfg["iters"], cfg["pv"], seed)
    b = _agent(cfg["db"], cfg["lb"], cfg["iters"], cfg["pv"], seed + 101)
    return _play_and_record(a, b, cfg["da"], cfg["db"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck_a", default=os.path.join(_ROOT, "data/decks/abomasnow.csv"))
    ap.add_argument("--deck_b", default=os.path.join(_ROOT, "data/decks/mega_lucario.csv"))
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--pv", default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(_ROOT, "data/selfplay/records.jsonl"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    cfg = dict(da=_read(a.deck_a), db=_read(a.deck_b),
               la=_read(a.deck_b), lb=_read(a.deck_a),  # each models the other deck as opponent
               iters=a.iters, pv=a.pv)

    ctx = get_context("spawn")
    n = 0
    with open(a.out, "a") as f, ctx.Pool(a.workers) as pool:
        for recs in pool.imap_unordered(_worker, [(a.seed + i, cfg) for i in range(a.games)]):
            for r in recs:
                f.write(json.dumps(r) + "\n"); n += 1
    print(f"wrote {n} self-play records -> {a.out}")


if __name__ == "__main__":
    main()
