"""How much of a win is the DECK and how much is the PILOT? A rating-controlled fit.

The problem this solves. `tools/meta_aug.py`'s archetype table -- the one this workspace has been
navigating deck choice by -- reports raw win% per archetype. That number is confounded: an
archetype's win rate is partly the deck and partly the strength of whoever plays it. The
confound is not hypothetical. Marnie's Grimmsnarl wins 41.9% in the 850-1000 band and 50.7% in
the 1000+ band; it is the same 60 cards, so ~9 points of "archetype win rate" is pilot quality.

Model. For each seat of each decided game, with r = the pilot's public-leaderboard rating,

    P(i beats j) = sigmoid( a * (r_i - r_j) / 400  +  d[arch_i] - d[arch_j] )

`a` is how much rating actually predicts the result (a sanity check on the join: it must come out
clearly positive) and `d[arch]` is the archetype's intrinsic contribution with pilot strength
held fixed. d is identified up to a constant, so it is centred on the field-share-weighted mean;
report it in win-probability terms against an average deck piloted by an equal-rated opponent.

Fitted by full-batch gradient ascent on the log-likelihood with L2 shrinkage on d (which also
keeps thin archetypes from running off), and 95% CIs by resampling GAMES (not seats -- the two
seats of one game are one observation, and bootstrapping seats would halve the interval).

Caching. Extracting seats means parsing every replay, which is slow and identical every run, so
the extraction is cached to a small CSV; pass --cache to reuse it.

Usage:
  ./scripts/run.sh -m tools.deck_strength --zip 'data/ep_aug/*.zip' 'data/ep_aug09/*.json' \
      --lb 'data/lb_now/pokemon-tcg-ai-battle-publicleaderboard-*.csv' \
      --cache data/meta_aug/seats.csv
"""
import argparse
import csv
import glob
import json
import os
import random
from collections import Counter, defaultdict

import numpy as np

from tools.meta_aug import archetype, card_data, iter_replays

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_ratings(paths):
    r = {}
    for p in paths:
        for row in csv.DictReader(open(p, encoding="utf-8-sig")):
            try:
                r[row["TeamName"]] = float(row["Score"])
            except (KeyError, TypeError, ValueError):
                continue
    return r


def extract_fast(sources, ratings, names):
    """Same output as extract(), via prefix scanning instead of full JSON parse.

    A replay is ~6 MB but the team names, the result and both 60-card registrations all live in
    the first few hundred KB, so a full parse of a 21 GB dump is ~10x more work than the question
    needs. Validated against extract() on the 08-08 zip -- see RESEARCH.md.
    """
    import zipfile
    from tools.frontier_deck_watch import scan, _TEAMS, _REWARDS, _ARR

    def parse_blob(blob):
        mt, mr = _TEAMS.search(blob), _REWARDS.search(blob)
        if not mt or not mr or mr.group(1) == b"null" or mr.group(2) == b"null":
            return None
        try:
            teams = json.loads(b"[" + mt.group(1) + b"]")
        except Exception:
            return None
        r = (int(mr.group(1)), int(mr.group(2)))
        if r[0] == r[1] or len(teams) != 2:
            return None
        decks = [json.loads(m.group(0)) for m in _ARR.finditer(blob)][:2]
        return (teams, r, decks) if len(decks) == 2 else None

    N = 512 * 1024
    games, miss, skipped = [], 0, 0
    for src in sources:
        if src.endswith(".zip"):
            with zipfile.ZipFile(src) as zf:
                blobs = ((n, zf.open(n).read(N)) for n in zf.namelist() if n.endswith(".json"))
                for _n, blob in blobs:
                    got = parse_blob(blob)
                    if got is None:
                        skipped += 1
                        continue
                    teams, r, decks = got
                    rt = [ratings.get(t) for t in teams]
                    if rt[0] is None or rt[1] is None:
                        miss += 1
                        continue
                    w = 0 if r[0] > r[1] else 1
                    lab = [archetype(decks[i], names) for i in (0, 1)]
                    games.append((lab[w], rt[w], lab[1 - w], rt[1 - w]))
        else:
            got = scan(src, N)
            if got is None:
                skipped += 1
                continue
            teams, r, decks = got
            rt = [ratings.get(t) for t in teams]
            if rt[0] is None or rt[1] is None:
                miss += 1
                continue
            w = 0 if r[0] > r[1] else 1
            lab = [archetype(decks[i], names) for i in (0, 1)]
            games.append((lab[w], rt[w], lab[1 - w], rt[1 - w]))
    print(f"extracted {len(games)} decided games with both ratings "
          f"({miss} dropped: team not on LB; {skipped} replays unusable by prefix scan)")
    return games


def extract(zips, ratings, names):
    """One row per GAME: (arch_w, r_w, arch_l, r_l) -- seat 0 is the winner."""
    games = []
    miss = 0
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
            games.append((lab[w], rt[w], lab[1 - w], rt[1 - w]))
        except Exception:
            continue
    print(f"extracted {len(games)} decided games with both ratings ({miss} dropped: team not on LB)")
    return games


def fit(games, arch_ix, n_arch, l2=1.0, iters=4000, lr=0.5):
    """Returns (a, d) maximising the log-likelihood. Winner is always seat 0, so y == 1."""
    wi = np.array([arch_ix[g[0]] for g in games])
    li = np.array([arch_ix[g[2]] for g in games])
    dr = np.array([(g[1] - g[3]) / 400.0 for g in games])
    a = 0.0
    d = np.zeros(n_arch)
    n = len(games)
    for _ in range(iters):
        z = a * dr + d[wi] - d[li]
        p = 1.0 / (1.0 + np.exp(-z))
        resid = 1.0 - p                     # y == 1 for every row
        ga = float(np.dot(resid, dr)) / n
        gd = np.zeros(n_arch)
        np.add.at(gd, wi, resid)
        np.add.at(gd, li, -resid)
        gd = gd / n - l2 * d / n
        a += lr * ga * 10.0
        d += lr * gd * 10.0
        d -= d.mean()
    return a, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", nargs="*", default=[])
    ap.add_argument("--lb", nargs="+", required=True)
    ap.add_argument("--cache", default=os.path.join(_ROOT, "data", "meta_aug", "seats.csv"))
    ap.add_argument("--min-games", type=int, default=60)
    ap.add_argument("--boot", type=int, default=300)
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--slow", action="store_true", help="full JSON parse instead of prefix scan")
    a = ap.parse_args()

    if os.path.exists(a.cache):
        games = []
        for row in csv.reader(open(a.cache)):
            games.append((row[0], float(row[1]), row[2], float(row[3])))
        print(f"loaded {len(games)} games from cache {a.cache}")
    else:
        zips = []
        for pat in a.zip:
            zips.extend(sorted(glob.glob(pat)) or [pat])
        lbs = []
        for pat in a.lb:
            lbs.extend(sorted(glob.glob(pat)) or [pat])
        ratings = load_ratings(lbs)
        print(f"{len(ratings)} teams on the leaderboard; {len(zips)} replay sources")
        names = card_data()
        games = extract(zips, ratings, names) if a.slow else extract_fast(zips, ratings, names)
        os.makedirs(os.path.dirname(a.cache) or ".", exist_ok=True)
        with open(a.cache, "w", newline="") as f:
            csv.writer(f).writerows(games)
        print(f"cached -> {a.cache}")

    seats = Counter()
    wins = Counter()
    for aw, _rw, al, _rl in games:
        seats[aw] += 1
        seats[al] += 1
        wins[aw] += 1
    keep = {k for k, v in seats.items() if v >= a.min_games}
    games = [g for g in games if g[0] in keep and g[2] in keep]
    arch = sorted(keep)
    ix = {k: i for i, k in enumerate(arch)}
    print(f"{len(arch)} archetypes with >= {a.min_games} seats; {len(games)} games usable")

    aa, d = fit(games, ix, len(arch), l2=a.l2)

    # bootstrap over GAMES
    rng = random.Random(12345)
    boot = np.zeros((a.boot, len(arch)))
    boota = np.zeros(a.boot)
    n = len(games)
    for b in range(a.boot):
        samp = [games[rng.randrange(n)] for _ in range(n)]
        ba, bd = fit(samp, ix, len(arch), l2=a.l2, iters=1200)
        boot[b] = bd
        boota[b] = ba
    lo = np.percentile(boot, 2.5, axis=0)
    hi = np.percentile(boot, 97.5, axis=0)

    print(f"\nrating coefficient a = {aa:.3f}  (95% CI {np.percentile(boota,2.5):.3f} "
          f"to {np.percentile(boota,97.5):.3f})")
    print("  -> a 400-point rating edge is worth "
          f"{100/(1+np.exp(-aa)):.1f}% win probability. If this is not clearly above 50%, the "
          "rating join is broken and nothing below means anything.")

    print("\n=== INTRINSIC ARCHETYPE STRENGTH, PILOT RATING HELD FIXED ===")
    print("d is in log-odds; 'deck-only win%' = the win rate this deck would post against an "
          "average deck\n piloted by an equally-rated opponent. 'raw win%' is the confounded "
          "number meta_aug reports.")
    print(f"\n{'archetype':44s} {'seats':>6s} {'raw win%':>9s} {'deck-only':>10s} "
          f"{'95% CI':>16s} {'confound':>9s}")
    rows = []
    for k in arch:
        i = ix[k]
        raw = 100 * wins[k] / seats[k]
        deck = 100 / (1 + np.exp(-d[i]))
        rows.append((k, seats[k], raw, deck, 100 / (1 + np.exp(-lo[i])),
                     100 / (1 + np.exp(-hi[i])), deck - raw))
    rows.sort(key=lambda x: -x[3])
    for k, s, raw, deck, l, h, cf in rows:
        print(f"{k[:43]:44s} {s:6d} {raw:8.1f}% {deck:9.1f}% "
              f"{l:6.1f}-{h:5.1f}% {cf:+8.1f}")

    # mean |confound| tells you how badly the raw table misranks decks
    cf = np.array([r[6] for r in rows])
    print(f"\nmean |raw - deck-only| = {np.abs(cf).mean():.1f} points; "
          f"largest {np.abs(cf).max():.1f}")

    out = os.path.join(_ROOT, "data", "meta_aug", "deck_strength.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["archetype", "seats", "raw_win_pct", "deck_only_win_pct", "ci_lo", "ci_hi"])
        for k, s, raw, deck, l, h, _c in rows:
            w.writerow([k, s, round(raw, 2), round(deck, 2), round(l, 2), round(h, 2)])
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
