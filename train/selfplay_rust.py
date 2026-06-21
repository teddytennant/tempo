"""True-AlphaZero self-play: net-in-Rust (the strong, fast agent) plays itself and records its
visit-count policies + outcomes. Because search > the raw net, training the net on these targets
makes the net exceed its current self each cycle (policy improvement) — unlike vanilla distillation,
which is capped at vanilla.

Run: ./scripts/run.sh -m train.selfplay_rust --pv net/model.npz --games 200 --budget 0.3 --workers 14
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

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402


def _read(p):
    return [int(x) for x in open(p).read().splitlines() if x.strip()][:60]


def _worker(task):
    seed, cfg = task
    import engine_rs
    engine_rs.init(os.path.abspath(os.path.join(_ROOT, "cg", "libcg.so")))
    engine_rs.init_net(os.path.abspath(cfg["pv"]))
    _random.seed(seed)
    da, db, la, lb, budget = cfg["da"], cfg["db"], cfg["la"], cfg["lb"], cfg["budget"]
    decks, opps = [da, db], [la, lb]
    obs, start = battle_start(da, db)
    if obs is None:
        return []
    recs = []
    try:
        for _ in range(2000):
            o = to_observation_class(obs)
            cur = o.current
            if cur is not None and cur.result != -1:
                return [{"obs": od, "policy": pol, "won": (cur.result == ai)} for od, pol, ai in recs]
            if o.select is None:
                return []
            ai = cur.yourIndex if cur is not None else 0
            sel = o.select
            if sel.context == 0 and sel.maxCount == 1 and len(sel.option) > 1 and (sel.minCount or 0) <= 1:
                try:
                    s, pol = engine_rs.choose_policy(json.dumps(obs), decks[ai], opps[ai], budget, 10**9, 1.4, seed, True)
                    pick = s if (isinstance(s, list) and s) else [0]
                    if pol:
                        recs.append((obs, pol, ai))
                except Exception:
                    pick = [0]
            else:
                k = sel.maxCount
                pick = _random.sample(range(len(sel.option)), min(k, len(sel.option))) if k > 0 else []
            obs = battle_select(pick)
        return []
    finally:
        battle_finish()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pv", required=True)
    ap.add_argument("--deck_a", default=os.path.join(_ROOT, "data/decks/abomasnow.csv"))
    ap.add_argument("--deck_b", default=os.path.join(_ROOT, "data/decks/mega_lucario.csv"))
    ap.add_argument("--budget", type=float, default=0.3)
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(_ROOT, "data/selfplay_rust/records.jsonl"))
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    cfg = dict(da=_read(a.deck_a), db=_read(a.deck_b), la=_read(a.deck_b), lb=_read(a.deck_a),
               budget=a.budget, pv=a.pv)
    ctx = get_context("spawn")
    n = 0
    with open(a.out, "a") as f, ctx.Pool(a.workers) as pool:
        for recs in pool.imap_unordered(_worker, [(a.seed + i, cfg) for i in range(a.games)]):
            for r in recs:
                f.write(json.dumps(r) + "\n"); n += 1
    print(f"wrote {n} net-in-Rust self-play records -> {a.out}")


if __name__ == "__main__":
    main()
