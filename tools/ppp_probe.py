"""What is the frontier's ACTUAL rule for Premium Power Pro? Derive it, don't guess it.

`tools/card_use.py` on 4,000 real MAIN decisions: Premium Power Pro is on the menu 1,618 times, the
frontier plays it 256 (15.8%) and we play it 4 (0.2%). Our guard in `agent/lucario_rules.py` fires
only when `best_dmg < opp_hp <= best_dmg + 30` AND the Active is in the Lucario line -- i.e. only
when the +30 EXACTLY converts a swing into a knockout, with Hariyama/Solrock/Makuhita (all {F}, all
boosted by the card) excluded outright.

Rather than invent a replacement, bucket the frontier's own 1,618 offers by the features a rule
could key on and read its take rate off each bucket.

    ./scripts/run.sh -m tools.ppp_probe --src experiments/luc_majkel_v7_src --n 6000
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = 0
T_PLAY, T_ATTACK = 7, 13
PREMIUM_POWER_PRO = 1141


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=6000)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    from cg.api import to_observation_class, all_card_data
    import lucario_rules as LR
    names = {c.cardId: c.name for c in all_card_data()}

    buckets = collections.Counter()   # (feature) -> offers
    taken = collections.Counter()     # (feature) -> elite plays it here
    by_active = collections.Counter()
    by_active_take = collections.Counter()
    seen = 0

    with open(a.recs) as f:
        for line in f:
            if a.n and seen >= a.n:
                break
            try:
                r = json.loads(line)
            except Exception:
                continue
            obs_d = r.get("obs") or {}
            sel = obs_d.get("select")
            if not isinstance(sel, dict) or sel.get("context") != MAIN:
                continue
            opts = sel.get("option") or []
            act = r.get("action") or []
            if not act or not (0 <= act[0] < len(opts)):
                continue
            seen += 1
            try:
                obs = to_observation_class(obs_d)
            except Exception:
                continue
            state = obs.current
            me_i = state.yourIndex
            me = state.players[me_i]
            opp = state.players[1 - me_i]
            active = me.active[0] if me.active else None
            oa = opp.active[0] if opp.active else None
            if active is None or oa is None:
                continue

            ppp_idx = [i for i, o in enumerate(opts)
                       if o.get("type") == T_PLAY
                       and LR._id(LR._get(obs, o.get("area") or 2, o.get("index") or 0, me_i))
                       == PREMIUM_POWER_PRO]
            if not ppp_idx:
                continue
            chose = act[0] in ppp_idx

            atk_opts = [o for o in opts if o.get("type") == T_ATTACK]
            best = 0
            for o in atk_opts:
                try:
                    best = max(best, LR._attack_damage(active, obs.select.option[opts.index(o)]
                                                       .attackId, oa))
                except Exception:
                    pass
            hp = oa.hp or 0
            if not atk_opts:
                f_atk = "no-attack-on-menu"
            elif best >= hp:
                f_atk = "already-lethal"
            elif best + 30 >= hp:
                f_atk = "+30 CONVERTS to a KO"
            else:
                f_atk = "+30 does not convert"
            buckets[f_atk] += 1
            taken[f_atk] += chose

            aid = LR._id(active)
            in_line = aid in LR._LUCARIO_LINE
            f_line = "active in Lucario line" if in_line else f"active = {names.get(aid, aid)}"
            by_active[f_line] += 1
            by_active_take[f_line] += chose

            # what our SHIPPED guard would say
            ours = (in_line and best < hp <= best + 30)
            buckets[("SHIPPED-GUARD", ours)] += 1
            taken[("SHIPPED-GUARD", ours)] += chose

    print(f"src={src}\nMAIN decisions read: {seen}")
    tot = sum(v for k, v in buckets.items() if isinstance(k, str))
    tot_t = sum(v for k, v in taken.items() if isinstance(k, str))
    print(f"\nPremium Power Pro offered on {tot} of them; the frontier played it {tot_t} "
          f"({100.0*tot_t/max(tot,1):.1f}%)\n")
    print(f"{'bucket':<34}{'offers':>8}{'elite played':>14}{'rate':>9}")
    for k in ("+30 CONVERTS to a KO", "+30 does not convert", "already-lethal", "no-attack-on-menu"):
        if buckets[k]:
            print(f"{k:<34}{buckets[k]:>8}{taken[k]:>14}{100.0*taken[k]/buckets[k]:>8.1f}%")
    print()
    for k, v in sorted(by_active.items(), key=lambda kv: -kv[1]):
        print(f"{k:<34}{v:>8}{by_active_take[k]:>14}{100.0*by_active_take[k]/v:>8.1f}%")
    print()
    for flag in (True, False):
        k = ("SHIPPED-GUARD", flag)
        if buckets[k]:
            print(f"{'our guard says PLAY' if flag else 'our guard says NEVER':<34}"
                  f"{buckets[k]:>8}{taken[k]:>14}{100.0*taken[k]/buckets[k]:>8.1f}%")


if __name__ == "__main__":
    main()
