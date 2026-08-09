"""Confound-free probe of the energy-ATTACH target decision.

tools/tempo_agreement.py showed main/attach-to-bench agreement at 18.6% vs 52.4% for
attach-to-active, but raw agreement over-penalises benign turn ordering (we play a card first
and attach later in the same turn, which scores as a disagreement).

This probe removes that confound entirely: it keeps only decisions where the elite attached AND
we also attached, so both players committed the energy at the same decision point and the only
thing that can differ is the TARGET. It then reports the target choice cross-tab conditioned on
board state (what is active, how much energy it already has, what is on the bench), which is what
tells us whether our "fill the active attacker first" rule is right.

  ./scripts/run.sh -m tools.attach_probe --src experiments/luc_majkel_v2_src
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ATTACH = 8
ACTIVE = 4
BENCH = 5


def _area(o):
    a = o.get("inPlayArea")
    return "ACTIVE" if a == ACTIVE else ("BENCH" if a == BENCH else f"A{a}")


def _load(path):
    out = []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if not r.get("won"):
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            act = r.get("action")
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            if sel.get("context") != 0:
                continue
            opts = sel.get("option") or []
            if len(opts) < 2 or not (isinstance(act, list) and act):
                continue
            if any((not isinstance(i, int)) or i < 0 or i >= len(opts) for i in act):
                continue
            types = [o.get("type") for o in opts]
            if ATTACH not in types:
                continue
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--dump", type=int, default=0)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import agent.main as M
    from agent import lucario_rules as LR

    recs = _load(a.recs)
    print(f"src={src}\nMAIN decisions with an ATTACH on the table: {len(recs)}")

    crosstab = Counter()          # (elite_area, our_area)
    by_state = Counter()          # (elite_area, our_area, active_at_goal)
    elite_bench_state = Counter()  # what the elite's board looked like when they benched energy
    goal_hist = Counter()
    dumped = 0

    for r in recs:
        obs, act = r["obs"], r["action"]
        opts = obs["select"]["option"]
        elite = [opts[i] for i in act if i < len(opts)]
        if not any(o.get("type") == ATTACH for o in elite):
            continue
        try:
            got = M.agent(obs)
        except Exception:
            continue
        ours = [opts[i] for i in got if i < len(opts)]
        if not any(o.get("type") == ATTACH for o in ours):
            continue        # elite attached, we did something else -> ordering confound, skip
        eo = [o for o in elite if o.get("type") == ATTACH][0]
        oo = [o for o in ours if o.get("type") == ATTACH][0]
        crosstab[(_area(eo), _area(oo))] += 1

        # Board context: is our active already at its energy goal under the current rule?
        cur = obs["current"]
        me = cur["yourIndex"]
        st = cur["players"][me] if "players" in cur else cur["playerState"][me]
        act_list = st.get("active") or []
        active = act_list[0] if act_list else None
        aid = (active or {}).get("id")
        n_en = len((active or {}).get("energies") or [])
        goal = LR.LUCARIO_ENERGY_GOAL if aid in LR._LUCARIO_LINE else (
            LR.HARIYAMA_ENERGY_GOAL if aid == LR.HARIYAMA else 99)
        at_goal = n_en >= goal
        by_state[(_area(eo), _area(oo), f"active_at_goal={at_goal}")] += 1
        if _area(eo) == "BENCH":
            bench = [b for b in (st.get("bench") or []) if b]
            tgt_i = eo.get("inPlayIndex")
            tgt = bench[tgt_i] if tgt_i is not None and tgt_i < len(bench) else None
            elite_bench_state[(
                f"active={aid}", f"activeE={n_en}",
                f"tgt={(tgt or {}).get('id')}", f"tgtE={len((tgt or {}).get('energies') or [])}",
            )] += 1
            goal_hist[(aid, n_en, at_goal)] += 1
        if a.dump and dumped < a.dump and _area(eo) != _area(oo):
            dumped += 1
            print(f"\n-- mismatch #{dumped}: elite->{_area(eo)}[{eo.get('inPlayIndex')}] "
                  f"ours->{_area(oo)}[{oo.get('inPlayIndex')}] turn={cur.get('turn')}")
            print(f"   active id={aid} E={n_en} goal={goal}")
            print(f"   bench={[(b.get('id'), len(b.get('energies') or [])) for b in (st.get('bench') or []) if b]}")

    tot = sum(crosstab.values())
    print(f"\nBOTH attached at the same decision point: n={tot}  (confound-free)")
    print(f"{'elite':>8} {'ours':>8} {'n':>6} {'pct':>7}")
    for k, v in crosstab.most_common():
        print(f"{k[0]:>8} {k[1]:>8} {v:>6} {100.0*v/tot:>6.1f}%")

    e_bench = sum(v for k, v in crosstab.items() if k[0] == "BENCH")
    o_bench = sum(v for k, v in crosstab.items() if k[1] == "BENCH")
    print(f"\nelite chose BENCH {e_bench}/{tot} = {100.0*e_bench/tot:.1f}%"
          f"   we chose BENCH {o_bench}/{tot} = {100.0*o_bench/tot:.1f}%")
    same = sum(v for k, v in crosstab.items() if k[0] == k[1])
    print(f"same AREA agreement: {same}/{tot} = {100.0*same/tot:.1f}%")

    print("\nconditioned on whether our active is already at its energy goal:")
    for k, v in sorted(by_state.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  elite->{k[0]:<7} ours->{k[1]:<7} {k[2]:<22} x{v}")

    print("\nwhen the ELITE attached to the BENCH, board looked like (top 15):")
    for k, v in elite_bench_state.most_common(15):
        print(f"  {'  '.join(k)}  x{v}")

    print("\n(activeId, activeEnergy, atGoal) when elite benched the energy:")
    for k, v in goal_hist.most_common(15):
        print(f"  {k}  x{v}")


if __name__ == "__main__":
    main()
