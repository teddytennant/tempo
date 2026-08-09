"""Robustness probe for a *packed* agent tree (the deploy path, not the repo tree).

Point it at any directory containing `agent/` + `search/` (i.e. an extracted submission, or a
reconstructed candidate) and it plays many full real-engine games, driving BOTH seats through the
deploy entry point and asserting on every single decision:

  * the agent did not raise,
  * the returned selection is LEGAL (distinct ints in range, length in [minCount, maxCount]),
  * the engine actually accepted it,
  * per-move latency, and — the one that actually kills submissions — CUMULATIVE agent
    wall-clock per game against the 600s game clock.

Unlike tools/fuzz.py this takes `--src`, so two candidate builds can be compared on identical
seeds. An epsilon fraction of moves are perturbed to a random *legal* selection to push the agent
into states a clean game never reaches; the agent is still called and checked on EVERY step.

  ./scripts/run.sh -m tools.robust_probe --src experiments/proven_src --games 200 --workers 10
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

# Kaggle's per-episode clock. An agent that burns this loses on time regardless of play quality.
GAME_CLOCK_S = 600.0
LATENCY_BUDGET_S = 1.0


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _legal(sel, sel_dict):
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
            return False, f"index {i} out of range(0,{n})"
    if not (minc <= len(sel) <= maxc):
        return False, f"len {len(sel)} not in [{minc},{maxc}] (n={n})"
    return True, ""


def _random_legal(sel_dict, rng):
    n = len(sel_dict.get("option") or [])
    minc = max(0, min(sel_dict.get("minCount", 0) or 0, n))
    maxc = max(minc, min(sel_dict.get("maxCount", 0) or 0, n))
    if n == 0 or maxc == 0:
        return []
    k = rng.randint(minc, maxc) if maxc >= minc else minc
    if minc == 0 and maxc >= 1 and rng.random() < 0.8:
        k = max(1, k)
    return rng.sample(range(n), min(k, n))


def _play_one(task):
    src, name_a, deck_a, name_b, deck_b, max_steps, epsilon, seed = task
    # The candidate tree must win the import race against the repo's own agent/ package.
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    rng = random.Random(seed)

    res = {
        "matchup": f"{name_a} vs {name_b}", "steps": 0, "moves": 0,
        "agent_exc": 0, "illegal": 0, "engine_reject": 0, "hang": 0,
        "max_lat": 0.0, "over_budget": 0, "agent_time": 0.0, "clock_blown": 0,
        "result": None, "fail": [], "lats": [],
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
                "n": len(sel_dict.get("option") or []), "sel": sel, "detail": str(detail)[:700],
            }))

    try:
        obs, _ = battle_start(deck_a, deck_b)
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

            res["moves"] += 1
            t0 = time.monotonic()
            try:
                pick = M.agent(obs)
            except Exception:
                res["agent_exc"] += 1
                record("agent_exc", sel_dict, traceback.format_exc()[-800:])
                pick = None
            lat = time.monotonic() - t0
            res["agent_time"] += lat
            res["lats"].append(lat)
            res["max_lat"] = max(res["max_lat"], lat)
            if lat > LATENCY_BUDGET_S:
                res["over_budget"] += 1
                record("latency", sel_dict, f"{lat:.3f}s single move")

            ok = False
            if pick is not None:
                ok, why = _legal(pick, sel_dict)
                if not ok:
                    res["illegal"] += 1
                    record("illegal", sel_dict, why, sel=pick)

            play_random = rng.random() < epsilon or not ok or pick is None
            to_play = _random_legal(sel_dict, rng) if play_random else pick

            try:
                obs = battle_select(to_play)
            except Exception:
                # Only a rejection of the AGENT's own legality-passing pick is a real deploy bug;
                # random perturbations can be semantically illegal by construction.
                if not play_random:
                    res["engine_reject"] += 1
                    record("engine_reject", sel_dict, traceback.format_exc()[-400:], sel=to_play)
                recovered = False
                cands = ([pick] if (ok and pick is not None) else [])
                cands += [_random_legal(sel_dict, rng) for _ in range(4)]
                for cand in cands:
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
        res["hang"] = 1
        res["result"] = "hang"
        record("hang", {"option": []}, f"exceeded {max_steps} steps")
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
    finally:
        # Both seats share one game clock in our accounting; flag anything near Kaggle's limit.
        if res["agent_time"] > GAME_CLOCK_S:
            res["clock_blown"] = 1


def main():
    import multiprocessing as mp

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir containing agent/ and search/")
    ap.add_argument("--label", default="")
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--epsilon", type=float, default=0.12)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "decks"))
    ap.add_argument("--opps", default="crustle,dragapult,starmie,dunsparce,fezandipiti,abomasnow,"
                                      "iono,mega_lucario,lucario_praxel,hops_snorlax,sample")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    own = _read_deck(os.path.join(src, "agent", "deck.csv"))
    assert len(own) == 60, f"{src}/agent/deck.csv has {len(own)} cards"
    label = args.label or os.path.basename(src)

    opps = {}
    for name in args.opps.split(","):
        name = name.strip()
        p = os.path.join(args.decks_dir, f"{name}.csv")
        if os.path.exists(p):
            d = _read_deck(p)
            if len(d) == 60:
                opps[name] = d
    assert opps, "no opponent decks found"

    # Our deck in BOTH seats against every opponent, plus the true mirror (= Kaggle validation).
    matchups = [("self", own, "self", own)]
    for n, d in sorted(opps.items()):
        matchups.append(("self", own, n, d))
        matchups.append((n, d, "self", own))

    rng = random.Random(args.seed)
    jobs = []
    for i in range(args.games):
        na, da, nb, db = matchups[i % len(matchups)]
        jobs.append((src, na, da, nb, db, args.max_steps, args.epsilon,
                     rng.randint(1, 2**31 - 1)))
    rng.shuffle(jobs)
    print(f"[{label}] src={src}  games={len(jobs)}  matchups={len(matchups)}  "
          f"eps={args.epsilon}  workers={args.workers}", flush=True)

    agg = Counter()
    results = Counter()
    all_fails = []
    moves_total = 0
    all_lats = []
    worst_game_time = 0.0
    worst_game = ""
    max_lat = 0.0

    t0 = time.time()
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(processes=args.workers) as pool:
        for r in pool.imap_unordered(_play_one, jobs, chunksize=1):
            done += 1
            for k in ("agent_exc", "illegal", "engine_reject", "hang", "over_budget",
                      "clock_blown"):
                agg[k] += r[k]
            moves_total += r["moves"]
            results[str(r["result"])] += 1
            all_lats.extend(r["lats"])
            max_lat = max(max_lat, r["max_lat"])
            if r["agent_time"] > worst_game_time:
                worst_game_time = r["agent_time"]
                worst_game = r["matchup"]
            all_fails.extend(r["fail"])
            if done % 25 == 0 or done == len(jobs):
                print(f"  [{done:4d}/{len(jobs)}] {time.time()-t0:6.1f}s  "
                      f"exc={agg['agent_exc']} illegal={agg['illegal']} "
                      f"reject={agg['engine_reject']} hang={agg['hang']} "
                      f"maxlat={max_lat*1000:.0f}ms worstgame={worst_game_time:.1f}s", flush=True)

    all_lats.sort()

    def q(p):
        return all_lats[min(len(all_lats) - 1, int(len(all_lats) * p))] if all_lats else 0.0

    print("\n" + "=" * 68)
    print(f"ROBUSTNESS [{label}]: {len(jobs)} games, {moves_total} agent decisions, "
          f"{time.time()-t0:.1f}s")
    print(f"  agent exceptions        : {agg['agent_exc']}")
    print(f"  illegal selections      : {agg['illegal']}")
    print(f"  engine rejects (agent)  : {agg['engine_reject']}")
    print(f"  hangs (step cap)        : {agg['hang']}")
    print(f"  moves over {LATENCY_BUDGET_S}s        : {agg['over_budget']}")
    print(f"  games over {GAME_CLOCK_S:.0f}s clock  : {agg['clock_blown']}")
    print(f"  latency p50/p99/max     : {q(.50)*1000:.2f} / {q(.99)*1000:.2f} / "
          f"{max_lat*1000:.1f} ms")
    print(f"  worst cumulative game   : {worst_game_time:.1f}s  ({worst_game})")
    print(f"  outcomes                : {dict(results)}")

    if all_fails:
        print(f"\n--- {len(all_fails)} failure record(s) (first 20) ---")
        for kind, info in all_fails[:20]:
            print(f"[{kind}] {info}")

    bad = agg["agent_exc"] + agg["illegal"] + agg["engine_reject"] + agg["hang"] + agg["clock_blown"]
    print("\nRESULT: " + ("CLEAN" if bad == 0 else f"{bad} ROBUSTNESS FAILURE(S)"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
