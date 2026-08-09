"""Prize-trade agreement: on REAL elite ladder decisions, how often do we play the move the
strong player actually played?

Our local arena is anti-predictive (it only measures which deck best exploits our own bots — see
RESEARCH.md), so policy changes cannot be justified by win rates any more. This harness replaces
it for *relative policy questions*: replay observations recorded from frontier players' winning
games and ask our deploy entry point what it would have done, bucketed by decision type. The
buckets that matter for prize-trade economics are the ones where an ATTACK option is on the table
and the ones where damage/KO targets are chosen.

It takes `--src`, so two candidate trees are scored on exactly the same decisions.

  ./scripts/run.sh -m tools.prize_agreement --src . --recs data/bc_lucario/records_11447.jsonl
  ./scripts/run.sh -m tools.prize_agreement --src experiments/luc_majkel_src --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ATTACK = 13
END = 14
RETREAT = 12

# Contexts in which the engine is asking *where to put damage / what to knock out*. Prize-trade
# decisions in the literal sense: the wrong target here throws away a prize.
TARGET_CTX = {13, 14, 15, 25}          # DAMAGE_COUNTER, DAMAGE_COUNTER_ANY, DAMAGE, EFFECT_TARGET
SETUP_CTX = {1, 2}                     # SETUP_ACTIVE_POKEMON, SETUP_BENCH_POKEMON


def _bucket(obs, action):
    """Which analysis buckets does this decision belong to?"""
    sel = obs["select"]
    ctx = sel.get("context")
    opts = sel.get("option") or []
    types = [o.get("type") for o in opts]
    out = ["all"]
    if ctx == 0:
        out.append("main")
        n_atk = types.count(ATTACK)
        if n_atk:
            out.append("main/attack-available")
            elite_attacked = any(types[i] == ATTACK for i in action if i < len(types))
            out.append("main/elite-attacked" if elite_attacked else "main/elite-declined-attack")
            # Pure prize-trade decisions, with the turn-ordering confound removed: the only
            # things on the table are swinging (one way or another) and ending the turn, so
            # "we developed the board first and attacked later" cannot explain a disagreement.
            if all(t in (ATTACK, END, RETREAT) for t in types):
                out.append("main/swing-or-end")
            if n_atk > 1:
                out.append("main/attack-choice")
                if elite_attacked:
                    out.append("main/attack-choice+attacked")
    elif ctx in TARGET_CTX:
        out.append("target")
    elif ctx in SETUP_CTX:
        out.append("setup")
    else:
        out.append("other")
    return out


def _load(path, n, won_only):
    recs = []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if won_only and not r.get("won"):
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            act = r.get("action")
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            opts = sel.get("option") or []
            if len(opts) < 2:
                continue                      # forced move: agreement is vacuous
            if not (isinstance(act, list) and act):
                continue
            if any((not isinstance(i, int)) or i < 0 or i >= len(opts) for i in act):
                continue
            recs.append(r)
            if n and len(recs) >= n:
                break
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT, help="tree containing agent/ (repo root or a packed build)")
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=0, help="cap records (0 = all)")
    ap.add_argument("--won-only", action="store_true", default=True)
    ap.add_argument("--all-games", dest="won_only", action="store_false")
    ap.add_argument("--json", default="", help="write per-bucket results here")
    ap.add_argument("--show-disagreements", type=int, default=0)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import agent.main as M

    recs = _load(a.recs, a.n, a.won_only)
    print(f"src={src}\nrecs={len(recs)} (won_only={a.won_only}) from {a.recs}")

    hit = Counter()
    tot = Counter()
    errors = 0
    # What we do instead, when the elite attacked and we did not.
    instead = Counter()
    shown = 0

    for r in recs:
        obs, act = r["obs"], r["action"]
        try:
            got = M.agent(obs)
        except Exception:
            errors += 1
            continue
        if not isinstance(got, list):
            errors += 1
            continue
        agree = set(got) == set(act)
        buckets = _bucket(obs, act)
        for b in buckets:
            tot[b] += 1
            if agree:
                hit[b] += 1
        if not agree and "main/elite-attacked" in buckets:
            types = [o.get("type") for o in obs["select"]["option"]]
            picked = [types[i] for i in got if i < len(types)]
            instead[tuple(sorted(picked))] += 1
            if shown < a.show_disagreements:
                shown += 1
                print(f"\n-- disagreement #{shown}: elite={act} ours={got}")
                print(f"   option types={types}")

    order = ["all", "main", "main/attack-available", "main/elite-attacked",
             "main/elite-declined-attack", "main/swing-or-end", "main/attack-choice",
             "main/attack-choice+attacked", "target", "setup", "other"]
    print(f"\n{'bucket':<30} {'n':>7} {'agree':>7} {'pct':>7}")
    results = {}
    for b in order:
        if not tot[b]:
            continue
        pct = 100.0 * hit[b] / tot[b]
        results[b] = {"n": tot[b], "agree": hit[b], "pct": round(pct, 2)}
        print(f"{b:<30} {tot[b]:>7} {hit[b]:>7} {pct:>6.2f}%")
    if errors:
        print(f"\nAGENT ERRORS: {errors}")
    if instead:
        print("\nWhen the elite ATTACKED and we did not, we played (option types):")
        for k, v in instead.most_common(8):
            print(f"  {list(k)}  x{v}")

    if a.json:
        with open(a.json, "w") as f:
            json.dump({"src": src, "recs": len(recs), "errors": errors, "buckets": results}, f, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
