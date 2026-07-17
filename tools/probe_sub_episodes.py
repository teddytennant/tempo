"""Identify what agent/deck a Kaggle submission is, from its public ladder episodes.

Usage:
  ./scripts/run.sh tools/probe_sub_episodes.py --sub 54290398 --cache /tmp/eps_54290398 [--max-replays 25]

POSTs to the anonymous ListEpisodes endpoint, then fetches replay JSONs from
kaggleusercontent, extracts our seat's decklist (steps[1] action, see
tools/extract_decklists.py precedent), W/L by opponent deck archetype, and a
recent-vs-older win-rate split to gauge score stability.
"""
import argparse
import json
import os
import ssl
import sys
import urllib.request
from collections import Counter, defaultdict

UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
CTX = ssl.create_default_context()


def post_list_episodes(sub_id):
    req = urllib.request.Request(
        "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
        data=json.dumps({"submissionId": sub_id}).encode(),
        headers=UA, method="POST")
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return json.load(r)


def fetch_replay(ep_id, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    p = os.path.join(cache_dir, f"{ep_id}.json")
    if os.path.exists(p):
        return json.load(open(p))
    url = f"https://www.kaggleusercontent.com/episodes/{ep_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        data = r.read()
    with open(p, "wb") as f:
        f.write(data)
    return json.loads(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", type=int, required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--max-replays", type=int, default=30)
    ap.add_argument("--dump-raw", action="store_true")
    a = ap.parse_args()

    resp = post_list_episodes(a.sub)
    if a.dump_raw:
        print(json.dumps(resp, indent=2)[:8000])
        return
    eps = resp.get("episodes") or []
    print(f"sub {a.sub}: {len(eps)} episodes listed", file=sys.stderr)

    # Which seat/agent belongs to this submission in each episode
    rows = []
    for ep in eps:
        ep_id = ep.get("id")
        agents = ep.get("agents") or []
        seat = None
        my_score = None
        my_rew = None
        opp_sub = None
        for i, ag in enumerate(agents):
            if ag.get("submissionId") == a.sub:
                seat = ag.get("index", i)
                my_score = ag.get("updatedScore")
                my_rew = ag.get("reward")
            else:
                opp_sub = ag.get("submissionId")
        if seat is None:
            continue
        rows.append({"id": ep_id, "seat": seat, "endTime": ep.get("endTime"),
                     "createTime": ep.get("createTime"), "score": my_score,
                     "reward": my_rew, "opp_sub": opp_sub, "agents": agents})
    rows.sort(key=lambda r: str(r.get("endTime") or r.get("createTime") or ""))
    print(f"episodes with our seat resolved: {len(rows)}", file=sys.stderr)

    # score trajectory (updatedScore over time)
    traj = [(r["endTime"], r["score"]) for r in rows if r.get("score") is not None]
    if traj:
        print("score trajectory (first 3 / last 6):")
        for t, s in traj[:3]:
            print(f"  {t} -> {s:.1f}")
        print("  ...")
        for t, s in traj[-6:]:
            print(f"  {t} -> {s:.1f}")

    # Overall W/L from episode metadata (all listed episodes), plus recent split
    def wl(rs):
        w = sum(1 for r in rs if r.get("reward") == 1)
        l = sum(1 for r in rs if r.get("reward") == -1)
        return w, l, len(rs) - w - l
    W, L, T = wl(rows)
    print(f"\nALL {len(rows)} episodes: W={W} L={L} T={T} ({W/max(1,W+L)*100:.0f}% of decided)")
    for label, chunk in (("last 20", rows[-20:]), ("prior 20", rows[-40:-20]),
                         ("older 40", rows[-80:-40])):
        if chunk:
            w, l, t = wl(chunk)
            print(f"  {label}: W={w} L={l} T={t} ({w/max(1,w+l)*100:.0f}%)")

    # Fetch newest N replays for deck + W/L
    take = rows[-a.max_replays:]
    my_deck_counts = Counter()
    wl_by_opp_deck = defaultdict(lambda: [0, 0])  # deck-sig -> [w, l]
    wins = losses = ties = 0
    for r in take:
        try:
            rep = fetch_replay(r["id"], a.cache)
        except Exception as e:
            print(f"  fetch {r['id']} failed: {e}", file=sys.stderr)
            continue
        seat = r["seat"]
        opp = 1 - seat
        try:
            my_act = rep["steps"][1][seat].get("action")
            opp_act = rep["steps"][1][opp].get("action")
        except Exception:
            continue
        if isinstance(my_act, list) and len(my_act) == 60:
            my_deck_counts[tuple(sorted(my_act))] += 1
        rew = rep.get("rewards") or [None, None]
        mine = rew[seat] if rew[seat] is not None else -1
        theirs = rew[opp] if rew[opp] is not None else -1
        sig = tuple(sorted(opp_act)) if isinstance(opp_act, list) else ("?",)
        if mine > theirs:
            wins += 1; wl_by_opp_deck[sig][0] += 1
        elif mine < theirs:
            losses += 1; wl_by_opp_deck[sig][1] += 1
        else:
            ties += 1

    print(f"\nrecent {len(take)} episodes: W={wins} L={losses} T={ties}")
    print(f"distinct decklists we played: {len(my_deck_counts)}")
    for deck, cnt in my_deck_counts.most_common(3):
        print(f"  deck used {cnt}x, ids sample: {sorted(set(deck))[:10]} ... total distinct ids {len(set(deck))}")
        out = f"{a.cache}/sub_{a.sub}_deck_{cnt}.csv"
        # persist unsorted-modal? we only have sorted sig; store sorted (composition identical)
        with open(out, "w") as f:
            f.write("\n".join(str(c) for c in deck) + "\n")
        print(f"  -> wrote composition to {out}")

    print("\nW/L by opponent deck signature (top 10 by games):")
    for sig, (w, l) in sorted(wl_by_opp_deck.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))[:10]:
        print(f"  opp-sig-hash {hash(sig) & 0xffffffff:08x} n={w+l} W{w}-L{l}")


if __name__ == "__main__":
    main()
