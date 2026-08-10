"""On the SAME position, with the SAME menu: which options does the frontier take that we don't?

`tools/turn_replay.py` shows the frontier plays ~6.1 MAIN actions per turn to our ~5.1 and attaches
energy on 79.9% of turns to our 58.8% -- but a fork replay determinizes our draws, so "the elite
played Dusk Ball and we didn't" can just mean we never drew it.

This removes that confound completely by never forking. For every real MAIN decision in the corpus
it reads the elite's own option list, asks our deploy entry point the identical question, and scores
each option TWICE:

    offered      the option was on this menu
    elite took   the frontier chose it here
    we took      we chose it here

Both sides face the identical menu, so the take-rate difference is policy and nothing else. A card
we score below END never appears in "we took" no matter how often it is offered -- which is exactly
the shape a hard `return -1.0` guard makes.

    ./scripts/run.sh -m tools.card_use --src experiments/luc_majkel_v7_src --n 4000
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = 0

from tools.turn_replay import action_desc, _g, T_END  # noqa: E402


def _key(state, opt):
    d = action_desc(state, opt)
    if d is None:
        return ("END",)
    return d[:2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import agent.main as M
    from cg.api import all_card_data
    names = {c.cardId: c.name for c in all_card_data()}

    print(f"src={src}\ndeck={os.path.join(src, 'agent', 'deck.csv')}")

    offered = collections.Counter()
    elite_took = collections.Counter()
    we_took = collections.Counter()
    seen = agree = err = 0

    with open(a.recs) as f:
        for line in f:
            if a.n and seen >= a.n:
                break
            try:
                r = json.loads(line)
            except Exception:
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            st = obs.get("current")
            if not isinstance(sel, dict) or not isinstance(st, dict):
                continue
            if sel.get("context") != MAIN:
                continue
            opts = sel.get("option") or []
            act = r.get("action") or []
            if len(opts) < 2 or not act or not (0 <= act[0] < len(opts)):
                continue
            try:
                got = M.agent(obs)
            except Exception:
                err += 1
                continue
            if not isinstance(got, list) or not got or not (0 <= got[0] < len(opts)):
                err += 1
                continue
            seen += 1
            agree += (got[0] == act[0])
            # An option can appear several times on one menu (two copies of a card in hand);
            # count the menu once per distinct key so "offered" means "was available here".
            for k in {_key(st, o) for o in opts}:
                offered[k] += 1
            elite_took[_key(st, opts[act[0]])] += 1
            we_took[_key(st, opts[got[0]])] += 1

    print(f"\nMAIN decisions scored: {seen}   agent errors: {err}   "
          f"raw agreement: {100.0*agree/max(seen,1):.2f}%")

    def label(k):
        if k[0] == "END":
            return "END"
        cid = k[1] if len(k) > 1 else None
        return f"{k[0]}({names.get(cid, cid)})"

    rows = []
    for k, off in offered.items():
        e, w = elite_took[k], we_took[k]
        rows.append((off, k, e, w, (e - w) / max(off, 1)))
    rows.sort(key=lambda t: -(t[2] - t[3]))

    print(f"\n{'option':<34}{'offered':>8}{'elite took':>12}{'we took':>9}"
          f"{'elite%':>9}{'ours%':>8}")
    print("  -- the frontier takes these and we do not " + "-" * 30)
    for off, k, e, w, _ in rows[:18]:
        if e - w <= 0:
            break
        print(f"{label(k):<34}{off:>8}{e:>12}{w:>9}"
              f"{100.0*e/off:>8.1f}%{100.0*w/off:>7.1f}%")
    print("  -- we take these and the frontier does not " + "-" * 29)
    for off, k, e, w, _ in rows[::-1][:18]:
        if w - e <= 0:
            break
        print(f"{label(k):<34}{off:>8}{e:>12}{w:>9}"
              f"{100.0*e/off:>8.1f}%{100.0*w/off:>7.1f}%")

    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"src": src, "seen": seen, "agree": agree,
                       "rows": [[label(k), off, e, w] for off, k, e, w, _ in rows]},
                      fh, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
