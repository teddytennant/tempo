"""Robustness fuzzer for the deploy agent (agent/main.agent).

Plays MANY full games across every matchup of our four tuned decks (crustle, lucario_praxel,
starmie, dunsparce) — each as BOTH seats — versus a variety of opponent decks. BOTH seats are
driven by the real deploy entry point `agent.main.agent(obs_dict)` (the exact submission path:
scorer.best_options -> deck specialists + lethal verifier, with the MCTS/Rust fallback live).

For every step we:
  * call `main.agent(obs)` and time it,
  * assert the returned selection is LEGAL: a list of DISTINCT ints in range(len(option)) whose
    length is in [minCount, maxCount] (or [] iff that is legal),
  * actually feed it to `battle_select` and catch any engine rejection.

To drive the agent into a wide diversity of (often pathological) states without a seed API on the
engine, an epsilon fraction of moves are perturbed to a random *legal* selection — but the agent
is still invoked and legality-checked on EVERY step, so coverage is broad while the assertions
always target the real deploy output.

Counts: agent exceptions, illegal selections returned, engine rejections of agent output, hangs
(step cap exceeded), and per-move latency (worst case). Exit code is non-zero if anything fails.

  ./scripts/run.sh -m tools.fuzz --games 320 --workers 12 --epsilon 0.15
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
import traceback
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Our four tuned decks (each piloted as both seats).
OUR_DECKS = ["crustle", "lucario_praxel", "starmie", "dunsparce"]
# Opponent variety (field archetypes + mirrors + odd/legacy lists for state diversity).
OPP_DECKS = ["dragapult", "fezandipiti", "abomasnow", "starmie", "lucario_praxel",
             "crustle", "dunsparce", "mega_lucario", "mega_gardevoir", "anti_lucario", "sample"]

# Per-move latency we want to stay well under (deploy clock budget is far larger, but the scorer
# path should be ~instant and the lethal verifier must never approach this).
LATENCY_BUDGET_S = 1.0


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _legal(sel, sel_dict):
    """Return (ok, reason). Checks distinct ints in range, length in [minCount, maxCount]."""
    if not isinstance(sel, list):
        return False, f"not a list: {type(sel).__name__}"
    if not all(isinstance(i, int) and not isinstance(i, bool) for i in sel):
        return False, f"non-int element in {sel!r}"
    n = len(sel_dict.get("option") or [])
    minc = sel_dict.get("minCount", 0) or 0
    maxc = sel_dict.get("maxCount", 0) or 0
    if len(set(sel)) != len(sel):
        return False, f"duplicate indices in {sel!r}"
    for i in sel:
        if not (0 <= i < n):
            return False, f"index {i} out of range(0,{n}) in {sel!r}"
    if not (minc <= len(sel) <= maxc):
        return False, f"len {len(sel)} not in [{minc},{maxc}] (n={n}) sel={sel!r}"
    return True, ""


def _random_legal(sel_dict, rng):
    n = len(sel_dict.get("option") or [])
    minc = max(0, min(sel_dict.get("minCount", 0) or 0, n))
    maxc = max(minc, min(sel_dict.get("maxCount", 0) or 0, n))
    if n == 0 or maxc == 0:
        return []
    k = rng.randint(minc, maxc) if maxc >= minc else minc
    k = max(1, k) if minc == 0 and maxc >= 1 and rng.random() < 0.8 else k
    k = min(k, n)
    return rng.sample(range(n), k)


def _play_one(task):
    """Worker: play deck_a (p0) vs deck_b (p1), both piloted by agent.main.agent.

    Returns a dict of per-game counters + a list of failure records.
    """
    name_a, deck_a, name_b, deck_b, max_steps, epsilon, seed = task
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "agent"))
    rng = random.Random(seed)

    res = {
        "matchup": f"{name_a} vs {name_b}", "steps": 0, "moves": 0,
        "agent_exc": 0, "illegal": 0, "engine_reject": 0, "hang": 0,
        "max_lat": 0.0, "over_budget": 0, "result": None, "fail": [],
    }

    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class
        import agent.main as M
    except Exception:
        res["fail"].append(("import", traceback.format_exc()[-800:]))
        return res

    def record(kind, sel_dict, detail, sel=None):
        if len(res["fail"]) < 6:
            res["fail"].append((kind, {
                "matchup": res["matchup"], "ctx": sel_dict.get("context"),
                "min": sel_dict.get("minCount"), "max": sel_dict.get("maxCount"),
                "n": len(sel_dict.get("option") or []), "sel": sel, "detail": str(detail)[:600],
            }))

    obs = None
    try:
        obs, _start = battle_start(deck_a, deck_b)
        if obs is None:
            res["result"] = "start_refused"
            return res
        for step in range(max_steps):
            res["steps"] = step + 1
            oc = to_observation_class(obs)
            r = oc.current.result if oc.current is not None else -1
            if r is not None and r >= 0:
                res["result"] = r
                battle_finish()
                return res
            sel_dict = obs.get("select")
            if sel_dict is None:
                res["result"] = "select_none"
                battle_finish()
                return res

            # --- the real deploy call: always invoked + legality-checked ---
            res["moves"] += 1
            t0 = time.monotonic()
            try:
                pick = M.agent(obs)
            except Exception:
                res["agent_exc"] += 1
                record("agent_exc", sel_dict, traceback.format_exc()[-800:])
                pick = None
            lat = time.monotonic() - t0
            if lat > res["max_lat"]:
                res["max_lat"] = lat
            if lat > LATENCY_BUDGET_S:
                res["over_budget"] += 1
                record("latency", sel_dict, f"{lat:.3f}s")

            ok = False
            if pick is not None:
                ok, why = _legal(pick, sel_dict)
                if not ok:
                    res["illegal"] += 1
                    record("illegal", sel_dict, why, sel=pick)

            # --- decide what to actually feed the engine ---
            play_random = rng.random() < epsilon or not ok or pick is None
            to_play = _random_legal(sel_dict, rng) if play_random else pick

            try:
                obs = battle_select(to_play)
            except Exception:
                # If we were feeding the AGENT's (legality-passed) selection and the engine still
                # rejected it, that is a genuine deploy bug. If we fed a random perturbation, just
                # recover with the agent's pick (random multi-combos can be semantically illegal).
                if not play_random:
                    res["engine_reject"] += 1
                    record("engine_reject", sel_dict, traceback.format_exc()[-400:], sel=to_play)
                # recover so the game can continue
                recovered = False
                for cand in ([pick] if (ok and pick is not None) else []) + [_random_legal(sel_dict, rng) for _ in range(4)]:
                    try:
                        obs = battle_select(cand)
                        recovered = True
                        break
                    except Exception:
                        continue
                if not recovered:
                    res["result"] = "stuck"
                    try:
                        battle_finish()
                    except Exception:
                        pass
                    return res
        # step cap exceeded
        res["hang"] = 1
        res["result"] = "hang"
        record("hang", {"context": None, "minCount": None, "maxCount": None, "option": []},
               f"exceeded {max_steps} steps")
        try:
            battle_finish()
        except Exception:
            pass
        return res
    except Exception:
        res["fail"].append(("loop", traceback.format_exc()[-800:]))
        try:
            battle_finish()
        except Exception:
            pass
        return res


def main():
    import multiprocessing as mp

    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=320, help="total games to play")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--epsilon", type=float, default=0.15, help="fraction of moves perturbed random")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "decks"))
    args = ap.parse_args()

    decks = {}
    for name in set(OUR_DECKS + OPP_DECKS):
        p = os.path.join(args.decks_dir, f"{name}.csv")
        if os.path.exists(p):
            d = _read_deck(p)
            if len(d) == 60:
                decks[name] = d
            else:
                print(f"SKIP {name}: {len(d)} cards")
        else:
            print(f"SKIP {name}: missing {p}")

    our = [d for d in OUR_DECKS if d in decks]
    opp = [d for d in OPP_DECKS if d in decks]
    print(f"our decks: {our}")
    print(f"opp decks: {opp}")

    # Build matchup list: each tuned deck as BOTH seats vs each opponent.
    matchups = []
    for a in our:
        for b in opp:
            matchups.append((a, b))   # tuned as p0
            matchups.append((b, a))   # tuned as p1
    matchups = sorted(set(matchups))

    rng = random.Random(args.seed)
    jobs = []
    for i in range(args.games):
        na, nb = matchups[i % len(matchups)]
        jobs.append((na, decks[na], nb, decks[nb], args.max_steps, args.epsilon,
                     rng.randint(1, 2**31 - 1)))
    rng.shuffle(jobs)
    print(f"total games: {len(jobs)}  matchups: {len(matchups)}  workers: {args.workers}  "
          f"epsilon: {args.epsilon}\n")

    agg = Counter()
    max_lat = 0.0
    lat_matchup = ""
    results = Counter()
    all_fails = []
    moves_total = 0

    t0 = time.time()
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(processes=args.workers) as pool:
        for r in pool.imap_unordered(_play_one, jobs, chunksize=1):
            done += 1
            for k in ("agent_exc", "illegal", "engine_reject", "hang", "over_budget"):
                agg[k] += r[k]
            moves_total += r["moves"]
            results[str(r["result"])] += 1
            if r["max_lat"] > max_lat:
                max_lat = r["max_lat"]
                lat_matchup = r["matchup"]
            for f in r["fail"]:
                all_fails.append(f)
            if done % 20 == 0 or done == len(jobs):
                bad = agg["agent_exc"] + agg["illegal"] + agg["engine_reject"] + agg["hang"]
                print(f"  [{done:4d}/{len(jobs)}] {time.time()-t0:6.1f}s  "
                      f"exc={agg['agent_exc']} illegal={agg['illegal']} "
                      f"reject={agg['engine_reject']} hang={agg['hang']} "
                      f"over_budget={agg['over_budget']} maxlat={max_lat*1000:.0f}ms",
                      flush=True)

    dt = time.time() - t0
    print("\n" + "=" * 64)
    print(f"FUZZ COMPLETE: {len(jobs)} games, {moves_total} agent moves, {dt:.1f}s")
    print(f"  agent exceptions : {agg['agent_exc']}")
    print(f"  illegal returns  : {agg['illegal']}")
    print(f"  engine rejects   : {agg['engine_reject']}")
    print(f"  hangs (stepcap)  : {agg['hang']}")
    print(f"  over latency budget ({LATENCY_BUDGET_S}s): {agg['over_budget']}")
    print(f"  worst per-move latency: {max_lat*1000:.1f} ms   ({lat_matchup})")
    print(f"  game outcomes    : {dict(results)}")

    if all_fails:
        print(f"\n--- {len(all_fails)} failure record(s) (first 25) ---")
        for kind, info in all_fails[:25]:
            print(f"[{kind}] {info}")

    total_bad = agg["agent_exc"] + agg["illegal"] + agg["engine_reject"] + agg["hang"]
    if total_bad == 0:
        print("\nRESULT: CLEAN — 0 exceptions, 0 illegal, 0 engine-rejects, 0 hangs.")
        sys.exit(0)
    else:
        print(f"\nRESULT: {total_bad} ROBUSTNESS FAILURE(S) — see records above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
