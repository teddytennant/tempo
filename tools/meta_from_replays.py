"""Analyze downloaded ladder replays -> the real metagame (which decks win).

Each replay (kaggle competitions replay <id>) has both players' 60-card deck (their deck-selection
action) and the winner. We fingerprint decks and tally frequency + win-rate, so deck decisions and
local opponents are grounded in what the field actually plays — not guesses. Names from card data.
"""
import collections
import csv
import glob
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def card_names():
    m = {}
    with open(os.path.join(_ROOT, "data", "raw", "EN_Card_Data.csv"), newline="") as f:
        for row in csv.DictReader(f):
            cid = row["Card ID"].strip()
            if cid.isdigit() and int(cid) not in m:
                m[int(cid)] = (row["Card Name"].strip(),
                               row["Stage (Pokémon)/Type (Energy and Trainer)"].strip())
    return m


def decks_and_winner(rep):
    decks = {}
    for step in rep["steps"][:3]:
        for ai, a in enumerate(step):
            act = a.get("action")
            if isinstance(act, list) and len(act) == 60:
                decks[ai] = act
    r = rep.get("rewards") or [0, 0]
    winner = 0 if r[0] > r[1] else 1 if r[1] > r[0] else None
    return decks, winner


def fp(deck):
    return tuple(sorted(collections.Counter(deck).items()))


def label(fp_tuple, names):
    # name a deck by its distinctive Pokémon (highest-stage / ex)
    poke = [(cid, n) for (cid, _c) in fp_tuple for (n, st) in [names.get(cid, ("?", ""))]
            if "Pokémon" in st and st != "Basic Energy"]
    megas = [n for cid, n in poke if "Mega" in names.get(cid, ("", ""))[0] or "ex" in n]
    key = megas[:2] or [n for _c, n in poke][:2]
    return " / ".join(key) if key else "unknown"


def main():
    names = card_names()
    files = glob.glob(os.path.join(_ROOT, "data", "episodes", "*replay*.json"))
    stats = collections.defaultdict(lambda: {"games": 0, "wins": 0, "teams": set()})
    n_games = 0
    for f in files:
        try:
            rep = json.load(open(f))
        except Exception:
            continue
        teams = rep.get("info", {}).get("TeamNames", ["?", "?"])
        decks, winner = decks_and_winner(rep)
        if not decks:
            continue
        n_games += 1
        for ai, dk in decks.items():
            s = stats[fp(dk)]
            s["games"] += 1
            if winner == ai:
                s["wins"] += 1
            if ai < len(teams):
                s["teams"].add(teams[ai])
    print(f"parsed {n_games} games from {len(files)} replays; {len(stats)} distinct decks\n")
    rank = sorted(stats.items(), key=lambda kv: kv[1]["games"], reverse=True)
    print(f"{'deck':42s} {'seen':>5s} {'winrate':>8s}  teams")
    for fpt, s in rank[:15]:
        wr = s["wins"] / s["games"] if s["games"] else 0
        print(f"{label(fpt, names)[:42]:42s} {s['games']:>5d} {wr:>7.0%}  "
              f"{', '.join(list(s['teams'])[:3])}")


if __name__ == "__main__":
    main()
