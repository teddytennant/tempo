"""How much of the verified in-turn search do we actually run?

`agent/lethal.py` is the one piece of *search* that ships: from a MAIN decision it explores the
engine's native forward model looking for a sequence of actions that wins the game THIS TURN, and
its answer is a proof, not an estimate. Unlike every heuristic-eval search this workspace has
refuted, it cannot be wrong about the value of its leaf.

But it is deliberately crippled on four axes, none of which was ever measured:

  PRIZE_GATE = 2      only search when the opponent has <= 2 prizes left
  _has_attack_option  only search when an ATTACK is *already* offered at the root
  _NODE_BUDGET = 600  / _MAX_TIME_S = 0.25
  _MAX_DEPTH = 10     selections deep into the turn

This probe replays REAL ladder MAIN decisions and runs the verifier under five configurations —
shipped, and each axis widened alone, and all widened together — so that a "wide finds a proven win
where shipped does not" event can be attributed to the axis responsible.

    ./scripts/run.sh -m tools.lethal_probe --src experiments/luc_majkel_v4_src --n 4000

Nothing here is a win-rate. A disagreement is a *proof* that a game-winning line existed and the
shipped agent did not look for it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ATTACK = 13
MAIN_CTX = 0

# (prize_gate, require_attack_option, node_budget, max_time_s, max_depth)
# One axis widened per config, so a "wide found a proof, ship did not" event is attributable.
# `gate` stops at 3 on purpose: a single KO yields at most 3 prizes (a Mega ex), so 3 is the
# largest prize count from which one knockout can end the game.
CONFIGS = {
    "ship":   (2, True,  600,   0.25, 10),
    "gate":   (3, True,  600,   0.25, 10),
    "noatk":  (2, False, 600,   0.25, 10),
    "budget": (2, True,  4000,  1.00, 10),
    "depth":  (2, True,  600,   0.25, 18),
    "wide":   (3, False, 4000,  1.00, 18),
    "widest": (6, False, 8000,  2.00, 22),
    # candidate ship configs: both cost filters opened, budget varied
    "cand1":  (3, False, 600,   0.25, 10),
    "cand2":  (3, False, 1500,  0.40, 10),
    "cand3":  (3, False, 3000,  0.60, 10),
    "gate6":  (6, False, 600,   0.25, 10),
}
AXES = ["gate", "noatk", "budget", "depth"]


def _load(path, n, won_only):
    """MAIN decisions with a real choice, in replay order."""
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
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            if sel.get("context") != MAIN_CTX:
                continue
            if len(sel.get("option") or []) < 2:
                continue
            if not obs.get("search_begin_input"):
                continue          # cannot fork the engine from this record
            recs.append(r)
            if n and len(recs) >= n:
                break
    return recs


def _segment_games(recs):
    """Records are in replay order and `turn` restarts at 0 each game, so a non-increase in turn
    across a game boundary segments them. Returns (game_id per record, last_turn per game)."""
    gid, last = [], []
    g, prev = 0, -1
    for r in recs:
        t = r["obs"]["current"].get("turn", 0)
        if t < prev:
            g += 1
        gid.append(g)
        prev = t
        while len(last) <= g:
            last.append(0)
        last[g] = max(last[g], t)
    return gid, last


def _shape(obs):
    """The cheap facts the gate is computed from — measurable without any search."""
    st = obs["current"]
    me_i = st["yourIndex"]
    opp = st["players"][1 - me_i]
    types = [o.get("type") for o in obs["select"].get("option") or []]
    return {
        "opp_prizes": len(opp.get("prize") or []),
        "opp_bench": len([b for b in (opp.get("bench") or []) if b is not None]),
        "has_attack": ATTACK in types,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--won-only", action="store_true", default=True)
    ap.add_argument("--all-games", dest="won_only", action="store_false")
    ap.add_argument("--configs", default="ship,gate,budget,depth,wide")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import lethal as L                       # the shipped module, from --src

    deck_path = os.path.join(src, "agent", "deck.csv")
    if not os.path.exists(deck_path):
        deck_path = os.path.join(src, "deck.csv")
    with open(deck_path) as f:
        decklist = [int(x) for x in f.read().splitlines() if x.strip()]
    print(f"src={src}\ndeck={deck_path} ({len(decklist)} cards)")

    want = [c for c in a.configs.split(",") if c in CONFIGS]
    recs = _load(a.recs, a.n, a.won_only)
    print(f"MAIN records: {len(recs)} (won_only={a.won_only})\nconfigs: {want}\n")

    # Pass 1 — pure gate arithmetic, no search at all. What fraction of real MAIN decisions does
    # the shipped gate refuse to even look at, and why?
    blocked = Counter()
    for r in recs:
        s = _shape(r["obs"])
        plausible = s["opp_prizes"] <= 2 or s["opp_bench"] == 0
        if not s["has_attack"] and not plausible:
            blocked["both"] += 1
        elif not s["has_attack"]:
            blocked["no-attack-option"] += 1
        elif not plausible:
            blocked["prizes>2"] += 1
        else:
            blocked["searched"] += 1
        if s["has_attack"] and s["opp_prizes"] == 3:
            blocked["prizes==3 & attack offered"] += 1
    print("gate arithmetic over all MAIN decisions:")
    for k, v in blocked.most_common():
        print(f"  {k:<28} {v:>6}  ({100.0*v/max(len(recs),1):5.2f}%)")

    # Pass 2 — actually run the verifier under each configuration.
    found = {c: set() for c in want}
    timing = defaultdict(list)
    errors = Counter()
    for c in want:
        pg, req_atk, nodes, tmax, depth = CONFIGS[c]
        L.PRIZE_GATE = pg
        L._NODE_BUDGET = nodes
        L._MAX_TIME_S = tmax
        L._MAX_DEPTH = depth
        # Trees shipped before 2026-08-10 hard-coded the attack-option gate; newer ones expose it
        # as REQUIRE_ATTACK_OPTION. Drive whichever this --src has.
        if hasattr(L, "REQUIRE_ATTACK_OPTION"):
            L.REQUIRE_ATTACK_OPTION = req_atk
        elif req_atk:
            L._has_attack_option = _orig_has_attack
        else:
            L._has_attack_option = lambda select: True
        t_cfg = time.monotonic()
        for i, r in enumerate(recs):
            t0 = time.monotonic()
            try:
                lm = L.lethal_move(r["obs"], decklist, None)
            except Exception:
                errors[c] += 1
                lm = None
            timing[c].append(time.monotonic() - t0)
            if isinstance(lm, list) and lm:
                found[c].add(i)
        el = time.monotonic() - t_cfg
        ts = sorted(timing[c])
        p50 = ts[len(ts) // 2] if ts else 0.0
        p99 = ts[int(len(ts) * 0.99)] if ts else 0.0
        print(f"\n[{c:<6}] proven wins {len(found[c]):>5} / {len(recs)}   "
              f"errors {errors[c]}   p50 {p50*1000:6.2f}ms  p99 {p99*1000:7.1f}ms  "
              f"max {max(ts)*1000 if ts else 0:7.1f}ms  wall {el:6.1f}s")

    if "ship" in found and "wide" in found:
        missed = found["wide"] - found["ship"]
        extra = found["ship"] - found["wide"]
        print(f"\nPROVEN WINS THE SHIPPED AGENT NEVER LOOKED FOR: {len(missed)}"
              f"  ({100.0*len(missed)/max(len(recs),1):.2f}% of MAIN decisions)")
        if extra:
            print(f"  (found by ship but not wide: {len(extra)} — nondeterminism/timeout noise)")
        # Attribute each miss to the single axis that recovers it.
        attrib = Counter()
        for i in missed:
            axes = [c for c in AXES if c in found and i in found[c]]
            attrib[",".join(axes) if axes else "interaction-only"] += 1
        print("  recovered by widening:")
        for k, v in attrib.most_common():
            print(f"    {k:<24} {v:>5}")
        # What the elite actually did in the positions we missed — a proven win we skipped should
        # coincide with the elite attacking.
        agree = 0
        for i in missed:
            act = recs[i].get("action") or []
            types = [o.get("type") for o in recs[i]["obs"]["select"].get("option") or []]
            if any(types[j] == ATTACK for j in act if j < len(types)):
                agree += 1
        if missed:
            print(f"  of those, the elite attacked in {agree}/{len(missed)} "
                  f"({100.0*agree/len(missed):.1f}%)")

    # ── falsification: a claimed proof should coincide with the game ENDING ──────────────────
    # The verifier's positives are supposed to be proofs, but the proof is taken under a
    # determinized deck/prize assignment, so a line that needs a lucky draw can be a phantom.
    # These are real games: if we claim "a win exists this turn" at turn t and the game demonstrably
    # ran on for many more turns, the elite (at <= 3 prizes, with an attack on the table) declined a
    # game-winning line — far less likely than our proof being fake.
    gid, last_turn = _segment_games(recs)
    print(f"\nfalsification — {max(gid) + 1} games segmented from {len(recs)} MAIN decisions")
    print(f"{'config':<8} {'claims':>7} {'elite-atk':>10} {'ended<=1t':>10} {'>=4t left':>10} {'median t left':>14}")
    for c in want:
        claims = sorted(found[c])
        if not claims:
            continue
        left, atk, ended, far = [], 0, 0, 0
        for i in claims:
            t = recs[i]["obs"]["current"].get("turn", 0)
            d = max(0, last_turn[gid[i]] - t)
            left.append(d)
            if d <= 1:
                ended += 1
            if d >= 4:
                far += 1
            types = [o.get("type") for o in recs[i]["obs"]["select"].get("option") or []]
            if any(types[j] == ATTACK for j in (recs[i].get("action") or []) if j < len(types)):
                atk += 1
        left.sort()
        print(f"{c:<8} {len(claims):>7} {100.0*atk/len(claims):>9.1f}% "
              f"{100.0*ended/len(claims):>9.1f}% {100.0*far/len(claims):>9.1f}% "
              f"{left[len(left)//2]:>14}")

    if a.json:
        out = {
            "src": src, "recs": len(recs), "gate": dict(blocked),
            "found": {c: sorted(found[c]) for c in want},
            "latency_ms": {c: {"p50": round(1000 * sorted(timing[c])[len(timing[c]) // 2], 3),
                               "max": round(1000 * max(timing[c]), 3)} for c in want if timing[c]},
        }
        with open(a.json, "w") as f:
            json.dump(out, f, indent=1)
        print(f"\nwrote {a.json}")


_orig_has_attack = None

if __name__ == "__main__":
    # capture the shipped gate before any config mutates it
    _src = os.path.abspath(sys.argv[sys.argv.index("--src") + 1]) if "--src" in sys.argv else _ROOT
    sys.path.insert(0, os.path.join(_src, "agent"))
    sys.path.insert(0, _src)
    import lethal as _L
    _orig_has_attack = _L._has_attack_option
    main()
