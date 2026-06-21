"""Extract behavior-cloning records from real ladder replays.

kaggle-environments stores an OFF-BY-ONE: the action at step i is the response to the observation
at step i-1, and only the ACTIVE agent is deciding. So we pair observation[i] (ACTIVE, select!=None)
with action[i+1] for the same agent, and validate the action against the option list (count in
[minCount,maxCount]; indices in range). Invalid pairs are dropped.

Emits one record per in-game decision:
  {"obs": <obs_dict>, "action": [idx...], "won": bool, "team": str, "context": int}

Run: python3 tools/extract_bc.py
"""
import glob
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(_ROOT, "data", "bc", "records.jsonl")


def winner_of(rep):
    r = rep.get("rewards") or [0, 0]
    return 0 if r[0] > r[1] else 1 if r[1] > r[0] else None


def valid(act, sel):
    if not isinstance(act, list):
        return False
    nopt = len(sel.get("option") or [])
    if nopt == 0:
        return False
    minc, maxc = sel.get("minCount", 0), sel.get("maxCount", 0)
    if not (minc <= len(act) <= maxc):
        return False
    return all(isinstance(x, int) and 0 <= x < nopt for x in act) and len(set(act)) == len(act)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    files = sorted(glob.glob(os.path.join(_ROOT, "data", "episodes", "*replay*.json")))
    n_games = n_rec = n_win = dropped = 0
    ctx_hist = {}
    with open(OUT, "w") as out:
        for f in files:
            try:
                rep = json.load(open(f))
            except Exception:
                continue
            teams = rep.get("info", {}).get("TeamNames", ["?", "?"])
            w = winner_of(rep)
            steps = rep.get("steps", [])
            used = False
            for i in range(len(steps) - 1):
                for ai in range(len(steps[i])):
                    e = steps[i][ai]
                    if e.get("status") != "ACTIVE":
                        continue
                    o = e.get("observation") or {}
                    sel = o.get("select")
                    if not isinstance(sel, dict) or o.get("current") is None:
                        continue
                    nxt = steps[i + 1][ai] if ai < len(steps[i + 1]) else {}
                    act = nxt.get("action")
                    if not valid(act, sel):
                        dropped += 1
                        continue
                    n_rec += 1
                    used = True
                    if w == ai:
                        n_win += 1
                    c = sel.get("context")
                    ctx_hist[c] = ctx_hist.get(c, 0) + 1
                    out.write(json.dumps({
                        "obs": o, "action": act, "won": (w == ai),
                        "team": teams[ai] if ai < len(teams) else "?", "context": c,
                    }) + "\n")
            if used:
                n_games += 1
    print(f"games={n_games} decision_records={n_rec} winner_records={n_win} dropped={dropped}")
    top = sorted(ctx_hist.items(), key=lambda kv: kv[1], reverse=True)[:10]
    print("top contexts (ctx:count):", top)
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
