"""Mine exact 60-card decklists per team from daily replay data.

The deck-selection frame is steps[1]: each agent's `action` is its 60 card ids. Aggregates the
modal decklist per team (teams occasionally switch lists mid-day), counting only games the team
WON so the list we copy is the one that actually performs.

Usage:
  python3 tools/extract_decklists.py --zip path/to/episodes.zip --team "The Debauchery Tea Party"
  python3 tools/extract_decklists.py --dir data/episodes_daily/raw_0701 --top 15
"""
import argparse
import csv
import glob
import io
import json
import os
import zipfile
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iter_replays(zip_path=None, dir_path=None):
    if zip_path:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                try:
                    yield json.load(io.TextIOWrapper(zf.open(name), encoding="utf-8"))
                except Exception:
                    continue
    else:
        for f in glob.glob(os.path.join(dir_path, "**", "*.json"), recursive=True):
            try:
                yield json.load(open(f))
            except Exception:
                continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip")
    ap.add_argument("--dir")
    ap.add_argument("--team", action="append", default=[])
    ap.add_argument("--top", type=int, default=0, help="also report the N most-winning teams")
    ap.add_argument("--out-dir", default=os.path.join(_ROOT, "data", "decks", "mined"))
    a = ap.parse_args()

    lists = defaultdict(Counter)   # team -> Counter of decklist tuples (wins only)
    wins = Counter()
    for rep in iter_replays(a.zip, a.dir):
        try:
            teams = rep.get("info", {}).get("TeamNames", [])
            r = rep.get("rewards") or [0, 0]
            ra = r[0] if r[0] is not None else 0
            rb = r[1] if len(r) > 1 and r[1] is not None else 0
            if ra == rb:
                continue
            w = 0 if ra > rb else 1
            team = teams[w] if w < len(teams) else "?"
            wins[team] += 1
            act = rep["steps"][1][w].get("action")
            if isinstance(act, list) and len(act) == 60:
                lists[team][tuple(act)] += 1
        except Exception:
            continue

    targets = list(a.team)
    if a.top:
        targets += [t for t, _ in wins.most_common(a.top) if t not in targets]
    os.makedirs(a.out_dir, exist_ok=True)
    for team in targets:
        if team not in lists or not lists[team]:
            print(f"{team!r}: no winning decklists found")
            continue
        (deck, cnt), total = lists[team].most_common(1)[0], sum(lists[team].values())
        safe = "".join(c if c.isalnum() else "_" for c in team)[:40]
        out = os.path.join(a.out_dir, f"{safe}.csv")
        with open(out, "w") as f:
            f.write("\n".join(str(c) for c in deck) + "\n")
        print(f"{team!r}: {total} wins, modal list {cnt}/{total} distinct={len(lists[team])} -> {out}")


if __name__ == "__main__":
    main()
