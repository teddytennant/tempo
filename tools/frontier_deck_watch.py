"""Did the frontier change its decklist? A cheap prefix-scan of a day's replays.

Why. We ship a copy of a specific frontier player's 60-card list, so the single most actionable
deck-construction question each day is "is that still what they are playing?". Answering it with
`meta_aug` costs a full parse of a 21 GB dump.

This does not parse the JSON. A replay's keys are emitted in the order
`configuration, description, id, info, ..., rewards, ..., steps, ...`, and the two 60-card deck
registrations are the first actions inside `steps`, so a few hundred KB of prefix contains the
team names, the result and both decklists. We regex them out of that prefix. On a miss (a replay
whose prefix does not contain everything) the file is simply skipped and counted -- this is a
sampling instrument, not a census, and it says so in its output.

Usage:
  ./scripts/run.sh -m tools.frontier_deck_watch --dir data/ep_aug09 --team Majkel1337 \
      --compare experiments/luc_majkel_v3_src/agent/deck.csv
"""
import argparse
import csv
import glob
import json
import os
import re
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_TEAMS = re.compile(rb'"TeamNames"\s*:\s*\[(.*?)\]', re.S)
_REWARDS = re.compile(rb'"rewards"\s*:\s*\[\s*(-?\d+|null)\s*,\s*(-?\d+|null)\s*\]')
_ARR = re.compile(rb'\[(?:\s*\d+\s*,){59}\s*\d+\s*\]')


def scan(path, prefix_bytes):
    with open(path, "rb") as f:
        blob = f.read(prefix_bytes)
    mt = _TEAMS.search(blob)
    mr = _REWARDS.search(blob)
    if not mt or not mr:
        return None
    try:
        teams = json.loads(b"[" + mt.group(1) + b"]")
    except Exception:
        return None
    if mr.group(1) == b"null" or mr.group(2) == b"null":
        return None
    r = (int(mr.group(1)), int(mr.group(2)))
    if r[0] == r[1]:
        return None
    decks = [json.loads(m.group(0)) for m in _ARR.finditer(blob)][:2]
    if len(decks) != 2 or len(teams) != 2:
        return None
    return teams, r, decks


def card_names():
    m = {}
    with open(os.path.join(_ROOT, "data", "raw", "EN_Card_Data.csv"), newline="") as f:
        for row in csv.DictReader(f):
            cid = row["Card ID"].strip()
            if cid.isdigit() and int(cid) not in m:
                m[int(cid)] = row["Card Name"].strip()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", nargs="+", required=True, help="dirs or globs of replay .json files")
    ap.add_argument("--team", nargs="+", required=True)
    ap.add_argument("--compare", default=None, help="a 60-line deck.csv to diff against")
    ap.add_argument("--prefix-kb", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    paths = []
    for d in a.dir:
        paths.extend(sorted(glob.glob(os.path.join(d, "*.json")) if os.path.isdir(d) else glob.glob(d)))
    if a.limit:
        paths = paths[:a.limit]
    want = set(a.team)
    print(f"scanning {len(paths)} replays, first {a.prefix_kb} KB of each, for {sorted(want)}")

    lists = {t: Counter() for t in want}
    rec = {t: [0, 0] for t in want}
    hit = miss = 0
    for p in paths:
        got = scan(p, a.prefix_kb * 1024)
        if got is None:
            miss += 1
            continue
        hit += 1
        teams, r, decks = got
        w = 0 if r[0] > r[1] else 1
        for i in (0, 1):
            t = teams[i]
            if t in want:
                lists[t][tuple(decks[i])] += 1
                rec[t][0] += 1
                rec[t][1] += 1 if i == w else 0
    print(f"prefix-scan usable on {hit}/{len(paths)} replays ({miss} skipped)\n")

    names = card_names()
    base = None
    if a.compare:
        base = Counter(int(x) for x in open(a.compare).read().split())
        print(f"comparing against {a.compare} ({sum(base.values())} cards)\n")

    for t in a.team:
        c = lists[t]
        if not c:
            print(f"{t}: no games found in this dump")
            continue
        g, w = rec[t]
        print(f"=== {t} — {g} games, {w} wins ({100*w/g:.1f}%), "
              f"{len(c)} distinct 60-card list(s) ===")
        for deck, n in c.most_common(4):
            print(f"  {n:4d} games on a list", end="")
            if base is not None:
                d = Counter(deck)
                diff = {k: d.get(k, 0) - base.get(k, 0)
                        for k in set(d) | set(base) if d.get(k, 0) != base.get(k, 0)}
                if not diff:
                    print("  == IDENTICAL to --compare")
                else:
                    print(f"  differs from --compare on {sum(abs(v) for v in diff.values())} card slots:")
                    for k, v in sorted(diff.items(), key=lambda x: -abs(x[1])):
                        print(f"       {v:+d}  {names.get(k, '?' + str(k))}")
            else:
                print()
        print()


if __name__ == "__main__":
    main()
