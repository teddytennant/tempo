"""Held-out weight optimizer for the Iono's Bellibolt ex specialist (agent/iono_rules.py).

The Iono policy's scoring weights (agent/iono_rules.WEIGHTS) are hand-tuned magic numbers. This
tool searches for a better table with a (1+1) hill-climber, then validates honestly on a HELD-OUT
set of bots it never optimized against — the only test that distinguishes real generalization from
over-fitting.

  OPTIMIZE set (search signal): crustle, baseline950, dragapult, abomasnow
  HELD-OUT set (validation)   : crustle_hardened, ragingbolt, iono   (mirror match)

Each candidate sets iono_rules.WEIGHTS, pilots the Iono deck (data/decks/iono.csv) with our own
scorer.best_options against the optimize bots over many games (both seats), and is scored by mean
win-rate. We keep improving candidates; on a tentative improvement we CONFIRM with a fresh batch
(the engine RNG isn't seedable, so a single batch is noisy). Finally we re-measure default vs best
on BOTH sets with a large game budget and print the before/after table + a generalization verdict.

Run: ./scripts/run.sh -m tools.optimize_iono --budget 60 --opt-games 40 --final-games 120
"""
from __future__ import annotations

import argparse
import importlib
import math
import multiprocessing as mp
import os
import random
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OPTIMIZE_BOTS = ["crustle", "baseline950", "dragapult", "abomasnow"]
HELDOUT_BOTS = ["crustle_hardened", "ragingbolt", "iono"]

# Per-weight search spec: kind + bounds. "mult" = multiplicative log-normal step (continuous score
# weights). "int_step" = small integer threshold nudged by +/-1. "int_mult" = integer damage model
# scaled multiplicatively then rounded. Bounds clamp to keep candidates sane.
WEIGHT_SPEC = {
    "voltorb_load_active":      ("mult", 200.0, 50000.0),
    "voltorb_overload_active":  ("mult", 50.0, 50000.0),
    "voltorb_bench_setup":      ("mult", 50.0, 50000.0),
    "bellibolt_load_active":    ("mult", 50.0, 50000.0),
    "bellibolt_overload_active":("mult", 20.0, 50000.0),
    "wattrel_first_energy":     ("mult", 200.0, 50000.0),
    "kilowattrel_first_energy": ("mult", 200.0, 50000.0),
    "voltorb_ready_energy":     ("int_step", 1, 3),
    "bellibolt_full_energy":    ("int_step", 3, 6),
    "voltaic_base_dmg":         ("int_mult", 5, 80),
    "voltaic_per_energy":       ("int_mult", 5, 60),
    "search_voltorb":           ("mult", 10.0, 5000.0),
    "search_tadbulb":           ("mult", 10.0, 5000.0),
    "search_bellibolt":         ("mult", 10.0, 5000.0),
    "search_wattrel":           ("mult", 10.0, 5000.0),
    "search_kilowattrel":       ("mult", 10.0, 5000.0),
}


# ── one game in a worker (weights passed in, applied to iono_rules.WEIGHTS) ────────────────────────
def _play_one(args):
    weights, bot_name, seat, max_steps = args
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "agent"))
    from cg.api import to_observation_class
    from cg.game import battle_start, battle_finish, battle_select
    import iono_rules
    from scorer import best_options as our_best

    iono_rules.WEIGHTS.update(weights)  # functions read this dict at call time

    bot = importlib.import_module(f"agent.bots.bot_{bot_name}")
    if hasattr(bot, "reset"):
        bot.reset()
    if hasattr(bot, "plan") and hasattr(bot, "AttackPlan"):
        bot.plan = bot.AttackPlan()
    if hasattr(bot, "pre_turn"):
        bot.pre_turn = 0
    if hasattr(bot, "ability_used"):
        bot.ability_used = False
    bot_deck = list(bot.DECK)

    if seat == 0:
        deck0, deck1 = _OUR_DECK, bot_deck
    else:
        deck0, deck1 = bot_deck, _OUR_DECK
    try:
        obs, _ = battle_start(deck0, deck1)
        if obs is None:
            return "E"
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                if res == 2:
                    return "D"
                return "W" if res == seat else "L"
            if oc.select is None:
                battle_finish()
                return "D"
            who = oc.current.yourIndex
            sel = our_best(obs) if who == seat else bot.best_options(obs)
            obs = battle_select(sel)
        battle_finish()
        return "D"
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return "E"


_OUR_DECK = None  # set in worker initializer


def _winit(deck):
    global _OUR_DECK
    _OUR_DECK = deck


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


# ── evaluation: win-rate of a weight table vs a set of bots ────────────────────────────────────────
def evaluate(pool, weights, bots, games_per_bot, max_steps, per_bot=False):
    jobs = []
    for bn in bots:
        for g in range(games_per_bot):
            jobs.append((weights, bn, g % 2, max_steps))
    rec = {bn: [0, 0, 0, 0] for bn in bots}  # W L D E
    idx = {"W": 0, "L": 1, "D": 2, "E": 3}
    job_bot = [j[1] for j in jobs]
    for i, outcome in enumerate(pool.imap(_play_one, jobs, chunksize=2)):
        rec[job_bot[i]][idx[outcome]] += 1
    tot_w = sum(r[0] for r in rec.values())
    tot_l = sum(r[1] for r in rec.values())
    wr = tot_w / (tot_w + tot_l) if (tot_w + tot_l) else 0.0
    if per_bot:
        pb = {}
        for bn in bots:
            w, l, d, e = rec[bn]
            pb[bn] = (w / (w + l)) if (w + l) else 0.0
        return wr, pb
    return wr


# ── perturbation ──────────────────────────────────────────────────────────────────────────────────
def perturb(weights, rng, n_coords, sigma):
    cand = dict(weights)
    keys = rng.sample(list(WEIGHT_SPEC), k=min(n_coords, len(WEIGHT_SPEC)))
    for k in keys:
        kind, lo, hi = WEIGHT_SPEC[k]
        v = cand[k]
        if kind == "mult":
            v = v * math.exp(rng.gauss(0.0, sigma))
            cand[k] = float(min(max(v, lo), hi))
        elif kind == "int_mult":
            v = int(round(v * math.exp(rng.gauss(0.0, sigma))))
            cand[k] = int(min(max(v, lo), hi))
        elif kind == "int_step":
            v = int(v) + rng.choice([-1, 1])
            cand[k] = int(min(max(v, lo), hi))
    return cand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=60, help="candidate evaluations")
    ap.add_argument("--opt-games", type=int, default=40, help="games per optimize-bot per eval")
    ap.add_argument("--final-games", type=int, default=120, help="games per bot in final report")
    ap.add_argument("--workers", type=int, default=min(16, mp.cpu_count()))
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--sigma", type=float, default=0.5)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "agent"))
    import iono_rules
    defaults = dict(iono_rules.WEIGHTS)
    our_deck = _read_deck(os.path.join(_ROOT, "data", "decks", "iono.csv"))

    ctx = mp.get_context("spawn")
    pool = ctx.Pool(processes=args.workers, initializer=_winit, initargs=(our_deck,))
    t0 = time.time()
    try:
        print(f"optimize bots: {OPTIMIZE_BOTS}")
        print(f"held-out bots: {HELDOUT_BOTS}")
        print(f"workers={args.workers} opt-games/bot={args.opt_games} budget={args.budget}\n")

        # Baseline on the optimize set (noisy single batch used for the climb).
        incumbent = dict(defaults)
        inc_score = evaluate(pool, incumbent, OPTIMIZE_BOTS, args.opt_games, args.max_steps)
        print(f"[init] default opt-set win-rate = {inc_score:.3f}")
        best = dict(defaults)
        best_score = inc_score
        accepts = 0

        for it in range(1, args.budget + 1):
            n_coords = rng.choice([1, 1, 2, 3])
            cand = perturb(incumbent, rng, n_coords, args.sigma)
            cand_score = evaluate(pool, cand, OPTIMIZE_BOTS, args.opt_games, args.max_steps)
            tag = ""
            if cand_score > inc_score:
                # Confirm with a fresh batch for BOTH (fight RNG noise) before accepting.
                c2 = evaluate(pool, cand, OPTIMIZE_BOTS, args.opt_games, args.max_steps)
                i2 = evaluate(pool, incumbent, OPTIMIZE_BOTS, args.opt_games, args.max_steps)
                cand_avg = 0.5 * (cand_score + c2)
                inc_avg = 0.5 * (inc_score + i2)
                if cand_avg > inc_avg:
                    incumbent = cand
                    inc_score = cand_avg
                    accepts += 1
                    tag = f"  ACCEPT (cand {cand_avg:.3f} > inc {inc_avg:.3f})"
                    if cand_avg > best_score:
                        best, best_score = dict(cand), cand_avg
                else:
                    inc_score = inc_avg  # refresh incumbent's noisy estimate
                    tag = f"  reject-after-confirm ({cand_avg:.3f} vs {inc_avg:.3f})"
            print(f"[{it:3d}/{args.budget}] cand={cand_score:.3f} inc={inc_score:.3f}"
                  f" best={best_score:.3f}{tag}  ({time.time()-t0:5.0f}s)", flush=True)

        print(f"\nsearch done: {accepts} accepts in {args.budget} evals, {time.time()-t0:.0f}s")

        # ── honest final report: large-budget re-measure on BOTH sets ──
        fg = args.final_games
        print(f"\n=== FINAL ({fg} games/bot) ===")
        d_opt, d_opt_pb = evaluate(pool, defaults, OPTIMIZE_BOTS, fg, args.max_steps, per_bot=True)
        d_hld, d_hld_pb = evaluate(pool, defaults, HELDOUT_BOTS, fg, args.max_steps, per_bot=True)
        b_opt, b_opt_pb = evaluate(pool, best, OPTIMIZE_BOTS, fg, args.max_steps, per_bot=True)
        b_hld, b_hld_pb = evaluate(pool, best, HELDOUT_BOTS, fg, args.max_steps, per_bot=True)
    finally:
        pool.close()
        pool.join()

    def row(label, agg, pb, bots):
        cells = "  ".join(f"{bn[:10]}={pb[bn]:.0%}" for bn in bots)
        return f"  {label:9s} AGG={agg:.1%}   {cells}"

    print("\n-- OPTIMIZE set --")
    print(row("default", d_opt, d_opt_pb, OPTIMIZE_BOTS))
    print(row("best", b_opt, b_opt_pb, OPTIMIZE_BOTS))
    print("\n-- HELD-OUT set --")
    print(row("default", d_hld, d_hld_pb, HELDOUT_BOTS))
    print(row("best", b_hld, b_hld_pb, HELDOUT_BOTS))

    print("\n=== VERDICT ===")
    print(f"optimize-set: default {d_opt:.1%} -> best {b_opt:.1%}  ({b_opt-d_opt:+.1%})")
    print(f"held-out-set: default {d_hld:.1%} -> best {b_hld:.1%}  ({b_hld-d_hld:+.1%})")
    if b_hld > d_hld:
        print("GENERALIZES: optimized weights improve the HELD-OUT set. Keep them.")
    else:
        print("OVER-FITS: optimized weights do NOT improve held-out. Revert to defaults.")

    print("\n=== BEST WEIGHTS ===")
    for k in WEIGHT_SPEC:
        dv, bv = defaults[k], best[k]
        mark = "" if dv == bv else "   <-- changed"
        print(f"    {k!r}: {bv},{mark}")


if __name__ == "__main__":
    main()
