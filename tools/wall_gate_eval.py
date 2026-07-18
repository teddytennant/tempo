"""Crustle-wall gate eval: OUR pilot (an arbitrary flat agent dir) vs a fixed opponent.

Built for the "golden base vs candidate" regression gates of the wall agent: the pilot under
test is a FLAT agent dir (e.g. the extracted proven submission tarball, or that tarball plus a
surgical fix), NOT the live repo agent/ — so the measured artifact is byte-identical to what
ships. Isolation follows tools/selfplay_ab.py: the pilot runs in its own subprocess
(tools/pilot_server.py) with a private sys.path, because two agent codebases defining the same
top-level modules (scorer, crustle_rules, ...) cannot share one Python process.

Opponents:
  bot:<name>      agent/bots/bot_<name>.py (self-contained published bots; own DECK, no scorer)
  pilot:<dir>     a second pilot_server on <dir> (e.g. the live repo agent/ so its specialist
                  rules pilot the opponent deck) -- requires --opp-deck

Seats alternate every game (our deck AND our agent move together, player order alternates),
the matchup_eval discipline that avoids the anomaly_eval seat artifact.

Run (engine needs libstdc++ on the loader path -> use scripts/run.sh):
  ./scripts/run.sh -m tools.wall_gate_eval --our-agent /path/to/flat_agent_dir \
      --our-deck data/decks/crustle.csv --opp bot:crustle --games 40 --workers 10
  ./scripts/run.sh -m tools.wall_gate_eval --our-agent /path/to/flat_agent_dir \
      --our-deck data/decks/crustle.csv --opp pilot:agent --opp-deck data/decks/dunsparce.csv
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ENGINE = None
_OUR = None            # our pilot Popen
_OPP = None            # opponent: Popen (pilot) or module (bot)
_OPP_IS_BOT = False
_DECKS = None          # (our_deck, opp_deck)


def _read_deck(path):
    with open(path) as f:
        return [int(x) for x in f.read().splitlines() if x.strip()][:60]


def _spawn_pilot(agent_dir, engine_root):
    cmd = [sys.executable, os.path.join(_ROOT, "tools", "pilot_server.py"),
           "--agent", agent_dir, "--engine-root", engine_root]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, bufsize=1, env=os.environ.copy())
    line = p.stdout.readline().strip()
    if line != "READY":
        raise RuntimeError(f"pilot {agent_dir} failed to start: {line!r}")
    return p


def _ask(pilot, obs):
    pilot.stdin.write(json.dumps(obs) + "\n")
    pilot.stdin.flush()
    line = pilot.stdout.readline()
    if not line:
        raise RuntimeError("pilot died")
    return json.loads(line)


def _reset_bot_state(mod):
    """Published bots carry module-global per-game state; clear it between games."""
    if hasattr(mod, "reset"):
        mod.reset()
    if hasattr(mod, "plan") and hasattr(mod, "AttackPlan"):
        mod.plan = mod.AttackPlan()
    if hasattr(mod, "pre_turn"):
        mod.pre_turn = 0
    if hasattr(mod, "ability_used"):
        mod.ability_used = False


def _init(our_agent, opp_spec, engine_root, decks):
    global _ENGINE, _OUR, _OPP, _OPP_IS_BOT, _DECKS
    sys.path.insert(0, engine_root)
    from cg.api import to_observation_class
    from cg.game import battle_start, battle_finish, battle_select
    _ENGINE = (battle_start, battle_finish, battle_select, to_observation_class)
    _DECKS = decks
    _OUR = _spawn_pilot(our_agent, engine_root)
    if opp_spec.startswith("bot:"):
        _OPP = importlib.import_module(f"agent.bots.bot_{opp_spec[4:]}")
        _OPP_IS_BOT = True
    else:
        _OPP = _spawn_pilot(opp_spec[len("pilot:"):], engine_root)
        _OPP_IS_BOT = False

    import atexit

    def _cleanup():
        for p in ([_OUR] + ([] if _OPP_IS_BOT else [_OPP])):
            try:
                p.stdin.close()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
    atexit.register(_cleanup)


def _play_one(args):
    """One game; our agent+deck on seat `our_seat`. 'W'/'L'/'D' (draw/unfinished), 'E' (error)."""
    our_seat, max_steps = args
    battle_start, battle_finish, battle_select, to_observation_class = _ENGINE
    our_deck, opp_deck = _DECKS
    if _OPP_IS_BOT:
        _reset_bot_state(_OPP)
    decks = [our_deck, opp_deck] if our_seat == 0 else [opp_deck, our_deck]
    try:
        obs, _start = battle_start(decks[0], decks[1])
        if obs is None:
            return "E"
        for _ in range(max_steps):
            oc = to_observation_class(obs)
            res = oc.current.result if oc.current is not None else -1
            if res is not None and res >= 0:
                battle_finish()
                if res == 2:
                    return "D"
                return "W" if res == our_seat else "L"
            if oc.select is None:
                battle_finish()
                return "D"
            who = oc.current.yourIndex
            if who == our_seat:
                sel = _ask(_OUR, obs)
            elif _OPP_IS_BOT:
                sel = _OPP.best_options(obs)
            else:
                sel = _ask(_OPP, obs)
            obs = battle_select(sel)
        battle_finish()
        return "D"
    except Exception:
        try:
            battle_finish()
        except Exception:
            pass
        return "E"


def _wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = w / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--our-agent", required=True, help="FLAT agent dir for the pilot under test")
    ap.add_argument("--our-deck", default=os.path.join(_ROOT, "data", "decks", "crustle.csv"))
    ap.add_argument("--opp", required=True, help="bot:<name> or pilot:<agent dir>")
    ap.add_argument("--opp-deck", default=None, help="opponent deck csv (bots default to their DECK)")
    ap.add_argument("--engine-root", default=_ROOT)
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=6000)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    our_agent = os.path.abspath(args.our_agent)
    if not os.path.isfile(os.path.join(our_agent, "scorer.py")):
        print(f"ERROR: {our_agent} is not a flat agent dir (no scorer.py)")
        return 2
    our_deck = _read_deck(args.our_deck)

    opp_spec = args.opp
    if opp_spec.startswith("bot:"):
        sys.path.insert(0, _ROOT)
        mod = importlib.import_module(f"agent.bots.bot_{opp_spec[4:]}")
        opp_deck = _read_deck(args.opp_deck) if args.opp_deck else list(mod.DECK)
    elif opp_spec.startswith("pilot:"):
        d = os.path.abspath(opp_spec[len("pilot:"):])
        opp_spec = f"pilot:{d}"
        if not args.opp_deck:
            print("ERROR: pilot: opponents need --opp-deck")
            return 2
        opp_deck = _read_deck(args.opp_deck)
    else:
        print(f"ERROR: bad --opp {opp_spec!r}")
        return 2

    lab = args.label or f"{os.path.basename(our_agent)} vs {args.opp}"
    print(f"[{lab}] our deck {os.path.basename(args.our_deck)} ({len(our_deck)}) vs "
          f"{args.opp} deck ({len(opp_deck)})  games={args.games} workers={args.workers}")

    jobs = [(g % 2, args.max_steps) for g in range(args.games)]
    counts = {"W": 0, "L": 0, "D": 0, "E": 0}
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=args.workers, initializer=_init,
                  initargs=(our_agent, opp_spec, os.path.abspath(args.engine_root),
                            (our_deck, opp_deck))) as pool:
        done = 0
        for outcome in pool.imap_unordered(_play_one, jobs, chunksize=1):
            counts[outcome] += 1
            done += 1
            if done % 10 == 0 or done == len(jobs):
                w, l = counts["W"], counts["L"]
                dec = w + l
                wr = (w / dec) if dec else 0.0
                print(f"  [{done:3d}/{len(jobs)}] W{w} L{l} D{counts['D']} E{counts['E']}  "
                      f"wr={wr:5.1%}  ({time.time()-t0:5.1f}s)", flush=True)

    w, l, d, e = counts["W"], counts["L"], counts["D"], counts["E"]
    dec = w + l
    p, lo, hi = _wilson(w, dec)
    print(f"RESULT [{lab}]: W{w} L{l} D{d} E{e}  win-rate(decided)={p:.1%} "
          f"95%CI[{lo:.1%},{hi:.1%}] n={dec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
