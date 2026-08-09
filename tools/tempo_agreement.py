"""Energy / tempo agreement: on REAL elite ladder decisions, where does our sequencing of
energy attachment, retreat and bench development differ from a frontier player's?

Sibling of tools/prize_agreement.py (same corpus, same deploy entry point, same --src A/B
mechanics) but bucketed for the *tempo* question instead of the prize-trade one:

  main/attach-available      an ATTACH option is on the table at MAIN
  main/elite-attached        ... and the elite took it        <- did we also attach?
  main/elite-declined-attach ... and the elite did not
  main/attach-to-active      the elite attached to the ACTIVE spot
  main/attach-to-bench       the elite attached to a BENCH spot
  main/attach-choice         >1 distinct attach option (which target / which card)
  main/retreat-available     a RETREAT option is on the table
  main/elite-retreated       ... and the elite retreated
  main/play-available        a PLAY (card from hand) option is on the table
  attach-target              sub-select: ATTACH_FROM / ATTACH_TO (ctx 21/22)
  bench-select               sub-select: SWITCH / TO_ACTIVE / TO_BENCH / TO_FIELD (ctx 3-6)

The headline diagnostic is the CONFUSION table: when the elite attached and we did not, what
did we do instead (by option type)? A tempo leak shows up as a systematic "elite ATTACH -> we
END" or "elite ATTACH -> we ATTACK".

  ./scripts/run.sh -m tools.tempo_agreement --src . --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# OptionType
PLAY = 7
ATTACH = 8
EVOLVE = 9
ABILITY = 10
RETREAT = 12
ATTACK = 13
END = 14

_TYPE_NAME = {0: "NUMBER", 1: "YES", 2: "NO", 3: "CARD", 4: "TOOL", 5: "ENERGY_CARD",
              6: "ENERGY", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
              11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL",
              16: "SPECIAL_CONDITION"}

# AreaType
ACTIVE = 4
BENCH = 5

# SelectContext
ATTACH_CTX = {21, 22}                  # ATTACH_FROM, ATTACH_TO
BENCH_CTX = {3, 4, 5, 6}               # SWITCH, TO_ACTIVE, TO_BENCH, TO_FIELD


def _tname(t):
    return _TYPE_NAME.get(t, str(t))


def _bucket(obs, action):
    sel = obs["select"]
    ctx = sel.get("context")
    opts = sel.get("option") or []
    types = [o.get("type") for o in opts]
    chosen = [opts[i] for i in action if i < len(opts)]
    ctypes = [o.get("type") for o in chosen]
    out = ["all"]
    if ctx == 0:
        out.append("main")
        n_att = types.count(ATTACH)
        if n_att:
            out.append("main/attach-available")
            if ATTACH in ctypes:
                out.append("main/elite-attached")
                tgt = {o.get("inPlayArea") for o in chosen if o.get("type") == ATTACH}
                if ACTIVE in tgt:
                    out.append("main/attach-to-active")
                if BENCH in tgt:
                    out.append("main/attach-to-bench")
            else:
                out.append("main/elite-declined-attach")
            # More than one distinct attach (different source card and/or different target)
            keys = {(o.get("index"), o.get("inPlayArea"), o.get("inPlayIndex"))
                    for o in opts if o.get("type") == ATTACH}
            if len(keys) > 1:
                out.append("main/attach-choice")
        if RETREAT in types:
            out.append("main/retreat-available")
            out.append("main/elite-retreated" if RETREAT in ctypes
                       else "main/elite-declined-retreat")
        if PLAY in types:
            out.append("main/play-available")
    elif ctx in ATTACH_CTX:
        out.append("attach-target")
    elif ctx in BENCH_CTX:
        out.append("bench-select")
    else:
        out.append("other")
    return out


def _load(path, n, won_only):
    recs = []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if won_only and not r.get("won"):
                continue
            obs = r.get("obs") or {}
            sel = obs.get("select")
            act = r.get("action")
            if not isinstance(sel, dict) or obs.get("current") is None:
                continue
            opts = sel.get("option") or []
            if len(opts) < 2:
                continue
            if not (isinstance(act, list) and act):
                continue
            if any((not isinstance(i, int)) or i < 0 or i >= len(opts) for i in act):
                continue
            recs.append(r)
            if n and len(recs) >= n:
                break
    return recs


ORDER = ["all", "main", "main/attach-available", "main/elite-attached",
         "main/elite-declined-attach", "main/attach-to-active", "main/attach-to-bench",
         "main/attach-choice", "main/retreat-available", "main/elite-retreated",
         "main/elite-declined-retreat", "main/play-available",
         "attach-target", "bench-select", "other"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--won-only", action="store_true", default=True)
    ap.add_argument("--all-games", dest="won_only", action="store_false")
    ap.add_argument("--json", default="")
    ap.add_argument("--dump-attach-misses", type=int, default=0,
                    help="print this many 'elite attached, we did not' positions in full")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    import agent.main as M

    recs = _load(a.recs, a.n, a.won_only)
    print(f"src={src}\nrecs={len(recs)} (won_only={a.won_only}) from {a.recs}")

    hit, tot = Counter(), Counter()
    errors = 0
    attach_confusion = Counter()      # elite attached, we played X
    retreat_confusion = Counter()     # elite retreated, we played X
    decline_confusion = Counter()     # elite declined attach, we attached anyway?
    attach_target_miss = Counter()    # elite attached to A, we attached to B
    shown = 0

    for r in recs:
        obs, act = r["obs"], r["action"]
        try:
            got = M.agent(obs)
        except Exception:
            errors += 1
            continue
        if not isinstance(got, list):
            errors += 1
            continue
        agree = set(got) == set(act)
        buckets = _bucket(obs, act)
        for b in buckets:
            tot[b] += 1
            if agree:
                hit[b] += 1
        if agree:
            continue
        opts = obs["select"]["option"]
        ours = [opts[i] for i in got if i < len(opts)]
        otypes = tuple(sorted(_tname(o.get("type")) for o in ours))
        if "main/elite-attached" in buckets:
            if ATTACH in [o.get("type") for o in ours]:
                el = [o for o in (opts[i] for i in act if i < len(opts))
                      if o.get("type") == ATTACH]
                ou = [o for o in ours if o.get("type") == ATTACH]
                attach_target_miss[
                    (f"elite->{'ACTIVE' if el[0].get('inPlayArea') == ACTIVE else 'BENCH'}"
                     f"[{el[0].get('inPlayIndex')}]",
                     f"ours->{'ACTIVE' if ou[0].get('inPlayArea') == ACTIVE else 'BENCH'}"
                     f"[{ou[0].get('inPlayIndex')}]")] += 1
            else:
                attach_confusion[otypes] += 1
                if shown < a.dump_attach_misses:
                    shown += 1
                    cur = obs["current"]
                    me = cur["yourIndex"]
                    st = cur["playerState"][me] if "playerState" in cur else None
                    print(f"\n-- attach-miss #{shown}: elite={act} ours={got} "
                          f"turn={cur.get('turn')} actionCount={cur.get('turnActionCount')}")
                    print(f"   opts={[ (i,_tname(o.get('type')),o.get('inPlayArea'),o.get('inPlayIndex')) for i,o in enumerate(opts) ]}")
                    if st:
                        print(f"   me active={st.get('active')}")
        if "main/elite-retreated" in buckets:
            retreat_confusion[otypes] += 1
        if "main/elite-declined-attach" in buckets and ATTACH in [o.get("type") for o in ours]:
            decline_confusion[otypes] += 1

    print(f"\n{'bucket':<30} {'n':>7} {'agree':>7} {'pct':>7}")
    results = {}
    for b in ORDER:
        if not tot[b]:
            continue
        pct = 100.0 * hit[b] / tot[b]
        results[b] = {"n": tot[b], "agree": hit[b], "pct": round(pct, 2)}
        print(f"{b:<30} {tot[b]:>7} {hit[b]:>7} {pct:>6.2f}%")
    if errors:
        print(f"\nAGENT ERRORS: {errors}")

    def _tbl(title, c):
        if not c:
            return
        print(f"\n{title}")
        for k, v in c.most_common(10):
            print(f"  {list(k)}  x{v}")

    _tbl("Elite ATTACHED, we did NOT — what we played instead:", attach_confusion)
    _tbl("Elite ATTACHED, we attached ELSEWHERE:", attach_target_miss)
    _tbl("Elite DECLINED to attach, we attached anyway:", decline_confusion)
    _tbl("Elite RETREATED, we played instead:", retreat_confusion)

    if a.json:
        with open(a.json, "w") as f:
            json.dump({"src": src, "recs": len(recs), "errors": errors, "buckets": results,
                       "attach_confusion": {str(k): v for k, v in attach_confusion.items()},
                       "attach_target_miss": {str(k): v for k, v in attach_target_miss.items()}},
                      f, indent=1)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
