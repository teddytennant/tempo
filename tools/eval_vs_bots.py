"""Honest strength check: OUR agent vs INDEPENDENT, published competition bots.

We tune by playing our scorer against itself, which over-fits (great self-play
numbers, mediocre ladder). This harness instead measures our four tuned decks
against opponents we did NOT tune against: faithful ports of published Kaggle
notebooks living in agent/bots/ (each is a self-contained best_options + its own
decklist, none of which call our scorer):

  * crustle           — dashimaki360 Day-1 #1 Crustle wall (~1140 LB)
  * crustle_hardened  — biohack44 Day-2 hardened Crustle wall
  * baseline950       — romanrozen Mega Lucario ex baseline (~950 LB)
  * dragapult         — skarin Dragapult ex spread/aggro (proactive multi-prize)
  * ragingbolt        — yakitori55 Raging Bolt ex energy-acceleration attacker

The pool was Crustle-heavy (2 walls), which skewed conclusions toward wall-breakers;
dragapult and ragingbolt add proactive, prize-racing archetypes so the win-rates
reflect a balanced frontier field rather than just "can you crack a wall".

For each of our decks (piloted by agent/scorer.best_options, which auto-fires the
right deck specialist) we play N games per bot, alternating seats to remove the
first/second-player bias, and report win-rate vs each bot plus an aggregate.

A win-rate above ~50% here is real strength; the round-robin where we pilot both
seats only tells us which deck the scorer prefers, not whether the tuning holds up
against a foreign policy.

Run: ./scripts/run.sh -m tools.eval_vs_bots --games 24 --workers 12
"""
from __future__ import annotations

import argparse
import importlib
import multiprocessing as mp
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Our tuned decks (csv stem under data/decks) and the bots (module under agent.bots).
OUR_DECKS = ["crustle", "lucario_praxel", "starmie", "dunsparce"]
# module = bot_<name>. Crustle-heavy pool (2 walls + 1 Mega-Lucario) skewed results
# toward wall-breakers, so we add diverse, faithfully-ported frontier archetypes:
#   dragapult   — skarin Dragapult ex spread/aggro (proactive multi-prize attacker)
#   ragingbolt  — yakitori55 Raging Bolt ex energy-acceleration attacker
#   abomasnow   — kiyotah Mega Abomasnow ex control/tank (out-tanks, Riptide snipe)
#   iono        — kiyotah Iono's Bellibolt ex Lightning energy-stacking engine
# (the mossarimossari Dragapult notebook was rejected: identical scoring constants
#  to dragapult above, so it would have added no matchup diversity.)
BOTS = ["crustle", "crustle_hardened", "baseline950", "dragapult", "ragingbolt",
        "abomasnow", "iono"]


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _reset_bot_state(mod):
    """Bots carry module-global per-game state (attack plan / turn cache). Clear it
    so a worker that plays several games doesn't leak one game's plan into the next."""
    if hasattr(mod, "reset"):
        # New bots (dragapult/ragingbolt) expose an explicit reset() that clears all
        # their per-game module globals (logs / prize composition / attack plan).
        mod.reset()
    if hasattr(mod, "plan") and hasattr(mod, "AttackPlan"):
        mod.plan = mod.AttackPlan()
    if hasattr(mod, "pre_turn"):
        mod.pre_turn = 0
    if hasattr(mod, "ability_used"):
        mod.ability_used = False


def _play_one(args):
    """Play one game: OUR scorer on our_deck vs bot on bot_deck.

    our_seat is the player index (0 or 1) that OUR agent pilots; the bot pilots the
    other. Returns (our_deck_name, bot_name, outcome) where outcome is
    'W' (our agent won), 'L' (bot won), 'D' (draw/unfinished), or 'E' (engine/agent error).
    """
    our_name, our_deck, bot_name, bot_mod_name, bot_deck, our_seat, max_steps = args
    sys.path.insert(0, _ROOT)
    sys.path.insert(0, os.path.join(_ROOT, "agent"))
    from cg.api import to_observation_class
    from cg.game import battle_start, battle_finish, battle_select
    from scorer import best_options as our_best
    bot = importlib.import_module(f"agent.bots.{bot_mod_name}")
    _reset_bot_state(bot)

    if our_seat == 0:
        deck0, deck1 = our_deck, bot_deck
    else:
        deck0, deck1 = bot_deck, our_deck

    try:
        obs, _start = battle_start(deck0, deck1)
        if obs is None:
            return (our_name, bot_name, "E")
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                if res == 2:
                    return (our_name, bot_name, "D")
                return (our_name, bot_name, "W" if res == our_seat else "L")
            if oc.select is None:
                battle_finish()
                return (our_name, bot_name, "D")
            who = oc.current.yourIndex
            sel = our_best(obs) if who == our_seat else bot.best_options(obs)
            obs = battle_select(sel)
        battle_finish()
        return (our_name, bot_name, "D")  # unfinished within step budget
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return (our_name, bot_name, "E")


def _valid(name, deck):
    if len(deck) != 60:
        print(f"SKIP {name}: {len(deck)} cards (need 60)")
        return False
    sys.path.insert(0, _ROOT)
    from cg.game import battle_start, battle_finish
    try:
        obs, _ = battle_start(deck, deck)
        battle_finish()
        if obs is None:
            print(f"SKIP {name}: engine refused deck (illegal?)")
            return False
        return True
    except Exception as e:
        print(f"SKIP {name}: engine error {e!r}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decks-dir", default=os.path.join(_ROOT, "data", "decks"))
    ap.add_argument("--games", type=int, default=24, help="games per (our-deck, bot) pair (split across both seats)")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-steps", type=int, default=4000)
    ap.add_argument("--our-decks", nargs="*", default=OUR_DECKS)
    ap.add_argument("--bots", nargs="*", default=BOTS)
    args = ap.parse_args()

    # Load + validate our decks.
    our = {}
    for name in args.our_decks:
        path = os.path.join(args.decks_dir, f"{name}.csv")
        if not os.path.exists(path):
            print(f"SKIP {name}: {path} missing")
            continue
        d = _read_deck(path)
        if _valid(name, d):
            our[name] = d

    # Load bot decks (the bot module owns its decklist).
    sys.path.insert(0, _ROOT)
    bots = {}
    for name in args.bots:
        mod_name = f"bot_{name}"
        try:
            mod = importlib.import_module(f"agent.bots.{mod_name}")
            bots[name] = (mod_name, list(mod.DECK))
        except Exception as e:
            print(f"SKIP bot {name}: import error {e!r}")

    if not our or not bots:
        print("need at least one valid deck and one bot")
        return
    print(f"\nour decks ({len(our)}): {list(our)}")
    print(f"bots ({len(bots)}): {list(bots)}")

    # Build job list: N games per (our-deck, bot), seats alternated.
    jobs = []
    for dn, dd in our.items():
        for bn, (bmod, bdeck) in bots.items():
            for g in range(args.games):
                seat = g % 2  # alternate which seat our agent takes
                jobs.append((dn, dd, bn, bmod, bdeck, seat, args.max_steps))
    print(f"total games: {len(jobs)}  (workers={args.workers})\n")

    # results[(deck, bot)] = [W, L, D, E]
    res = {(dn, bn): [0, 0, 0, 0] for dn in our for bn in bots}
    idx = {"W": 0, "L": 1, "D": 2, "E": 3}

    t0 = time.time()
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(processes=args.workers) as pool:
        for (dn, bn, outcome) in pool.imap_unordered(_play_one, jobs, chunksize=1):
            res[(dn, bn)][idx[outcome]] += 1
            done += 1
            if done % 20 == 0 or done == len(jobs):
                print(f"  [{done:4d}/{len(jobs)}] {time.time()-t0:6.1f}s", flush=True)
    dt = time.time() - t0

    bot_names = list(bots)
    print("\n=== OUR-DECK win-rate vs each INDEPENDENT bot (W / decided games) ===")
    header = f"{'our deck':16s}" + "".join(f"{b[:14]:>16s}" for b in bot_names) + f"{'AGG':>10s}"
    print(header)

    def wr(rec):
        w, l, d, e = rec
        decided = w + l
        return (w / decided) if decided else 0.0, decided

    agg_rank = {}
    for dn in our:
        cells = ""
        tot_w = tot_l = 0
        for bn in bot_names:
            w, l, d, e = res[(dn, bn)]
            rate, dec = wr(res[(dn, bn)])
            tot_w += w
            tot_l += l
            cells += f"{rate:>9.0%}({w}-{l}{'/'+str(e)+'E' if e else ''})".rjust(16)
        agg = tot_w / (tot_w + tot_l) if (tot_w + tot_l) else 0.0
        agg_rank[dn] = agg
        cells += f"{agg:>9.0%}".rjust(10)
        print(f"{dn:16s}{cells}")

    print("\n=== ranked by aggregate win-rate vs independent bots ===")
    for dn in sorted(our, key=lambda n: agg_rank[n], reverse=True):
        tw = sum(res[(dn, b)][0] for b in bot_names)
        tl = sum(res[(dn, b)][1] for b in bot_names)
        td = sum(res[(dn, b)][2] for b in bot_names)
        te = sum(res[(dn, b)][3] for b in bot_names)
        print(f"  {dn:16s} {agg_rank[dn]:6.1%}   (W{tw} L{tl} D{td} E{te})")

    best = max(our, key=lambda n: agg_rank[n])
    print(f"\n=== STRONGEST vs independent opponents: {best} ({agg_rank[best]:.1%}) ===")
    print(f"time={dt:.1f}s over {len(jobs)} games ({dt/max(1,len(jobs))*1000:.0f} ms/game)")


if __name__ == "__main__":
    main()
