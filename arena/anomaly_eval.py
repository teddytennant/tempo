"""Anomaly-instrumented arena (per docs/plans/05-eval-methodology.md §2).

The eval doc says: track deterministic failure modes, not just win-rate (which is ±14pt noisy).
This harness drives full real-engine games of our deployed agent and reports the prescribed
anomalies so improvements can be validated on *deterministic* signal:

  - error_games     : a game where our agent raised (fell back to legal default)
  - deckout_loss    : we lost AND our deck was empty at game end (self-milled out)
  - no_offense_loss : we lost having landed <= 1 damaging attack (pressure failure)
  - unfinished      : game hit the step cap without a result

Usage (on NixOS, via the lib wrapper):
    ./scripts/run.sh -m arena.anomaly_eval --games 40 --opp floor --deck agent/deck.csv
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402
from arena.selfplay import random_agent, _load_floor, _load_deploy, _read_deck  # noqa: E402


def _our_deck_count(obs, me_i):
    try:
        return obs.current.players[me_i].deckCount
    except Exception:
        return None


def _damaging_attack(obs, sel, me_i):
    """True iff the selection plays an ATTACK option whose attack id is non-zero-damage.
    Cheap proxy: any ATTACK option chosen counts as offense (the scorer only fires KO/chip
    attacks). We can't see resolved damage here, so this measures 'did we attack at all'."""
    try:
        from cg.api import OptionType
        opts = obs.select.option
        for i in sel:
            if 0 <= i < len(opts) and opts[i].type == OptionType.ATTACK:
                return True
    except Exception:
        pass
    return False


def play_instrumented(deploy, opp, deck0, deck1, me_i_target=0, max_steps=2000):
    """Play one game with our deploy agent seated at me_i_target. Returns a dict of outcome flags."""
    agents = [None, None]
    agents[me_i_target] = deploy
    agents[1 - me_i_target] = opp
    obs_dict, _ = battle_start(deck0, deck1)
    if obs_dict is None:
        return {"result": -1, "error": True, "our_attacks": 0, "our_deck_end": None, "unfinished": False, "start_fail": True}
    our_errors = 0
    our_attacks = 0
    our_deck_end = None
    result = -1
    try:
        for _ in range(max_steps):
            obs = to_observation_class(obs_dict)
            cur = obs.current
            if cur is not None and getattr(cur, "result", -1) != -1:
                result = cur.result
                break
            if obs.select is None:
                break
            who = cur.yourIndex if cur is not None else 0
            if who == me_i_target:
                our_deck_end = _our_deck_count(obs, who)
                try:
                    sel = agents[who](obs_dict)
                except Exception:
                    our_errors += 1
                    sel = list(range(min(obs.select.minCount, len(obs.select.option))))
                if _damaging_attack(obs, sel, who):
                    our_attacks += 1
            else:
                try:
                    sel = agents[who](obs_dict)
                except Exception:
                    sel = list(range(min(obs.select.minCount, len(obs.select.option))))
            obs_dict = battle_select(sel)
    finally:
        battle_finish()
    we_lost = (result == (1 - me_i_target))
    return {
        "result": result,
        "we_won": result == me_i_target,
        "we_lost": we_lost,
        "draw": result == 2,
        "unfinished": result == -1,
        "error": our_errors > 0,
        "our_attacks": our_attacks,
        "our_deck_end": our_deck_end,
        "deckout_loss": we_lost and (our_deck_end is not None and our_deck_end <= 0),
        "no_offense_loss": we_lost and our_attacks <= 1,
        "start_fail": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--me", choices=["deploy", "bc2"], default="deploy",
                    help="which agent to instrument: deploy=agent/main.py, bc2=agent/main_bc2.py")
    ap.add_argument("--opp", choices=["floor", "random", "deploy"], default="floor")
    ap.add_argument("--deck", default=os.path.join(_ROOT, "agent", "deck.csv"))
    ap.add_argument("--opp_deck", default=None, help="opponent deck.csv (default: same as --deck)")
    args = ap.parse_args()

    global _DECK
    deck = _read_deck(args.deck)
    odeck = _read_deck(args.opp_deck) if args.opp_deck else deck
    import arena.selfplay as sp
    sp._DECK = deck  # random/floor agents read this

    if args.me == "bc2":
        import main_bc2
        deploy = main_bc2.agent
    else:
        deploy = _load_deploy()
    opp = {"floor": _load_floor(), "random": random_agent, "deploy": _load_deploy()}[args.opp]

    agg = {"we_won": 0, "we_lost": 0, "draw": 0, "unfinished": 0, "error_games": 0,
           "deckout_loss": 0, "no_offense_loss": 0, "start_fail": 0}
    for g in range(args.games):
        r = play_instrumented(deploy, opp, deck, odeck, me_i_target=(g % 2))  # alternate seats
        if r["start_fail"]:
            agg["start_fail"] += 1
            continue
        agg["we_won"] += int(r["we_won"]); agg["we_lost"] += int(r["we_lost"])
        agg["draw"] += int(r["draw"]); agg["unfinished"] += int(r["unfinished"])
        agg["error_games"] += int(r["error"])
        agg["deckout_loss"] += int(r["deckout_loss"])
        agg["no_offense_loss"] += int(r["no_offense_loss"])

    decided = agg["we_won"] + agg["we_lost"]
    wr = (100.0 * agg["we_won"] / decided) if decided else 0.0
    print(f"games={args.games} deploy vs {args.opp}  (seats alternated)")
    print(f"  win-rate(decided) = {wr:.1f}%  (W={agg['we_won']} L={agg['we_lost']} D={agg['draw']} unfinished={agg['unfinished']})")
    print(f"  ANOMALIES: error_games={agg['error_games']}  deckout_loss={agg['deckout_loss']}  "
          f"no_offense_loss={agg['no_offense_loss']}  start_fail={agg['start_fail']}")
    print(f"  (of {agg['we_lost']} losses: {agg['deckout_loss']} deckout, {agg['no_offense_loss']} no-offense)")


if __name__ == "__main__":
    main()
