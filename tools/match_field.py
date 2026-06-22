"""Local matchup tournament: our belief-agent (prize tracking + corrected determinization + opponent
detection + heuristic search) vs each field deck, both sides playing the full pipeline. Tells us which
matchups we lose so we fix the right thing — offline, no submission slots burned.

  ./scripts/run.sh -m tools.match_field --deck data/decks/starmie.csv --games 24 --budget 0.4 --workers 14
"""
import argparse, json, os, random, sys
from multiprocessing import get_context

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT); sys.path.insert(0, os.path.join(_ROOT, "agent"))
from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_start, battle_finish, battle_select  # noqa: E402


def _read(p):
    return [int(x) for x in open(p).read().splitlines() if x.strip()][:60]


def _searchable(sel, cur):
    return (sel and cur and sel.get("context") == 0 and sel.get("maxCount") == 1
            and (sel.get("minCount") or 0) <= 1 and len(sel.get("option") or []) > 1)


def _worker(task):
    seed, our, opp, budget = task
    import engine_rs
    from prize_tracker import PrizeTracker
    from belief import corrected_deck
    from opp_detect import detect_opp
    engine_rs.init(os.path.abspath(os.path.join(_ROOT, "cg", "libcg.so")))
    random.seed(seed)
    decks = [our, opp]
    defmodel = [opp, our]               # each side's fallback opp_model
    trackers = [PrizeTracker(our), PrizeTracker(opp)]
    obs, _ = battle_start(our, opp)
    if obs is None:
        return None
    try:
        for _ in range(2500):
            o = to_observation_class(obs)
            cur = o.current
            if cur is not None and cur.result != -1:
                return 1 if cur.result == 0 else (0 if cur.result == 1 else -1)  # 1 = our (player 0) win
            if o.select is None:
                return -1
            yi = cur.yourIndex if cur is not None else 0
            trackers[yi].update(o, obs)
            sd = obs.get("select"); cd_ = obs.get("current")
            if _searchable(sd, cd_):
                deck = corrected_deck(o, decks[yi], trackers[yi].prized_cards())
                opm = detect_opp(o, defmodel[yi])
                ev = 1 if yi == 0 else 0   # A/B: player 0 = new eval (v1), player 1 = old eval (v0)
                try:
                    sel = engine_rs.choose(json.dumps(obs), deck, opm, budget, 10**9, 1.4, seed, False, 0, ev)
                    pick = sel if (isinstance(sel, list) and sel) else [0]
                except Exception:
                    pick = [0]
            else:
                k = sd.get("maxCount") or 1
                pick = random.sample(range(len(sd.get("option"))), min(k, len(sd.get("option"))))
            obs = battle_select(pick)
        return -1
    finally:
        battle_finish()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default=os.path.join(_ROOT, "data/decks/starmie.csv"))
    ap.add_argument("--opps", default="lucario_praxel,dragapult,dunsparce,fezandipiti,starmie")
    ap.add_argument("--games", type=int, default=24)
    ap.add_argument("--budget", type=float, default=0.4)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    our = _read(a.deck)
    ctx = get_context("spawn")
    print(f"our deck vs the field ({a.games} games each, {a.budget}s/move):")
    for oppname in a.opps.split(","):
        opp = _read(os.path.join(_ROOT, "data/decks", oppname + ".csv"))
        tasks = [(i * 7 + 1, our, opp, a.budget) for i in range(a.games)]
        res = []
        with ctx.Pool(a.workers) as pool:
            for r in pool.imap_unordered(_worker, tasks):
                if r is not None and r >= 0:
                    res.append(r)
        n = len(res); w = sum(res)
        wr = w / n if n else 0.0
        print(f"  vs {oppname:16} {w:2}/{n:2}  = {wr:5.1%}")


if __name__ == "__main__":
    main()
