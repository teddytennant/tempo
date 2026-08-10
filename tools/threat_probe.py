"""How often does the shipped agent hand the opponent the game on the last move of its turn?

The prize-trade angle is on file as settled at the *offensive* level: swing-or-end agreement 88%,
attack-choice deviation 6/133, the "don't over-expose the Mega ex" guard measured harmful. What was
never measured is the defensive half of a prize trade — after we swing, can they swing back and take
their last prizes?

`agent/threat.py` answers that with a proof rather than a heuristic (see its docstring). This probe
runs it over real ladder MAIN decisions and reports:

  gated          the plausibility gate opened (opponent within one KO of their last prize, or we
                 have no bench) AND the scorer's move ends the turn -> the search actually ran
  chosen_loses   applying the SHIPPED agent's own move provably lets the opponent win next turn
  saved          ...and some other turn-ending option provably does not

plus the falsification the offensive verifier gets: the corpus is decisions from games the frontier
player WON, so in a position where our move provably loses, what did the elite actually play? If the
elite's move is one of the alternatives we would switch to, the proof is corroborated by a human-
level player who went on to win. If the elite played the very move we call losing and still won, the
proof is a phantom and the mechanism must not ship.

    ./scripts/run.sh -m tools.threat_probe --src experiments/luc_majkel_v6_src --n 2500
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN_CTX = 0
ATTACK = 13
END = 14
_TYPE_NAME = {13: "ATTACK", 14: "END"}


def _load(path, n):
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
            if sel.get("context") != MAIN_CTX or len(sel.get("option") or []) < 2:
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
    ap.add_argument("--n", type=int, default=2500)
    ap.add_argument("--gate", type=int, default=-1, help="override threat.OPP_PRIZE_GATE")
    ap.add_argument("--no-opp-attach", action="store_true",
                    help="forbid the opponent to ATTACH inside the fork (energy-zone falsification)")
    ap.add_argument("--elite-move", action="store_true",
                    help="judge the ELITE's own move instead of ours -- if it proves losing just as "
                         "often, the verifier is describing the position, not the move")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import threat as T
    import agent.main as M

    if a.gate >= 0:
        T.OPP_PRIZE_GATE = a.gate
    if a.no_opp_attach:
        T.OPP_MAY_ATTACH = False
        print("opponent ATTACH disabled inside the fork")
    if a.elite_move:
        print("judging the ELITE's move, not ours")

    deck_path = os.path.join(src, "agent", "deck.csv")
    with open(deck_path) as f:
        decklist = [int(x) for x in f.read().splitlines() if x.strip()]

    recs = _load(a.recs, a.n)
    print(f"src={src}\ndeck={deck_path} ({len(decklist)} cards)\nMAIN records: {len(recs)}")

    stats = {}
    lat = []
    fired = []
    agent_err = 0
    for i, r in enumerate(recs):
        obs_d = r["obs"]
        if a.elite_move:
            got = list(r.get("action") or [])
        else:
            try:
                got = M.agent(obs_d)
            except Exception:
                agent_err += 1
                continue
        if not isinstance(got, list) or not got:
            agent_err += 1
            continue
        before = dict(stats)
        t0 = time.perf_counter()
        alt = T.threat_alternative(obs_d, decklist, None, got, _stats=stats)
        lat.append((time.perf_counter() - t0) * 1000.0)
        if stats.get("chosen_loses", 0) > before.get("chosen_loses", 0):
            opts = obs_d["select"]["option"]
            fired.append({
                "i": i,
                "turn": obs_d["current"].get("turn"),
                "ours": [_TYPE_NAME.get(opts[j]["type"], str(opts[j]["type"])) for j in got],
                "elite": [_TYPE_NAME.get(opts[j]["type"], str(opts[j]["type"]))
                          for j in (r.get("action") or []) if j < len(opts)],
                "elite_idx": list(r.get("action") or []),
                "our_idx": list(got),
                "alt": list(alt) if alt else None,
                "opp_prizes": len(obs_d["current"]["players"][1 - obs_d["current"]["yourIndex"]]["prize"]),
            })

    lat.sort()

    def q(p):
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0.0

    gated = stats.get("gated", 0)
    loses = stats.get("chosen_loses", 0)
    saved = stats.get("saved", 0)
    print(f"\nagent errors            {agent_err}")
    print(f"search ran (gated)      {gated}  ({100.0*gated/max(len(recs),1):.1f}% of MAIN)")
    print(f"chosen move LOSES       {loses}")
    print(f"alternative found       {saved}")
    print(f"\nlatency ms  p50 {q(0.50):.2f}  p99 {q(0.99):.2f}  max {max(lat) if lat else 0:.2f}")

    # falsification: what did the elite (who WON this game) play in those positions?
    same = diff = alt_matches = 0
    for f in fired:
        if f["elite_idx"] == f["our_idx"]:
            same += 1
        else:
            diff += 1
            if f["alt"] is not None and f["alt"] == f["elite_idx"]:
                alt_matches += 1
    if fired:
        print(f"\nin the {len(fired)} positions where our move provably loses, the ELITE (who won):")
        print(f"  played the SAME move        {same}   <- phantom proof if this dominates")
        print(f"  played a DIFFERENT move     {diff}")
        print(f"    ...the exact move we switch to  {alt_matches}")
        print("\n  sample:")
        for f in fired[:15]:
            print(f"    turn {f['turn']:>3} oppPrizes {f['opp_prizes']}  ours={f['ours']} "
                  f"elite={f['elite']} alt={f['alt']}")

    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"src": src, "recs": len(recs), "gated": gated, "loses": loses,
                       "saved": saved, "agent_err": agent_err,
                       "p50": q(0.50), "p99": q(0.99), "max": max(lat) if lat else 0,
                       "elite_same": same, "elite_diff": diff, "elite_is_alt": alt_matches,
                       "fired": fired}, fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
