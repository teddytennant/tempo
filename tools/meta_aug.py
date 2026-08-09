"""Mine a day's ladder replays -> the CURRENT metagame, matchup matrix, and per-team decklists.

Answers the questions a deck-construction run actually needs:
  1. Which archetypes do the strongest teams play right now?
  2. What is each archetype's win rate, and against whom does it lose?
  3. Where does OUR deck sit in that table, and which decks beat it?

Ratings are not in the replay JSON, so "strength" is proxied by a team's win count and by an
optional leaderboard CSV join (--lb) on team name.

Usage:
  ./scripts/run.sh -m tools.meta_aug --zip data/ep_aug/*.zip --out data/meta_aug
"""
import argparse
import csv
import io
import json
import os
import zipfile
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def card_data():
    """cid -> (name, stage/type)."""
    m = {}
    with open(os.path.join(_ROOT, "data", "raw", "EN_Card_Data.csv"), newline="") as f:
        for row in csv.DictReader(f):
            cid = row["Card ID"].strip()
            if cid.isdigit() and int(cid) not in m:
                m[int(cid)] = (row["Card Name"].strip(),
                               row["Stage (Pokémon)/Type (Energy and Trainer)"].strip())
    return m


def archetype(deck, names):
    """Name a 60-card list by its win condition: the highest-stage / ex Pokemon lines."""
    cnt = Counter(deck)
    poke = []
    for cid, c in cnt.items():
        nm, st = names.get(cid, ("?", "?"))
        if "Pok" not in st:          # 'Basic Pokémon' / 'Stage 1 Pokémon' / 'Stage 2 Pokémon'
            continue
        stage = 2 if "Stage 2" in st else 1 if "Stage 1" in st else 0
        special = 2 if nm.startswith("Mega ") else 1 if " ex" in nm or nm.endswith("ex") else 0
        poke.append((special, stage, c, nm))
    if not poke:
        return "no-pokemon"
    poke.sort(reverse=True)
    top = []
    for _s, _st, _c, nm in poke:
        base = nm.replace("Mega ", "").split(" ex")[0]
        if base not in top:
            top.append(base)
        if len(top) == 2:
            break
    return " / ".join(top)


def iter_replays(paths):
    for p in paths:
        if p.endswith(".zip"):
            try:
                with zipfile.ZipFile(p) as zf:
                    for name in zf.namelist():
                        if not name.endswith(".json"):
                            continue
                        try:
                            yield json.load(io.TextIOWrapper(zf.open(name), encoding="utf-8"))
                        except Exception:
                            continue
                continue
            except zipfile.BadZipFile:
                pass    # still downloading — fall back to walking local file headers
            from tools.zipstream import iter_members
            for _name, blob in iter_members(p):
                try:
                    yield json.loads(blob)
                except Exception:
                    continue
        else:
            try:
                yield json.load(open(p))
            except Exception:
                continue


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", nargs="+", required=True)
    ap.add_argument("--out", default=os.path.join(_ROOT, "data", "meta_aug"))
    ap.add_argument("--min-games", type=int, default=25)
    a = ap.parse_args()

    names = card_data()
    arch = defaultdict(lambda: {"g": 0, "w": 0})
    matchup = defaultdict(lambda: {"g": 0, "w": 0})       # (mine, theirs) -> from mine's view
    team_arch = defaultdict(Counter)                      # team -> archetype counter
    team_rec = defaultdict(lambda: {"g": 0, "w": 0})
    team_list = defaultdict(Counter)                      # team -> exact winning 60-card lists
    n = 0

    for rep in iter_replays(a.zip):
        try:
            r = rep.get("rewards") or [0, 0]
            if r[0] is None or r[1] is None or r[0] == r[1]:
                continue
            teams = rep.get("info", {}).get("TeamNames", ["?", "?"])
            decks = {}
            for step in rep["steps"][:3]:
                for i, ag in enumerate(step):
                    act = ag.get("action")
                    if isinstance(act, list) and len(act) == 60:
                        decks.setdefault(i, act)
            if len(decks) != 2:
                continue
            w = 0 if r[0] > r[1] else 1
            labels = {i: archetype(decks[i], names) for i in (0, 1)}
            n += 1
            for i in (0, 1):
                won = 1 if i == w else 0
                arch[labels[i]]["g"] += 1
                arch[labels[i]]["w"] += won
                matchup[(labels[i], labels[1 - i])]["g"] += 1
                matchup[(labels[i], labels[1 - i])]["w"] += won
                t = teams[i] if i < len(teams) else "?"
                team_arch[t][labels[i]] += 1
                team_rec[t]["g"] += 1
                team_rec[t]["w"] += won
                if won:
                    team_list[t][tuple(decks[i])] += 1
        except Exception:
            continue

    os.makedirs(a.out, exist_ok=True)
    print(f"parsed {n} decided games\n")

    print("=== ARCHETYPE TABLE (>= %d games) ===" % a.min_games)
    rows = [(k, v["g"], v["w"] / v["g"]) for k, v in arch.items() if v["g"] >= a.min_games]
    rows.sort(key=lambda x: -x[2])
    print(f"{'archetype':46s} {'games':>6s} {'share':>7s} {'win%':>6s}")
    tot = sum(v["g"] for v in arch.values())
    for k, g, wr in rows:
        print(f"{k[:45]:46s} {g:6d} {100*g/tot:6.1f}% {100*wr:5.1f}%")

    with open(os.path.join(a.out, "archetypes.csv"), "w", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["archetype", "games", "share_pct", "win_pct"])
        for k, g, wr in rows:
            wcsv.writerow([k, g, round(100 * g / tot, 2), round(100 * wr, 2)])

    print("\n=== TOP TEAMS BY WINS (their modal archetype) ===")
    for t, rec in sorted(team_rec.items(), key=lambda x: -x[1]["w"])[:30]:
        if rec["g"] < 10:
            continue
        top = team_arch[t].most_common(1)[0]
        print(f"{t[:34]:35s} {rec['w']:4d}W/{rec['g']:4d}G {100*rec['w']/rec['g']:5.1f}%  "
              f"{top[0][:38]:39s} ({100*top[1]/rec['g']:.0f}% of games)")

    with open(os.path.join(a.out, "teams.csv"), "w", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["team", "games", "wins", "win_pct", "modal_archetype"])
        for t, rec in sorted(team_rec.items(), key=lambda x: -x[1]["w"]):
            if rec["g"] < 5:
                continue
            wcsv.writerow([t, rec["g"], rec["w"], round(100 * rec["w"] / rec["g"], 2),
                           team_arch[t].most_common(1)[0][0]])

    with open(os.path.join(a.out, "matchups.csv"), "w", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["mine", "theirs", "games", "win_pct"])
        for (mi, th), v in sorted(matchup.items(), key=lambda x: -x[1]["g"]):
            if v["g"] >= 5:
                wcsv.writerow([mi, th, v["g"], round(100 * v["w"] / v["g"], 2)])

    # exact modal decklists for the winningest teams
    dl = os.path.join(a.out, "decks")
    os.makedirs(dl, exist_ok=True)
    kept = 0
    for t, rec in sorted(team_rec.items(), key=lambda x: -x[1]["w"]):
        if rec["w"] < 8 or not team_list[t]:
            continue
        deck, c = team_list[t].most_common(1)[0]
        safe = "".join(ch if ch.isalnum() else "_" for ch in t)[:38]
        with open(os.path.join(dl, f"{safe}.csv"), "w") as fh:
            fh.write("\n".join(str(x) for x in deck) + "\n")
        kept += 1
    print(f"\nwrote {kept} modal winning decklists -> {dl}")


if __name__ == "__main__":
    main()
