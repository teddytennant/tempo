"""Extract a TOP-PLAYER behavior-cloning corpus from ladder replays.

Behavior cloning the *whole field* teaches the ~600-Elo average. To build a policy with a
1300+ ceiling we must imitate only the best: this extracts winning decisions made by the
top teams (by public leaderboard score), dropping everyone else.

Pairs observation[i] (ACTIVE, select!=None) with action[i+1] for the same agent (kaggle-environments'
off-by-one), validates the action against the option list, and emits one record per winning
top-team decision:
  {"obs": <obs_dict>, "action": [idx...], "team": str, "context": int}

Usage:
  # download daily datasets first, then:
  python3 tools/extract_bc_top.py \
      --episodes 'data/episodes_daily/**/*replay*.json' \
      --leaderboard /path/to/leaderboard.csv --min-score 1150 \
      --out data/bc_top/records.jsonl
"""
import argparse
import csv
import glob
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Fallback teacher set (public leaderboard >1150 as of 2026-06-24) if no --leaderboard given.
_DEFAULT_TOP_TEAMS = {
    "keidroid", "Mogja J", "tomatomato", "Jaga", "TG_Aetheryx", "カドラバ Kadoraba", "yamy893",
    "Yushin Ito", "Kimiaki Nakamura", "Yasuo 0/10/0", "Safiullah Baig", "uuji-qvp", "yomogi mochi",
    "Kohenyan", "katsudon 421", "CYLik", "Karolina Kafel", "Ryosei Kojima", "UBI=ISHI",
    "kashiwashira", "カントー地方マスター", "blue0620", "みがわり", "TrustHub hiroingk", "monnosuke",
    "nattomaki", "EF", "Team kuma", "Gotem Penguin", "FirstSS-Sub", "milix", "halup",
}


def load_top_teams(leaderboard, min_score):
    if not leaderboard or not os.path.exists(leaderboard):
        return set(_DEFAULT_TOP_TEAMS)
    teams = set()
    with open(leaderboard, newline="") as f:
        for row in csv.DictReader(f):
            try:
                if float(row.get("Score", 0)) >= min_score:
                    teams.add(row.get("TeamName", "").strip())
            except (ValueError, TypeError):
                continue
    return teams or set(_DEFAULT_TOP_TEAMS)


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default=os.path.join(_ROOT, "data", "top_episodes", "*replay*.json"),
                    help="glob for replay JSONs (use quotes; ** supported)")
    ap.add_argument("--leaderboard", default=None, help="leaderboard CSV to derive the teacher set")
    ap.add_argument("--min-score", type=float, default=1150.0)
    ap.add_argument("--out", default=os.path.join(_ROOT, "data", "bc_top", "records.jsonl"))
    ap.add_argument("--winners-only", action="store_true", default=True)
    a = ap.parse_args()

    top_teams = load_top_teams(a.leaderboard, a.min_score)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    files = sorted(glob.glob(a.episodes, recursive=True))
    print(f"teacher teams: {len(top_teams)} | replay files: {len(files)}")

    n_games = n_rec = n_top_games = dropped = 0
    teams_seen = {}
    with open(a.out, "w") as out:
        for f in files:
            try:
                rep = json.load(open(f))
            except Exception:
                continue
            teams = rep.get("info", {}).get("TeamNames", ["?", "?"])
            w = winner_of(rep)
            if w is None:
                continue
            winner_team = teams[w] if w < len(teams) else "?"
            teams_seen[winner_team] = teams_seen.get(winner_team, 0) + 1
            if winner_team not in top_teams:   # only learn from a top team's win
                continue
            steps = rep.get("steps", [])
            used = False
            for i in range(len(steps) - 1):
                ai = w  # learn only the winning (top) agent's decisions
                if ai >= len(steps[i]):
                    continue
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
                out.write(json.dumps({
                    "obs": o, "action": act, "won": True,
                    "team": winner_team, "context": sel.get("context"),
                }) + "\n")
            if used:
                n_top_games += 1
            n_games += 1

    print(f"games={n_games} top_team_wins={n_top_games} records={n_rec} dropped={dropped}")
    top_winners = sorted(teams_seen.items(), key=lambda kv: kv[1], reverse=True)[:12]
    print("winners seen (team:games):", top_winners)
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
