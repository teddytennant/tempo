"""Deck-matchup eval with correct deck/agent binding.

arena.anomaly_eval alternates the instrumented agent's SEAT while the decks stay bound to player
indices — fine for comparing two different agent builds on fixed decks, but for a deck-vs-deck
matchup with the SAME agent code on both sides it degenerates to a coin-flip (the instrumented
side pilots the opposing deck every other game, so the aggregate is 50% by construction).

This runner keeps OUR deck with the instrumented side and alternates the PLAYER ORDER instead,
so first-player advantage cancels while the matchup stays fixed.

Usage:
    ./scripts/run.sh -m arena.matchup_eval --games 40 \
        --deck data/decks/mined/The_Debauchery_Tea_Party.csv --opp_deck data/decks/crustle.csv
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent"))

from arena.anomaly_eval import play_instrumented  # noqa: E402
from arena.selfplay import _read_deck, _load_deploy, _load_floor, random_agent  # noqa: E402
import arena.selfplay as sp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--deck", required=True, help="our deck.csv (stays with the instrumented agent)")
    ap.add_argument("--opp_deck", required=True, help="opponent deck.csv")
    ap.add_argument("--opp", default="deploy",
                    help="deploy | floor | random | bot:<name> (agent/bots/bot_<name>.py)")
    args = ap.parse_args()

    deck = _read_deck(args.deck)
    odeck = _read_deck(args.opp_deck)
    sp._DECK = deck
    deploy = _load_deploy()
    if args.opp.startswith("bot:"):
        import importlib
        botmod = importlib.import_module(f"bots.bot_{args.opp[4:]}")
        opp = botmod.agent
    else:
        opp = {"deploy": deploy, "floor": _load_floor(), "random": random_agent}[args.opp]

    agg = {"we_won": 0, "we_lost": 0, "draw": 0, "unfinished": 0, "error_games": 0,
           "deckout_loss": 0, "no_offense_loss": 0, "start_fail": 0}
    for g in range(args.games):
        seat = g % 2  # our seat AND our deck's slot move together; player order alternates
        if seat == 0:
            r = play_instrumented(deploy, opp, deck, odeck, me_i_target=0)
        else:
            r = play_instrumented(deploy, opp, odeck, deck, me_i_target=1)
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
    print(f"games={args.games}  our_deck={os.path.basename(args.deck)} vs "
          f"{os.path.basename(args.opp_deck)} (opp={args.opp}, player order alternated)")
    print(f"  win-rate(decided) = {wr:.1f}%  (W={agg['we_won']} L={agg['we_lost']} "
          f"D={agg['draw']} unfinished={agg['unfinished']})")
    print(f"  ANOMALIES: error_games={agg['error_games']}  deckout_loss={agg['deckout_loss']}  "
          f"no_offense_loss={agg['no_offense_loss']}  start_fail={agg['start_fail']}")


if __name__ == "__main__":
    main()
