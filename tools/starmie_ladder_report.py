"""Ladder-episode report for a Starmie submission: W/L by opponent archetype + loss replays.

The ONLY place we can see our agent's real losses against the real field (the winners-only elite
corpus can't show losses). Method (validated 2026-07-17 on v10 = submission 54784159):

  1. POST https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes
     with body {"submissionId": <id>} (anonymous, content-type application/json)
     -> episodes with per-agent submissionId / reward / updatedScore.
  2. GET  https://www.kaggleusercontent.com/episodes/<episodeId>.json (follow redirects)
     -> full replay; steps[1][i].action is agent i's 60-card decklist (extract_decklists.py).
  3. Cluster opponents by their distinctive Pokémon (meta_from_replays-style label), tally W/L,
     and write loss replays to --out-dir for narration (scratchpad narrate_replay.py precedent:
     walk OUR seat's obs['logs'] stream deduped on obs['step'], LogType 2/10/11/12/15/16).

Usage:
  ./scripts/run.sh tools/starmie_ladder_report.py --submission 54784159 --out-dir data/episodes/v10
"""
import argparse
import collections
import csv
import json
import os
import subprocess

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def card_names():
    m = {}
    with open(os.path.join(_ROOT, "data", "raw", "EN_Card_Data.csv"), newline="") as f:
        for row in csv.DictReader(f):
            cid = row["Card ID"].strip()
            if cid.isdigit() and int(cid) not in m:
                m[int(cid)] = (row["Card Name"].strip(),
                               row["Stage (Pokémon)/Type (Energy and Trainer)"].strip())
    return m


# curl, not urllib: the uv-managed python in .venv has no CA bundle on this NixOS box
# (urllib -> CERTIFICATE_VERIFY_FAILED); the system curl trusts the system store.
def list_episodes(submission_id):
    out = subprocess.run(
        ["curl", "-s", "--max-time", "60", "-X", "POST",
         "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
         "-H", "content-type: application/json",
         "-d", json.dumps({"submissionId": submission_id})],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out).get("episodes", [])


def fetch_replay(episode_id):
    out = subprocess.run(
        ["curl", "-sL", "--max-time", "120",
         f"https://www.kaggleusercontent.com/episodes/{episode_id}.json"],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def deck_label(deck, names):
    """Name a deck by its most-played distinctive Pokémon (ex / Mega first)."""
    cnt = collections.Counter(deck)
    poke = [(names[cid][0], c) for cid, c in cnt.most_common()
            if cid in names and "Pokémon" in names[cid][1]]
    big = [n for n, _ in poke if "ex" in n or "Mega" in n]
    key = big[:2] or [n for n, _ in poke[:2]]
    return " / ".join(key) if key else "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", type=int, required=True)
    ap.add_argument("--out-dir", default=None, help="write LOSS replays here for narration")
    a = ap.parse_args()

    names = card_names()
    eps = list_episodes(a.submission)
    print(f"submission {a.submission}: {len(eps)} episodes listed")
    tally = collections.defaultdict(lambda: [0, 0])   # archetype -> [W, L]
    losses = []
    for e in eps:
        agents = e.get("agents", [])
        subs = [ag.get("submissionId") for ag in agents]
        if subs.count(a.submission) != 1:
            print(f"  ep {e['id']}: self-play validation episode, skipped")
            continue
        our = subs.index(a.submission)
        reward = agents[our].get("reward")
        rep = fetch_replay(e["id"])
        opp = 1 - our
        deck = rep["steps"][1][opp].get("action") or rep["steps"][0][opp].get("action")
        label = deck_label(deck, names) if isinstance(deck, list) and len(deck) == 60 else "unknown"
        res = "W" if reward == 1 else "L" if reward == -1 else "T"
        tally[label][0 if res == "W" else 1] += res != "T"
        opp_team = rep["info"]["TeamNames"][opp]
        print(f"  ep {e['id']}: {res} vs {opp_team!r} [{label}] "
              f"(our seat {our}, score {agents[our].get('updatedScore', 0):.1f})")
        if res == "L" and a.out_dir:
            os.makedirs(a.out_dir, exist_ok=True)
            out = os.path.join(a.out_dir, f"loss_ep_{e['id']}_seat{our}.json")
            with open(out, "w") as f:
                json.dump(rep, f)
            losses.append(out)

    print("\nW/L by opponent archetype:")
    for label, (w, l) in sorted(tally.items(), key=lambda kv: -(kv[1][0] + kv[1][1])):
        print(f"  {label:45s} W={w} L={l}")
    if losses:
        print("\nloss replays saved (narrate with scratchpad narrate_replay.py):")
        for p in losses:
            print(f"  {p}")


if __name__ == "__main__":
    main()
