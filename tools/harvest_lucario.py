"""Harvest expert Mega-Lucario play for BC: pull the top Lucario teams' games via the episode API,
keep only the Lucario-playing side's decisions. Bootstraps the Lucario net from frontier play.

  ./scripts/run.sh -m tools.harvest_lucario --per-team 30
"""
import argparse, json, os, sys, urllib.request, glob, subprocess
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT); sys.path.insert(0, os.path.join(_ROOT, "tools"))
from meta_from_replays import card_names, decks_and_winner, fp, label
from extract_bc import winner_of, valid

TOK = open(os.path.expanduser("~/.kaggle/access_token")).read().strip()
EPDIR = os.path.join(_ROOT, "data", "lucario_episodes")
OUT = os.path.join(_ROOT, "data", "bc_lucario", "records.jsonl")


def list_eps(sub):
    req = urllib.request.Request(
        "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes",
        data=json.dumps({"submissionId": sub}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOK})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=30))
        return [e["id"] for e in r.get("episodes", [])]
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--per-team", type=int, default=30); a = ap.parse_args()
    os.makedirs(EPDIR, exist_ok=True); os.makedirs(os.path.dirname(OUT), exist_ok=True)
    import pickle
    d = pickle.load(open("/tmp/topteams.pkl", "rb"))
    # teams whose extracted deck was Mega Lucario (by name, from the deck-attribution step)
    lucario_names = {"Praxel", "MEP", "LORD DREGS", "Pik-AI-chu", "tototo", "patamaru", "Aki Ogawa", "Kengo Yoko"}
    subs = [d["sub"][t] for t in d["elo"] if d["name"][t] in lucario_names and d["sub"].get(t)]
    print(f"lucario team submissions: {subs}")
    eps = []
    for s in subs:
        eps += list_eps(s)[:a.per_team]
    eps = sorted(set(eps))
    print(f"downloading {len(eps)} candidate replays...")
    kag = os.path.expanduser("~/.local/bin/kaggle")
    for ep in eps:
        f = os.path.join(EPDIR, f"episode-{ep}-replay.json")
        if not os.path.exists(f):
            subprocess.run([kag, "competitions", "replay", str(ep)], cwd=EPDIR,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    names = card_names()
    n_games = n_rec = 0
    with open(OUT, "w") as out:
        for f in glob.glob(os.path.join(EPDIR, "*replay*.json")):
            try:
                rep = json.load(open(f))
            except Exception:
                continue
            decks, _ = decks_and_winner(rep)
            luc = [ai for ai in decks if label(fp(decks[ai]), names) == "Mega Lucario ex"]
            if not luc:
                continue
            w = winner_of(rep); steps = rep.get("steps", []); used = False
            for i in range(len(steps) - 1):
                for ai in luc:
                    if ai >= len(steps[i]):
                        continue
                    e = steps[i][ai]
                    if e.get("status") != "ACTIVE":
                        continue
                    o = e.get("observation") or {}
                    sel = o.get("select")
                    if not isinstance(sel, dict) or o.get("current") is None:
                        continue
                    nxt = steps[i + 1][ai] if ai < len(steps[i + 1]) else {}
                    act = nxt.get("action")
                    if not valid(act, sel):
                        continue
                    out.write(json.dumps({"obs": o, "action": act, "won": (w == ai),
                                          "context": sel.get("context")}) + "\n")
                    n_rec += 1; used = True
            if used:
                n_games += 1
    print(f"lucario BC: {n_games} games, {n_rec} records -> {OUT}")


if __name__ == "__main__":
    main()
