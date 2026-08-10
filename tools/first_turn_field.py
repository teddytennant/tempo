"""How does the real ladder answer the turn-order toss, BY ARCHETYPE?

`SelectContext.IS_FIRST` (41) is asked once per game, before the opening hand is dealt. Our
specialist dispatch is board-visibility based, so at that moment nothing is visible and every
archetype specialist is bypassed — the decision falls through to a generic default. We fixed that
for one archetype after measuring 91/93 real Lucario pilots answering YES; this tool generalises the
measurement to **every** archetype in the dump, so the same fix can be applied to another specialist
on evidence rather than by analogy.

Reads the public episode zip directly (no extraction), finds each IS_FIRST decision, attributes it
to the answering seat's 60-card deck, labels the deck by archetype, and tabulates YES/NO — overall,
and split by whether that seat went on to win.

  ./scripts/run.sh -m tools.first_turn_field --zip data/ep_aug/*.zip --episodes 1200
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import random
import sys
import zipfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tools"))

from meta_from_replays import card_names, decks_and_winner, fp, label  # noqa: E402

IS_FIRST = 41
YES, NO = 1, 2   # OptionType.YES / OptionType.NO


def scan(rep, names, out, cache):
    decks, winner = decks_and_winner(rep)
    if len(decks) < 2:
        return
    lab = {}
    for ai, d in decks.items():
        key = fp(d)
        if key not in cache:
            cache[key] = label(key, names)
        lab[ai] = cache[key]

    for step in rep.get("steps") or []:
        for ai, a in enumerate(step):
            ob = (a or {}).get("observation") or {}
            sel = ob.get("select")
            if not isinstance(sel, dict) or sel.get("context") != IS_FIRST:
                continue
            act = (a or {}).get("action")
            opts = sel.get("option") or []
            if not isinstance(act, list) or len(act) != 1:
                continue
            i = act[0]
            if not (isinstance(i, int) and 0 <= i < len(opts)):
                continue
            t = (opts[i] or {}).get("type")
            if t not in (YES, NO):
                continue
            arch = lab.get(ai, "unknown")
            rec = out[arch]
            rec["n"] += 1
            rec["yes"] += 1 if t == YES else 0
            if winner is not None:
                if winner == ai:
                    rec["win_n"] += 1
                    rec["win_yes"] += 1 if t == YES else 0
                # Did going first actually pay, across all asked seats?
                rec["first_wins"] += 1 if (t == YES) == (winner == ai) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="")
    ap.add_argument("--episodes", type=int, default=1200)
    ap.add_argument("--min-n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    path = args.zip or (sorted(glob.glob(os.path.join(_ROOT, "data", "ep_aug", "*.zip")))
                        or [""])[0]
    assert path and os.path.exists(path), f"episode zip not found: {path!r}"

    names = card_names()
    z = zipfile.ZipFile(path)
    members = z.namelist()
    random.Random(args.seed).shuffle(members)
    members = members[:args.episodes]

    out = collections.defaultdict(lambda: {"n": 0, "yes": 0, "win_n": 0, "win_yes": 0,
                                           "first_wins": 0})
    cache = {}
    read = 0
    for m in members:
        try:
            rep = json.loads(z.read(m))
        except Exception:
            continue
        read += 1
        try:
            scan(rep, names, out, cache)
        except Exception:
            continue
        if read % 200 == 0:
            print(f"  ...{read} episodes, {len(out)} archetypes", flush=True)

    tot = {"n": 0, "yes": 0, "win_n": 0, "win_yes": 0, "first_wins": 0}
    for rec in out.values():
        for k in tot:
            tot[k] += rec[k]

    print("\n" + "=" * 84)
    print(f"IS_FIRST answers by archetype — {read} episodes from {os.path.basename(path)}")
    print(f"{'archetype':<44}{'n':>6}{'YES%':>8}{'winners YES%':>14}{'first-won%':>12}")
    rows = sorted(out.items(), key=lambda kv: -kv[1]["n"])
    for arch, r in rows:
        if r["n"] < args.min_n:
            continue
        wy = f"{100.0*r['win_yes']/r['win_n']:.1f}" if r["win_n"] else "-"
        fw = f"{100.0*r['first_wins']/r['n']:.1f}" if r["n"] else "-"
        print(f"{arch[:43]:<44}{r['n']:>6}{100.0*r['yes']/r['n']:>7.1f}%{wy:>13}%{fw:>11}%")

    print("-" * 84)
    print(f"{'ALL':<44}{tot['n']:>6}{100.0*tot['yes']/max(1,tot['n']):>7.1f}%"
          f"{100.0*tot['win_yes']/max(1,tot['win_n']):>13.1f}%"
          f"{100.0*tot['first_wins']/max(1,tot['n']):>11.1f}%")
    print("\n'first-won%' = of the seats that were ASKED, how often the seat that ended up going "
          "first\nwon the game. It is a field-wide estimate of the value of the turn itself, not "
          "of the answer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
