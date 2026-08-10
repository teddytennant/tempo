"""The metagame SPLIT BY RATING BAND, and the deck-choice objective that follows from it.

Why this exists. `tools/meta_aug.py` reports one global archetype table over the whole ladder.
But matchmaking pairs an agent with opponents near its own rating, so the field a 650-rated agent
actually plays is NOT the global field -- and deck choice should be optimised against the field we
face, not against the one the top 20 face.

Method. Episode JSON carries `info.TeamNames` but no rating, so ratings are joined from the public
leaderboard CSV on team name. Each SEAT of each decided game is then attributed to a rating band,
and we report:

  A. archetype share + win% WITHIN each band
  B. for a chosen band, the opponent-archetype distribution we would face
  C. the field-weighted expected win rate of every archetype against that distribution,
     using matchup win rates measured inside the band where n is sufficient and globally otherwise

(C) is the deck-choice objective function, computed entirely from real ladder games. It is the
thing our anti-predictive self-play arena cannot answer.

Usage:
  ./scripts/run.sh -m tools.meta_bands --zip data/ep_aug/*.zip data/ep_aug09/*.json \
      --lb data/lb_now/pokemon-tcg-ai-battle-publicleaderboard-*.csv --band 550 800
"""
import argparse
import csv
import glob
import json
import os
from collections import Counter, defaultdict

from tools.meta_aug import archetype, card_data, iter_replays

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BANDS = [(-9999, 400), (400, 550), (550, 700), (700, 850), (850, 1000), (1000, 9999)]


def band_of(score):
    for lo, hi in BANDS:
        if lo <= score < hi:
            return (lo, hi)
    return None


def band_name(b):
    lo, hi = b
    return f"{'<' if lo < 0 else lo}-{'+' if hi > 5000 else hi}" if lo < 0 or hi > 5000 \
        else f"{lo}-{hi}"


def load_ratings(paths):
    r = {}
    for p in paths:
        for row in csv.DictReader(open(p, encoding="utf-8-sig")):
            try:
                r[row["TeamName"]] = float(row["Score"])
            except (KeyError, TypeError, ValueError):
                continue
    return r


def collect(zips, ratings, names):
    """-> list of (team, rating, archetype, opp_archetype, opp_rating, won) per seat."""
    seats = []
    n = miss = 0
    for rep in iter_replays(zips):
        try:
            rw = rep.get("rewards") or [0, 0]
            if rw[0] is None or rw[1] is None or rw[0] == rw[1]:
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
            rt = [ratings.get(teams[i]) for i in (0, 1)]
            if rt[0] is None or rt[1] is None:
                miss += 1
                continue
            w = 0 if rw[0] > rw[1] else 1
            lab = {i: archetype(decks[i], names) for i in (0, 1)}
            n += 1
            for i in (0, 1):
                seats.append((teams[i], rt[i], lab[i], lab[1 - i], rt[1 - i], 1 if i == w else 0))
        except Exception:
            continue
    print(f"parsed {n} decided games with both ratings joined ({miss} games dropped: team not on LB)")
    return seats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", nargs="+", required=True)
    ap.add_argument("--lb", nargs="+", required=True)
    ap.add_argument("--band", nargs=2, type=float, default=[550, 700],
                    help="the band WE occupy; report C is computed against its opponents")
    ap.add_argument("--min-games", type=int, default=40)
    ap.add_argument("--min-matchup", type=int, default=12)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    zips = []
    for pat in a.zip:
        zips.extend(sorted(glob.glob(pat)) or [pat])
    lbs = []
    for pat in a.lb:
        lbs.extend(sorted(glob.glob(pat)) or [pat])

    ratings = load_ratings(lbs)
    print(f"{len(ratings)} teams on the leaderboard; {len(zips)} replay sources")
    seats = collect(zips, ratings, card_data())

    # ---- A. archetype table per band -------------------------------------------------
    per_band = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for _t, rt, lab, _ol, _orr, won in seats:
        b = band_of(rt)
        per_band[b][lab][0] += 1
        per_band[b][lab][1] += won

    print("\n=== A. ARCHETYPE TABLE BY RATING BAND (share of seats in band, win% in band) ===")
    for b in BANDS:
        d = per_band.get(b)
        if not d:
            continue
        tot = sum(v[0] for v in d.values())
        rows = [(k, v[0], v[1] / v[0]) for k, v in d.items() if v[0] >= a.min_games]
        rows.sort(key=lambda x: -x[1])
        print(f"\n-- band {band_name(b)}  ({tot} seats) --")
        print(f"{'archetype':44s} {'seats':>6s} {'share':>7s} {'win%':>6s}")
        for k, g, wr in rows[:12]:
            print(f"{k[:43]:44s} {g:6d} {100*g/tot:6.1f}% {100*wr:5.1f}%")

    # ---- B. the field WE face ---------------------------------------------------------
    lo, hi = a.band
    ours = [s for s in seats if lo <= s[1] < hi]
    opp = Counter(s[3] for s in ours)
    topp = sum(opp.values())
    print(f"\n=== B. OPPONENT ARCHETYPES FACED IN BAND {lo:.0f}-{hi:.0f}  ({topp} seats) ===")
    for k, c in opp.most_common(14):
        print(f"{k[:43]:44s} {c:6d} {100*c/topp:6.1f}%")

    # ---- C. field-weighted expected win rate ------------------------------------------
    # matchup win rates: prefer in-band, fall back to global when the in-band cell is thin
    mu_band = defaultdict(lambda: [0, 0])
    mu_glob = defaultdict(lambda: [0, 0])
    for _t, rt, lab, ol, _orr, won in seats:
        mu_glob[(lab, ol)][0] += 1
        mu_glob[(lab, ol)][1] += won
        if lo <= rt < hi:
            mu_band[(lab, ol)][0] += 1
            mu_band[(lab, ol)][1] += won

    cand = [k for k, v in Counter(s[2] for s in seats).items() if v >= a.min_games]
    weights = {k: c / topp for k, c in opp.items()}

    print(f"\n=== C. EXPECTED WIN RATE vs THE {lo:.0f}-{hi:.0f} FIELD "
          f"(weighted by B; in-band matchups where n>={a.min_matchup}, else global) ===")
    print(f"{'archetype (if we could pilot it)':44s} {'E[win%]':>8s} {'cover':>7s} {'n_band':>7s}")
    out_rows = []
    for c in cand:
        num = den = 0.0
        nb = 0
        for oarch, w in weights.items():
            cell = mu_band.get((c, oarch))
            if cell and cell[0] >= a.min_matchup:
                wr = cell[1] / cell[0]
                nb += cell[0]
            else:
                g = mu_glob.get((c, oarch))
                if not g or g[0] < 5:
                    continue
                wr = g[1] / g[0]
            num += w * wr
            den += w
        if den < 0.55:          # too little of the faced field is covered to trust the number
            continue
        out_rows.append((c, num / den, den, nb))
    out_rows.sort(key=lambda x: -x[1])
    for c, ev, den, nb in out_rows:
        print(f"{c[:43]:44s} {100*ev:7.1f}% {100*den:6.0f}% {nb:7d}")

    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["archetype", "exp_win_pct_vs_band", "field_coverage_pct", "n_band_games"])
            for c, ev, den, nb in out_rows:
                w.writerow([c, round(100 * ev, 2), round(100 * den, 1), nb])
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
