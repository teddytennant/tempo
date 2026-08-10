"""The win verifier is only consulted on the MAIN menu. Does the scorer break proven wins BELOW it?

`agent/lethal.py` proves "a sequence exists that wins the game this turn" and, since v6, keeps quiet
unless it can prove the scorer's own answer throws that win away. But it is only ever asked at
`SelectContext.MAIN`. Once the scorer has chosen to PLAY a card, the engine asks a *sub-select* —
which card, which target, where to attach — and nothing checks those. A proven win can be lost
there just as easily, and more invisibly.

Nothing about the search actually needs a MAIN menu: `search_begin` works from any agent
observation. The restriction was an assumption. `lethal.ALLOW_SUB_SELECT` lifts it (single-answer
sub-selects only), and this probe measures what lifting it is worth, with the same accounting the
MAIN-level change got:

  provable      a win this turn is provable from the sub-select itself
  preserved     the shipped agent's own sub-selection keeps it provable  -> the verifier must stay
                quiet, exactly as at MAIN
  THREW IT      the shipped sub-selection makes the win unprovable       -> a real save

    ./scripts/run.sh -m tools.lethal_sub_cost --src experiments/threat_probe_src --n 4000
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN_CTX = 0


def _load(path, n, sub_only=True):
    recs = []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            ctx = sel.get("context")
            if sub_only and ctx == MAIN_CTX:
                continue
            if len(sel.get("option") or []) < 2:
                continue
            if (sel.get("maxCount") or 1) != 1:
                continue
            if not obs.get("search_begin_input"):
                continue
            recs.append(r)
            if n and len(recs) >= n:
                break
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import lethal as L
    import agent.main as M

    deck_path = os.path.join(src, "agent", "deck.csv")
    with open(deck_path) as f:
        decklist = [int(x) for x in f.read().splitlines() if x.strip()]

    recs = _load(a.recs, a.n)
    print(f"src={src}\nsingle-answer SUB-SELECT records: {len(recs)}")

    L.ALLOW_SUB_SELECT = True
    provable = thrown = agent_err = 0
    lat = []
    hits = []
    ctxs = {}
    for i, r in enumerate(recs):
        obs_d = r["obs"]
        try:
            got = M.agent(obs_d)
        except Exception:
            agent_err += 1
            continue
        if not isinstance(got, list) or not got:
            agent_err += 1
            continue
        t0 = time.perf_counter()
        # defer_selection=None: "is a win provable at all from here?"
        raw = L.lethal_move(obs_d, decklist, None, None)
        # defer_selection=got: "...and does the shipped sub-selection keep it?"
        guarded = L.lethal_move(obs_d, decklist, None, got) if raw else None
        lat.append((time.perf_counter() - t0) * 1000.0)
        if raw:
            provable += 1
            ctx = obs_d["select"].get("context")
            ctxs[ctx] = ctxs.get(ctx, 0) + 1
            if guarded:
                thrown += 1
                hits.append({"i": i, "ctx": ctx, "turn": obs_d["current"].get("turn"),
                             "ours": list(got), "verifier": list(guarded),
                             "elite": list(r.get("action") or [])})

    lat.sort()

    def q(p):
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0.0

    print(f"\nagent errors                      {agent_err}")
    print(f"win provable from the sub-select  {provable}")
    print(f"  ...shipped answer KEPT it       {provable - thrown}")
    print(f"  ...shipped answer THREW it      {thrown}   <- the only positions this would change")
    print(f"\nlatency ms  p50 {q(0.50):.2f}  p99 {q(0.99):.2f}  max {max(lat) if lat else 0:.2f}")
    if ctxs:
        print(f"\nprovable-win sub-select contexts: "
              f"{sorted(ctxs.items(), key=lambda kv: -kv[1])}")
    if hits:
        agree = sum(1 for h in hits if h["verifier"] == h["elite"])
        print(f"\nin the {len(hits)} positions the verifier would override, it agrees with the "
              f"ELITE (who won) {agree} times, the shipped answer agrees "
              f"{sum(1 for h in hits if h['ours'] == h['elite'])} times")
        for h in hits[:20]:
            print(f"    ctx {h['ctx']:>3} turn {h['turn']:>3}  ours={h['ours']} "
                  f"verifier={h['verifier']} elite={h['elite']}")

    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"src": src, "recs": len(recs), "provable": provable, "thrown": thrown,
                       "agent_err": agent_err, "p50": q(0.50), "p99": q(0.99),
                       "max": max(lat) if lat else 0, "ctxs": ctxs, "hits": hits}, fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
