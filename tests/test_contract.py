"""Stage-1 contract tests: the agent must always return a legal selection and never raise.

These encode the acceptance criteria from docs/plans/01-agent-contract.md. They run against the
mock engine (tests/mock_cg) — no Kaggle assets required.
"""
import random

import cg.api as cg
import main


def _state(my_active_hp=100, opp_active_hp=100, supporter=False, stadium=False):
    me = cg.Player(active=[cg.Pokemon(1, hp=my_active_hp, energies=[cg.EnergyType.PSYCHIC])],
                   hand=[cg.Card(3), cg.Card(4)], handCount=2, deckCount=40)
    opp = cg.Player(active=[cg.Pokemon(2, hp=opp_active_hp)], deckCount=40)
    return cg.State(yourIndex=0, players=[me, opp],
                    supporterPlayed=supporter, stadiumPlayed=stadium)


def _assert_legal(result, select):
    n = len(select.option)
    minc = max(0, min(select.minCount, n))
    maxc = max(minc, min(select.maxCount, n))
    assert isinstance(result, list)
    assert all(isinstance(i, int) for i in result)
    assert all(0 <= i < n for i in result), f"index out of range: {result} (n={n})"
    assert len(result) == len(set(result)), f"duplicate indices: {result}"
    assert minc <= len(result) <= maxc, f"count {len(result)} not in [{minc},{maxc}]"


# ── deck-selection phase ──────────────────────────────────────────────────────
def test_deck_selection_returns_60_ids_on_dict_none():
    out = main.agent({"select": None})
    assert out == main.my_deck and len(out) == 60


def test_deck_selection_via_observation_none_select():
    out = main.agent({"current": _state(), "select": None})
    assert out == main.my_deck


# ── core in-game prompts ──────────────────────────────────────────────────────
def test_go_first_is_accepted():
    # This used to assert the opposite ("setup/reactive decks want the extra information"), which
    # was never measured and has now been refuted twice: real ladder players answered YES in 91 of
    # 93 IS_FIRST positions in the 2026-08-08 dump, and a forced mirror A/B over 2,200 games
    # (tools/first_turn_ab.py) put the player who went first at 54.0% +/- 2.1.
    sel = cg.Select(option=[cg.Option(cg.OptionType.YES), cg.Option(cg.OptionType.NO)],
                    context=cg.SelectContext.IS_FIRST, minCount=1, maxCount=1)
    out = main.agent({"current": _state(), "select": sel})
    _assert_legal(out, sel)
    assert out == [0]  # YES -> go first


def test_lethal_attack_is_taken():
    sel = cg.Select(option=[cg.Option(cg.OptionType.END),
                            cg.Option(cg.OptionType.ATTACK, attackId=102)],  # 120 dmg
                    minCount=1, maxCount=1)
    out = main.agent({"current": _state(opp_active_hp=100), "select": sel})
    _assert_legal(out, sel)
    assert out == [1]  # the KO attack, not END


def test_attack_preferred_over_end_when_nonzero():
    sel = cg.Select(option=[cg.Option(cg.OptionType.END),
                            cg.Option(cg.OptionType.ATTACK, attackId=101)],  # 30 dmg
                    minCount=1, maxCount=1)
    out = main.agent({"current": _state(opp_active_hp=200), "select": sel})
    assert out == [1]


def test_multi_select_respects_min_max():
    opts = [cg.Option(cg.OptionType.CARD, area=cg.AreaType.HAND, index=i) for i in range(5)]
    sel = cg.Select(option=opts, context=cg.SelectContext.DISCARD, minCount=2, maxCount=3)
    out = main.agent({"current": _state(), "select": sel})
    _assert_legal(out, sel)


def test_min_zero_allows_empty_when_nothing_scores():
    # END-type options with maxCount allowing zero: still legal whatever the agent picks.
    opts = [cg.Option(cg.OptionType.CARD, area=cg.AreaType.HAND, index=i) for i in range(3)]
    sel = cg.Select(option=opts, context=cg.SelectContext.DISCARD, minCount=0, maxCount=2)
    out = main.agent({"current": _state(), "select": sel})
    _assert_legal(out, sel)


# ── robustness: never raise, always legal ─────────────────────────────────────
def test_empty_options_does_not_crash():
    sel = cg.Select(option=[], minCount=0, maxCount=0)
    out = main.agent({"current": _state(), "select": sel})
    assert out == []


def test_malformed_dict_falls_back_legally():
    # missing 'current', odd select shape — must not raise.
    sel = cg.Select(option=[cg.Option(cg.OptionType.END)], minCount=1, maxCount=1)
    out = main.agent({"select": sel})
    assert isinstance(out, list)


def test_garbage_input_never_raises():
    for bad in [None, 42, "x", [], {}, {"select": {"minCount": 1, "option": [0, 0]}}]:
        out = main.agent(bad)
        assert isinstance(out, list)


def test_fuzz_random_prompts_always_legal():
    rng = random.Random(0)
    types = list(cg.OptionType)
    contexts = list(cg.SelectContext)
    areas = list(cg.AreaType)
    for _ in range(500):
        n = rng.randint(1, 8)
        opts = [cg.Option(rng.choice(types), index=rng.randint(0, 4),
                          area=rng.choice(areas), inPlayArea=rng.choice(areas),
                          inPlayIndex=rng.randint(-1, 4), attackId=rng.choice([None, 101, 102]),
                          playerIndex=rng.randint(0, 1), number=rng.randint(0, 9))
                for _ in range(n)]
        minc = rng.randint(0, n)
        maxc = rng.randint(minc, n)
        sel = cg.Select(option=opts, context=rng.choice(contexts), minCount=minc, maxCount=maxc)
        out = main.agent({"current": _state(rng.randint(10, 200), rng.randint(10, 200)),
                          "select": sel})
        _assert_legal(out, sel)
