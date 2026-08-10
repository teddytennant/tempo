"""Context-coverage probe + adversarial observation fuzzer for the deploy agent.

`tools/robust_probe.py` proves the agent survives every state a *real game* reaches. That is a
sampling argument, and it has a blind spot: the engine defines **49 `SelectContext` values** and a
normal game only ever asks a fraction of them. Any context the probe never reaches is code that has
never been executed on the deploy path — and on the ladder it only takes one to error out a game.

This tool closes that gap in two phases:

  1. **Capture / coverage.** Play real games through the deploy entry point and record which
     contexts actually occur, keeping a few real observation dicts per context.

  2. **Adversarial mutation.** Take every captured observation and rewrite it into states the
     engine could legally hand us but our games never produced: the same board asked under each of
     the 49 contexts, degenerate `minCount`/`maxCount` combinations, empty and truncated option
     lists, missing optional keys, and stripped sub-structures. Every mutant is fed to
     `agent.main.agent()` and checked for (a) no exception and (b) a selection that is legal for
     the mutant's own stated bounds.

A mutant board is not necessarily a board the engine would produce, so a *bad choice* here means
nothing. The only thing asserted is what a submission is actually killed by: raising, or returning
something the harness cannot use.

  ./scripts/run.sh -m tools.ctx_fuzz --src experiments/luc_majkel_v3_src --games 60
"""
from __future__ import annotations

import argparse
import copy
import os
import random
import sys
import time
import traceback
from collections import Counter, defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LATENCY_BUDGET_S = 1.0


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _legal(sel, sel_dict):
    """Legality against the selection dict's OWN stated bounds."""
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
    if minc > n or minc > maxc:
        return True, ""          # unsatisfiable by construction — only no-raise is required
    if not (minc <= len(sel) <= maxc):
        return False, f"len {len(sel)} not in [{minc},{maxc}] (n={n})"
    return True, ""


def _random_legal(sel_dict, rng):
    n = len(sel_dict.get("option") or [])
    minc = max(0, min(sel_dict.get("minCount", 0) or 0, n))
    maxc = max(minc, min(sel_dict.get("maxCount", 0) or 0, n))
    if n == 0 or maxc == 0:
        return []
    k = rng.randint(minc, maxc)
    if minc == 0 and maxc >= 1 and rng.random() < 0.8:
        k = max(1, k)
    return rng.sample(range(n), min(k, n))


def _mutants(obs, all_ctx, rng):
    """Yield (tag, mutated_obs). The board is real; only the *question* is rewritten."""
    sel = obs.get("select") or {}
    n = len(sel.get("option") or [])

    # (a) same board, every context the engine defines.
    for c in all_ctx:
        if c == sel.get("context"):
            continue
        m = copy.deepcopy(obs)
        m["select"]["context"] = c
        yield f"ctx={c}", m

    # (b) degenerate count bounds. These are the shapes that break naive index math.
    for minc, maxc in ((0, 0), (0, n), (0, 1), (1, 1), (n, n), (max(1, n), max(1, n)),
                       (n + 1, n + 1), (0, n + 3), (2, 1)):
        m = copy.deepcopy(obs)
        m["select"]["minCount"] = minc
        m["select"]["maxCount"] = maxc
        yield f"bounds={minc},{maxc}", m

    # (c) empty / single / truncated option lists.
    for k in (0, 1, max(0, n // 2)):
        if k == n:
            continue
        m = copy.deepcopy(obs)
        m["select"]["option"] = (sel.get("option") or [])[:k]
        m["select"]["minCount"] = min(sel.get("minCount", 0) or 0, k)
        m["select"]["maxCount"] = min(sel.get("maxCount", 0) or 0, k)
        yield f"options={k}", m

    # (d) optional keys absent or null — the engine sends these as None routinely, and a
    #     specialist that assumes one is populated dies the first time it is not.
    for key in ("deck", "contextCard", "effect", "remainDamageCounter", "remainEnergyCost"):
        if key not in sel:
            continue
        for val in (None, "__DROP__"):
            m = copy.deepcopy(obs)
            if val == "__DROP__":
                m["select"].pop(key, None)
            else:
                m["select"][key] = None
            yield f"sel.{key}={'drop' if val == '__DROP__' else 'None'}", m

    # (e) stripped board sub-structures: empty bench/hand/discard/prize, no stadium, no active.
    cur = obs.get("current") or {}
    players = cur.get("players") or []
    you = cur.get("yourIndex", 0)
    for pi in range(len(players)):
        for area in ("bench", "hand", "discard", "active", "prize", "energyZone"):
            if area not in (players[pi] or {}):
                continue
            m = copy.deepcopy(obs)
            m["current"]["players"][pi][area] = []
            who = "me" if pi == you else "opp"
            yield f"{who}.{area}=[]", m
    if "stadium" in cur:
        m = copy.deepcopy(obs)
        m["current"]["stadium"] = []
        yield "stadium=[]", m

    # (f) turn / result oddities: turn 0, a huge turn number, a decided game still asking.
    for field, val in (("turn", 0), ("turn", 9999), ("turnActionCount", 0), ("result", 0)):
        if field not in cur:
            continue
        m = copy.deepcopy(obs)
        m["current"][field] = val
        yield f"current.{field}={val}", m

    # (g) one random option-record field blanked — options arrive partially populated.
    opts = sel.get("option") or []
    if opts:
        i = rng.randrange(len(opts))
        for key in list(opts[i].keys())[:6]:
            if key == "type":
                continue
            m = copy.deepcopy(obs)
            m["select"]["option"][i][key] = None
            yield f"option[{i}].{key}=None", m


def _run_one(task):
    src, deck_a, deck_b, name_b, max_steps, epsilon, per_ctx, seed, do_mutate = task
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    rng = random.Random(seed)

    res = {
        "ctx": Counter(), "moves": 0, "mutants": 0, "mut_exc": 0, "mut_illegal": 0,
        "mut_slow": 0, "fail": [], "opp": name_b, "max_lat": 0.0,
    }

    try:
        from cg.game import battle_start, battle_finish, battle_select
        from cg.api import to_observation_class, SelectContext
        import agent.main as M
    except Exception:
        res["fail"].append(("import", traceback.format_exc()[-800:]))
        return res

    all_ctx = sorted({int(getattr(SelectContext, n)) for n in dir(SelectContext)
                      if not n.startswith("_")
                      and isinstance(getattr(SelectContext, n), SelectContext)})

    def record(kind, tag, ctx, detail, sel=None):
        if len(res["fail"]) < 40:
            res["fail"].append((kind, {"opp": name_b, "tag": tag, "base_ctx": ctx,
                                       "sel": sel, "detail": str(detail)[:600]}))

    captured = defaultdict(list)
    try:
        obs, _ = battle_start(deck_a, deck_b)
        if obs is None:
            return res
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            r = oc.current.result if oc.current is not None else -1
            if r is not None and r >= 0:
                break
            sel_dict = obs.get("select")
            if sel_dict is None:
                break
            c = sel_dict.get("context")
            res["ctx"][c] += 1
            res["moves"] += 1
            if len(captured[c]) < per_ctx:
                captured[c].append(copy.deepcopy(obs))
            try:
                pick = M.agent(obs)
            except Exception:
                record("live_exc", "-", c, traceback.format_exc()[-600:])
                pick = None
            ok = pick is not None and _legal(pick, sel_dict)[0]
            to_play = pick if (ok and rng.random() >= epsilon) else _random_legal(sel_dict, rng)
            try:
                obs = battle_select(to_play)
            except Exception:
                done = False
                for cand in [_random_legal(sel_dict, rng) for _ in range(4)]:
                    try:
                        obs = battle_select(cand)
                        done = True
                        break
                    except Exception:
                        continue
                if not done:
                    break
        try:
            battle_finish()
        except Exception:
            pass
    except Exception:
        res["fail"].append(("loop", traceback.format_exc()[-800:]))
        try:
            battle_finish()
        except Exception:
            pass

    if not do_mutate:
        return res

    # Phase 2 — the engine is idle now; hammer the policy on rewritten observations.
    for c, obs_list in captured.items():
        for base in obs_list:
            for tag, m in _mutants(base, all_ctx, rng):
                res["mutants"] += 1
                t0 = time.monotonic()
                try:
                    pick = M.agent(m)
                except Exception:
                    res["mut_exc"] += 1
                    record("mut_exc", tag, c, traceback.format_exc()[-600:])
                    continue
                lat = time.monotonic() - t0
                res["max_lat"] = max(res["max_lat"], lat)
                if lat > LATENCY_BUDGET_S:
                    res["mut_slow"] += 1
                    record("mut_slow", tag, c, f"{lat:.3f}s")
                good, why = _legal(pick, m.get("select") or {})
                if not good:
                    res["mut_illegal"] += 1
                    record("mut_illegal", tag, c, why, sel=pick)
    return res


def main():
    import multiprocessing as mp

    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir containing agent/ and search/")
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--epsilon", type=float, default=0.20)
    ap.add_argument("--per-ctx", type=int, default=2, help="observations captured per context/game")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "meta_aug", "decks"))
    ap.add_argument("--opps", default="", help="comma list; default = every deck in --decks-dir")
    ap.add_argument("--no-mutate", action="store_true", help="coverage only, no fuzzing")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    own = _read_deck(os.path.join(src, "agent", "deck.csv"))
    assert len(own) == 60, f"{src}/agent/deck.csv has {len(own)} cards"

    names = ([s.strip() for s in args.opps.split(",") if s.strip()]
             or sorted(f[:-4] for f in os.listdir(args.decks_dir) if f.endswith(".csv")))
    opps = {}
    for name in names:
        p = os.path.join(args.decks_dir, f"{name}.csv")
        if os.path.exists(p):
            d = _read_deck(p)
            if len(d) == 60:
                opps[name] = d
    assert opps, f"no opponent decks in {args.decks_dir}"

    matchups = [("self", own)] + sorted(opps.items())
    rng = random.Random(args.seed)
    jobs = []
    for i in range(args.games):
        nb, db = matchups[i % len(matchups)]
        jobs.append((src, own, db, nb, args.max_steps, args.epsilon, args.per_ctx,
                     rng.randint(1, 2**31 - 1), not args.no_mutate))
    rng.shuffle(jobs)

    print(f"[ctx_fuzz] src={src}  games={len(jobs)}  opponents={len(opps)}  "
          f"per_ctx={args.per_ctx}  mutate={not args.no_mutate}", flush=True)

    ctx_total = Counter()
    agg = Counter()
    fails = []
    max_lat = 0.0
    t0 = time.time()
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(processes=args.workers) as pool:
        for r in pool.imap_unordered(_run_one, jobs, chunksize=1):
            done += 1
            ctx_total.update(r["ctx"])
            for k in ("moves", "mutants", "mut_exc", "mut_illegal", "mut_slow"):
                agg[k] += r[k]
            max_lat = max(max_lat, r["max_lat"])
            fails.extend(r["fail"])
            if done % 10 == 0 or done == len(jobs):
                print(f"  [{done:4d}/{len(jobs)}] {time.time()-t0:6.1f}s  "
                      f"contexts={len(ctx_total)} mutants={agg['mutants']} "
                      f"exc={agg['mut_exc']} illegal={agg['mut_illegal']}", flush=True)

    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    from cg.api import SelectContext
    names_by_val = {int(getattr(SelectContext, n)): n for n in dir(SelectContext)
                    if not n.startswith("_") and isinstance(getattr(SelectContext, n), SelectContext)}

    print("\n" + "=" * 70)
    print(f"CONTEXT COVERAGE — {agg['moves']} live decisions over {len(jobs)} games")
    seen = sorted(ctx_total.items(), key=lambda kv: -kv[1])
    for c, k in seen:
        print(f"  {c:>3} {names_by_val.get(c,'?'):<32} {k:>8}  {100.0*k/max(1,agg['moves']):5.2f}%")
    missing = [c for c in sorted(names_by_val) if c not in ctx_total]
    print(f"\n  reached {len(seen)}/{len(names_by_val)} contexts; "
          f"NEVER REACHED ({len(missing)}): "
          + ", ".join(f"{c}:{names_by_val[c]}" for c in missing))

    print("\n" + "=" * 70)
    print(f"ADVERSARIAL MUTATION — {agg['mutants']} mutated observations")
    print(f"  agent exceptions   : {agg['mut_exc']}")
    print(f"  illegal selections : {agg['mut_illegal']}")
    print(f"  moves over {LATENCY_BUDGET_S}s   : {agg['mut_slow']}   (max {max_lat*1000:.0f} ms)")

    if fails:
        by_tag = Counter()
        by_kind = Counter()
        for kind, info in fails:
            by_kind[kind] += 1
            by_tag[(kind, info.get("tag"))] += 1
        print(f"\n--- {len(fails)} failure record(s); by kind {dict(by_kind)} ---")
        for (kind, tag), k in by_tag.most_common(25):
            print(f"  {kind:<12} {str(tag):<28} x{k}")
        print("\n--- first 8 in full ---")
        for kind, info in fails[:8]:
            print(f"[{kind}] {info}")

    bad = agg["mut_exc"] + agg["mut_illegal"] + sum(1 for k, _ in fails if k in ("import", "loop",
                                                                                "live_exc"))
    print("\nRESULT: " + ("CLEAN" if bad == 0 else f"{bad} FAILURE(S)"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
