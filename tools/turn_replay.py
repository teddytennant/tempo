"""Do we take the SAME ACTIONS in a turn as the frontier, just in a different order?

Every agreement harness in this workspace scores a single decision against the elite's answer at
that decision. On the MAIN menu that measurement is contaminated by turn ORDERING: if the elite
attacks immediately and we attach first and attack second, we are marked wrong at decision 1 and
wrong at decision 2, and we played the identical turn. "Turn-ordering confound" has been the
standing explanation for `main` sitting at 46.6% while `swing-or-end` sits at 88.0%, and it has
never actually been measured.

This measures it. For each elite TURN in the corpus:

  * the elite's turn is the multiset of MAIN actions it took, canonicalised to CARD IDENTITY
    (play Buddy-Buddy Poffin / attach a Fighting Energy to the Active / attack with Aura Sphere)
    rather than to option indices, which shift as the turn proceeds;
  * our turn is produced by forking the engine at the turn's FIRST decision and driving our own
    deploy entry point through the whole turn, one search_step at a time, until control passes to
    the opponent -- i.e. we play the turn out ourselves and are scored on what we did, not on when.

Then:

  same_multiset   we played the same actions in some order  -> the ordering confound is real and
                  the low `main` agreement is an artifact
  differs         we genuinely played a different turn      -> a real, localisable policy loss

and, for the tempo angle specifically, per-turn resource use on both sides: did the turn end with
the once-per-turn energy attachment unspent, with a bench slot free and a basic in hand, with a
retreat and no attack.

CONFOUND, stated up front: our fork determinizes the unseen deck, so any turn in which cards are
DRAWN diverges from reality at the draw. Turns are therefore bucketed by whether they contain a
draw, and the no-draw bucket is the clean one. A second, smaller one: `search_begin_input` is None
inside the fork, so the in-turn win verifier (agent/lethal.py) cannot run there -- the replay is the
scorer's turn, and the verifier fires on ~1% of decisions.

    ./scripts/run.sh -m tools.turn_replay --src . --n 600
    ./scripts/run.sh -m tools.turn_replay --src experiments/luc_majkel_v7_src --n 600 --json a.json
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN = 0
T_PLAY, T_ATTACH, T_EVOLVE, T_ABILITY, T_RETREAT, T_ATTACK, T_END = 7, 8, 9, 10, 12, 13, 14
A_HAND, A_ACTIVE, A_BENCH = 2, 4, 5

_PLACEHOLDER = 1072  # a vanilla basic, the same one agent/lethal.py uses for hidden opponent cards
_MAX_STEPS = 80      # a turn is a few actions; this only stops a pathological loop


# --------------------------------------------------------------------------- canonical actions

def _g(opt, key, default):
    """Records omit zero-valued option fields; `dataclasses.asdict` on a forked observation keeps
    them as None. Both must read as the default or every descriptor comes out as PLAY(None)."""
    v = opt.get(key)
    return default if v is None else v


def _card_id(state, pi, area, index):
    try:
        p = state["players"][pi]
        if area == A_HAND:
            return p["hand"][index]["id"]
        if area == A_ACTIVE:
            return p["active"][index]["id"]
        if area == A_BENCH:
            return p["bench"][index]["id"]
    except Exception:
        pass
    return None


def _target(state, pi, opt):
    """Where an ATTACH/EVOLVE/ABILITY is pointed, as (slot-kind, pokemon id)."""
    ia, ii = opt.get("inPlayArea"), _g(opt, "inPlayIndex", 0)
    if ia is None:
        return None
    return ("A" if ia == A_ACTIVE else "B", _card_id(state, pi, ia, ii))


def action_desc(state, opt):
    """A MAIN option as an order-independent, index-independent descriptor. None = ignore (END)."""
    t = opt.get("type")
    pi = _g(state, "yourIndex", 0)
    idx = _g(opt, "index", 0)
    if t == T_END:
        return None
    if t == T_ATTACK:
        act = _card_id(state, pi, A_ACTIVE, 0)
        return ("ATTACK", act, idx)
    if t == T_RETREAT:
        return ("RETREAT", _card_id(state, pi, A_ACTIVE, 0))
    if t == T_PLAY:
        return ("PLAY", _card_id(state, pi, _g(opt, "area", A_HAND), idx))
    if t == T_EVOLVE:
        return ("EVOLVE", _card_id(state, pi, _g(opt, "area", A_HAND), idx),
                _target(state, pi, opt))
    if t == T_ATTACH:
        return ("ATTACH", _card_id(state, pi, _g(opt, "area", A_HAND), idx),
                _target(state, pi, opt))
    if t == T_ABILITY:
        src = _card_id(state, pi, _g(opt, "area", A_ACTIVE), idx)
        return ("ABILITY", src, _g(opt, "number", 0))
    return (str(t), idx)


def _is_draw_action(desc):
    return desc is not None and desc[0] == "PLAY"


# --------------------------------------------------------------------------- corpus -> turns

def load_turns(path, limit):
    """Segment the (game-ordered) record stream into turns. A turn is a maximal run of records
    sharing a `current.turn` value; the corpus only holds the frontier player's own decisions."""
    turns, cur, prev = [], [], None
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            obs = r.get("obs") or {}
            st = obs.get("current")
            sel = obs.get("select")
            if not isinstance(st, dict) or not isinstance(sel, dict):
                continue
            key = (st.get("turn"), st.get("yourIndex"))
            if prev is not None and key != prev:
                if cur:
                    turns.append(cur)
                cur = []
                if limit and len(turns) >= limit:
                    break
            prev = key
            cur.append(r)
    if cur and (not limit or len(turns) < limit):
        turns.append(cur)
    return turns


def elite_turn_actions(turn):
    """The frontier player's MAIN actions this turn, plus what it spent."""
    acts, ended = [], False
    for r in turn:
        obs = r["obs"]
        sel = obs["select"]
        if sel.get("context") != MAIN:
            continue
        a = r.get("action") or []
        if not a:
            continue
        opts = sel.get("option") or []
        if not (0 <= a[0] < len(opts)):
            continue
        opt = opts[a[0]]
        if opt.get("type") == T_END:
            ended = True
            continue
        d = action_desc(obs["current"], opt)
        if d is not None:
            acts.append(d)
    return acts, ended


# --------------------------------------------------------------------------- our turn, in a fork

def _det_deck(obs_cls, decklist, belief):
    st = obs_cls.current
    me = st.yourIndex
    mine, opp = st.players[me], st.players[1 - me]
    prize_n, deck_n = max(len(mine.prize), 1), max(mine.deckCount, 1)
    your_deck = your_prize = None
    if belief is not None:
        try:
            ordered = belief(obs_cls, list(decklist), None)
            if ordered and len(ordered) >= prize_n:
                your_prize = ordered[:prize_n]
                your_deck = ordered[prize_n:prize_n + deck_n]
        except Exception:
            your_deck = None
    if not your_deck:
        pool = (list(decklist) * 3) if decklist else [_PLACEHOLDER]
        your_deck, your_prize = pool[:deck_n], pool[:prize_n]
    opp_active = [_PLACEHOLDER] if (opp.active and opp.active[0] is None) else []
    return (your_deck, your_prize,
            [_PLACEHOLDER] * max(opp.deckCount, 1),
            [_PLACEHOLDER] * max(len(opp.prize), 1),
            [_PLACEHOLDER] * max(opp.handCount, 0) if opp.handCount else [],
            opp_active)


def our_turn_actions(api, agent_fn, obs_dict, decklist, belief):
    """Fork at this decision and drive our own agent through the rest of the turn.

    Returns (actions, ended_turn, steps, error, why, first_sel) -- error is "" on success, why is
    how the replay loop terminated (the honest read on whether the replay ran the whole turn), and
    first_sel is the answer our agent gave to the fork's FIRST question (the fidelity control)."""
    to_cls, sbegin, sstep, srelease, send = api
    try:
        obs_cls = to_cls(obs_dict)
    except Exception as e:
        return [], False, 0, f"to_class:{type(e).__name__}", "to_class", None
    me = obs_cls.current.yourIndex
    root = None
    acts, ended, steps = [], False, 0
    why, first_sel = "maxsteps", None
    try:
        root = sbegin(obs_cls, *_det_deck(obs_cls, decklist, belief))
        node, node_obs = root.searchId, root.observation
        owned = []
        while steps < _MAX_STEPS:
            st = node_obs.current
            if st is None:
                why = "no-state"
                break
            if getattr(st, "result", -1) not in (None, -1):
                why = "terminal"
                break
            if getattr(st, "yourIndex", me) != me:
                ended, why = True, "passed-to-opponent"
                break
            sel = node_obs.select
            if sel is None or not sel.option:
                why = "no-select"
                break
            d = dataclasses.asdict(node_obs)
            try:
                got = agent_fn(d)
            except Exception as e:
                return acts, ended, steps, f"agent:{type(e).__name__}", why, first_sel
            if not isinstance(got, list):
                return acts, ended, steps, "agent:not-a-list", why, first_sel
            if first_sel is None:
                first_sel = list(got)
            if d["select"].get("context") == MAIN and got:
                o = d["select"]["option"][got[0]]
                if o.get("type") == T_END:
                    ended = True
                else:
                    desc = action_desc(d["current"], o)
                    if desc is not None:
                        acts.append(desc)
            steps += 1
            try:
                child = sstep(node, got)
            except Exception as e:
                return acts, ended, steps, f"step:{type(e).__name__}", "step-error", first_sel
            owned.append(child.searchId)
            node, node_obs = child.searchId, child.observation
        for sid in owned:
            try:
                srelease(sid)
            except Exception:
                pass
        return acts, ended, steps, "", why, first_sel
    except Exception as e:
        return acts, ended, steps, f"fork:{type(e).__name__}", "fork-error", first_sel
    finally:
        try:
            if root is not None:
                srelease(root.searchId)
        except Exception:
            pass
        try:
            send()
        except Exception:
            pass


# --------------------------------------------------------------------------- report helpers

def _names(ids):
    try:
        from cg.api import all_card_data
        data = all_card_data()
        out = {}
        for c in data:
            cid = getattr(c, "id", None)
            if cid is not None and cid not in out:
                out[cid] = getattr(c, "name", str(cid))
        return {i: out.get(i, str(i)) for i in ids}
    except Exception:
        return {i: str(i) for i in ids}


def _fmt(desc, nm):
    if desc is None:
        return "-"
    kind = desc[0]
    cid = desc[1] if len(desc) > 1 else None
    tail = ""
    if kind in ("ATTACH", "EVOLVE") and len(desc) > 2 and desc[2]:
        tail = f"->{desc[2][0]}:{nm.get(desc[2][1], desc[2][1])}"
    if kind == "ATTACK":
        tail = f"#{desc[2]}"
    return f"{kind}({nm.get(cid, cid)}){tail}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=_ROOT)
    ap.add_argument("--recs", default=os.path.join(_ROOT, "data/bc_lucario/records_11447.jsonl"))
    ap.add_argument("--n", type=int, default=600, help="turns to replay")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    sys.path.insert(0, os.path.join(src, "agent"))
    sys.path.insert(0, src)
    from cg.api import to_observation_class, search_begin, search_step, search_release, search_end
    api = (to_observation_class, search_begin, search_step, search_release, search_end)
    import agent.main as M
    try:
        from belief import corrected_deck as belief
    except Exception:
        belief = None

    deck_path = os.path.join(src, "agent", "deck.csv")
    with open(deck_path) as f:
        decklist = [int(x) for x in f.read().splitlines() if x.strip()]
    print(f"src={src}\ndeck={deck_path} ({len(decklist)} cards)")

    turns = load_turns(a.recs, a.n)
    print(f"turns segmented: {len(turns)}")

    stats = collections.Counter()
    missing = collections.Counter()   # elite played it, we did not
    extra = collections.Counter()     # we played it, the elite did not
    examples, lat, errs = [], [], collections.Counter()
    stop = collections.Counter()
    fork_fidelity = [0, 0]

    for ti, turn in enumerate(turns):
        first = turn[0]
        obs0 = first["obs"]
        if obs0["select"].get("context") != MAIN or not obs0.get("search_begin_input"):
            stats["skipped_no_fork"] += 1
            continue
        e_acts, e_ended = elite_turn_actions(turn)
        t0 = time.perf_counter()
        o_acts, o_ended, steps, err, why, first_sel = our_turn_actions(
            api, M.agent, obs0, decklist, belief)
        stop[why] += 1
        try:
            live_first = M.agent(obs0)
        except Exception:
            live_first = None
        lat.append((time.perf_counter() - t0) * 1000.0)
        if err:
            errs[err] += 1
            stats["error"] += 1
            continue
        stats["replayed"] += 1
        # Control: the fork's FIRST question is the live question. If our agent answers it
        # differently inside the fork, the fork is not reproducing the live agent and every
        # number below is suspect.
        if live_first is not None and first_sel is not None:
            fork_fidelity[1] += 1
            if list(first_sel) == list(live_first):
                fork_fidelity[0] += 1
        drew = any(_is_draw_action(d) for d in e_acts) or any(_is_draw_action(d) for d in o_acts)
        bucket = "draw" if drew else "nodraw"
        stats[f"{bucket}_n"] += 1

        em, om = collections.Counter(e_acts), collections.Counter(o_acts)
        if em == om:
            stats["same_multiset"] += 1
            stats[f"{bucket}_same"] += 1
        else:
            for d, c in (em - om).items():
                missing[d] += c
            for d, c in (om - em).items():
                extra[d] += c
            if len(examples) < 25:
                examples.append({"turn_i": ti, "turn": obs0["current"].get("turn"),
                                 "elite": e_acts, "ours": o_acts, "drew": drew})
        # --- tempo accounting, both sides
        e_atk = any(d[0] == "ATTACK" for d in e_acts)
        o_atk = any(d[0] == "ATTACK" for d in o_acts)
        e_att = any(d[0] == "ATTACH" for d in e_acts)
        o_att = any(d[0] == "ATTACH" for d in o_acts)
        stats["elite_attacked"] += e_atk
        stats["our_attacked"] += o_atk
        stats["elite_attached"] += e_att
        stats["our_attached"] += o_att
        stats["both_attacked"] += (e_atk and o_atk)
        stats["elite_only_attacked"] += (e_atk and not o_atk)
        stats["our_only_attacked"] += (o_atk and not e_atk)
        stats["elite_actions"] += len(e_acts)
        stats["our_actions"] += len(o_acts)

    lat.sort()
    q = lambda p: lat[min(len(lat) - 1, int(len(lat) * p))] if lat else 0.0
    rep = stats["replayed"] or 1

    print(f"\nreplay terminated: {dict(stop)}")
    if fork_fidelity[1]:
        print(f"FORK FIDELITY: our agent gives the fork's first question the same answer it gives "
              f"the live one in {fork_fidelity[0]}/{fork_fidelity[1]} "
              f"({100.0*fork_fidelity[0]/fork_fidelity[1]:.1f}%)")
    print(f"\nreplayed {stats['replayed']}   skipped(no fork) {stats['skipped_no_fork']}   "
          f"errors {stats['error']} {dict(errs) if errs else ''}")
    print(f"replay latency ms  p50 {q(.5):.1f}  p99 {q(.99):.1f}  max {lat[-1] if lat else 0:.1f}")
    print(f"\nTURN-LEVEL ACTION-MULTISET AGREEMENT (ordering fully de-confounded)")
    print(f"  identical turn        {stats['same_multiset']:>5} / {rep}  "
          f"= {100.0*stats['same_multiset']/rep:.1f}%")
    for b in ("nodraw", "draw"):
        n = stats[f"{b}_n"]
        if n:
            print(f"    {b:<7}            {stats[f'{b}_same']:>5} / {n}  "
                  f"= {100.0*stats[f'{b}_same']/n:.1f}%")
    print(f"\nTEMPO, per turn                elite      ours")
    print(f"  attacked                  {stats['elite_attacked']:>6}    {stats['our_attacked']:>6}"
          f"   ({100.0*stats['elite_attacked']/rep:.1f}% vs {100.0*stats['our_attacked']/rep:.1f}%)")
    print(f"  attached energy           {stats['elite_attached']:>6}    {stats['our_attached']:>6}"
          f"   ({100.0*stats['elite_attached']/rep:.1f}% vs {100.0*stats['our_attached']/rep:.1f}%)")
    print(f"  actions taken             {stats['elite_actions']:>6}    {stats['our_actions']:>6}"
          f"   ({stats['elite_actions']/rep:.2f} vs {stats['our_actions']/rep:.2f} per turn)")
    print(f"  elite swung, we did NOT   {stats['elite_only_attacked']:>6}"
          f"   ({100.0*stats['elite_only_attacked']/rep:.1f}%)")
    print(f"  we swung, elite did NOT   {stats['our_only_attacked']:>6}"
          f"   ({100.0*stats['our_only_attacked']/rep:.1f}%)")

    ids = set()
    for d in list(missing) + list(extra):
        ids.add(d[1])
        if len(d) > 2 and isinstance(d[2], tuple):
            ids.add(d[2][1])
    nm = _names({i for i in ids if isinstance(i, int)})

    print(f"\nACTIONS THE ELITE TOOK AND WE DID NOT (top 20)")
    for d, c in missing.most_common(20):
        print(f"  {c:>5}  {_fmt(d, nm)}")
    print(f"\nACTIONS WE TOOK AND THE ELITE DID NOT (top 20)")
    for d, c in extra.most_common(20):
        print(f"  {c:>5}  {_fmt(d, nm)}")

    print(f"\nEXAMPLE DIVERGENT TURNS")
    for ex in examples[:12]:
        print(f"  turn {ex['turn']:>3} {'(drew)' if ex['drew'] else '       '}")
        print(f"    elite: {[_fmt(d, nm) for d in ex['elite']]}")
        print(f"    ours : {[_fmt(d, nm) for d in ex['ours']]}")

    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"src": src, "stats": dict(stats),
                       "missing": [[list(map(str, d)), c] for d, c in missing.most_common(60)],
                       "extra": [[list(map(str, d)), c] for d, c in extra.most_common(60)],
                       "p50": q(.5), "p99": q(.99)}, fh, indent=1, default=str)
        print(f"\nwrote {a.json}")


if __name__ == "__main__":
    main()
