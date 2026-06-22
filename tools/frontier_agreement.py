"""Frontier-agreement: how often does our net's top move match what the 1300+ frontier players
actually played? Measured on real top-team replays — a far better strength proxy than self-play
win-rate (which we proved doesn't transfer to the ladder). Compare AZ net vs BC net vs random:
if AZ agrees with the frontier MORE than BC, self-play moved us toward strong play; if less, it drifted.

  ./scripts/run.sh -m tools.frontier_agreement --pv net/lucario.npz --bc data/bc_lucario/records.jsonl
"""
import argparse, json, os, sys, random
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pv", required=True)
    ap.add_argument("--bc", default=os.path.join(_ROOT, "data/bc_lucario/records.jsonl"))
    ap.add_argument("--n", type=int, default=1500)
    a = ap.parse_args()
    import engine_rs
    engine_rs.init(os.path.abspath(os.path.join(_ROOT, "cg", "libcg.so")))
    engine_rs.init_net(os.path.abspath(a.pv))
    recs = [json.loads(l) for l in open(a.bc)]
    random.seed(0); random.shuffle(recs)
    recs = recs[:a.n]
    match = total = rand_match = 0
    for r in recs:
        obs = r["obs"]; act = r.get("action")
        sel = obs.get("select")
        if not isinstance(sel, dict) or obs.get("current") is None:
            continue
        nopt = len(sel.get("option") or [])
        if nopt < 2 or not (isinstance(act, list) and act):
            continue
        try:
            priors, _ = engine_rs.policy_value_debug(json.dumps(obs))
        except Exception:
            continue
        if not priors or len(priors) != nopt:
            continue
        top = max(range(nopt), key=lambda i: priors[i])
        total += 1
        if top == act[0]:
            match += 1
        rand_match += 1.0 / nopt  # expected agreement of a random policy
    if total:
        print(f"frontier-agreement of {os.path.basename(a.pv)}: {match}/{total} = {match/total:.1%}"
              f"  (random baseline {rand_match/total:.1%})")
    else:
        print("no usable records")


if __name__ == "__main__":
    main()
