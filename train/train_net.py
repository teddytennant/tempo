"""Train the policy+value net on BC (expert moves) + self-play (MCTS visit-count) targets.

Policy loss = soft cross-entropy to the target distribution (one-hot for BC actions, visit-count
for self-play). Value loss = MSE to game outcome (+1 win / -1 loss). Warm-starts from --init for the
AlphaZero gen->train loop.

Run: ./scripts/run.sh -m train.train_net --bc data/bc/records.jsonl \
        --selfplay data/selfplay/records.jsonl --init net/model.pt --out net/model.pt --epochs 8
"""
import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "net"))
from cg.api import to_observation_class  # noqa: E402
from features import featurize, OPT_DIM  # noqa: E402
from model import PolicyValueNet  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_files(paths, maxn=60, cap=None):
    G, O, M, T, V, W = [], [], [], [], [], []
    for path in paths:
        if not path or not os.path.exists(path):
            continue
        for i, line in enumerate(open(path)):
            if cap and i >= cap:
                break
            r = json.loads(line)
            obs = to_observation_class(r["obs"])
            try:
                g, opts = featurize(obs)
            except Exception:
                continue
            n = opts.shape[0]
            if n == 0 or n > maxn:
                continue
            tgt = np.zeros(maxn, np.float32)
            if "policy" in r and len(r["policy"]) == n:
                tgt[:n] = r["policy"]
                w = 1.0
            else:
                act = r.get("action", [])
                if len(act) != 1 or not (0 <= act[0] < n):
                    continue
                tgt[act[0]] = 1.0
                w = 2.0 if r.get("won") else 1.0
            if tgt.sum() <= 0:
                continue
            pad = np.zeros((maxn, OPT_DIM), np.float32); pad[:n] = opts
            mask = np.zeros(maxn, bool); mask[:n] = True
            G.append(g); O.append(pad); M.append(mask); T.append(tgt)
            V.append(1.0 if r.get("won") else -1.0); W.append(w)
    print(f"loaded {len(G)} examples from {paths}")
    t = lambda x, d=None: torch.tensor(np.array(x), dtype=d) if d else torch.tensor(np.array(x))
    return (t(G), t(O), t(M), t(T, torch.float32), t(V, torch.float32), t(W, torch.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bc", default=os.path.join(_ROOT, "data/bc/records.jsonl"))
    ap.add_argument("--selfplay", default=os.path.join(_ROOT, "data/selfplay/records.jsonl"))
    ap.add_argument("--init", default=None)
    ap.add_argument("--out", default=os.path.join(_ROOT, "net", "model.pt"))
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--anchor", default=None, help="frozen BC net to KL-anchor toward (prevents self-play drift)")
    ap.add_argument("--kl", type=float, default=0.0, help="KL-anchor strength (beta)")
    a = ap.parse_args()
    torch.manual_seed(0)

    G, O, M, T, V, W = load_files([a.bc, a.selfplay])
    n = len(G)
    if n == 0:
        print("no data"); return
    idx = torch.randperm(n); ntr = int(n * 0.92)
    tr, va = idx[:ntr], idx[ntr:]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device:", dev)
    net = PolicyValueNet().to(dev)
    if a.init and os.path.exists(a.init):
        net.load_state_dict(torch.load(a.init, map_location=dev)["state"])
        print("warm-started from", a.init)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    anchor = None
    if a.anchor and os.path.exists(a.anchor) and a.kl > 0:
        anchor = PolicyValueNet().to(dev)
        anchor.load_state_dict(torch.load(a.anchor, map_location=dev)["state"])
        anchor.eval()
        print(f"KL-anchored to {a.anchor} (beta={a.kl})")

    def go(ix, train):
        ix = ix[torch.randperm(len(ix))] if train else ix
        tot_c = tot = 0
        for i in range(0, len(ix), a.bs):
            b = ix[i:i + a.bs]
            gb, ob, mb, tb, vb, wb = G[b].to(dev), O[b].to(dev), M[b].to(dev), T[b].to(dev), V[b].to(dev), W[b].to(dev)
            s, v = net(gb, ob, mb)
            logp = torch.log_softmax(s.masked_fill(~mb, -1e9), dim=1)
            ploss = -(tb * logp).sum(1)
            ploss = (ploss * wb).mean()
            vloss = F.mse_loss(v, vb)
            loss = ploss + 0.5 * vloss
            if anchor is not None:
                with torch.no_grad():
                    sa, _ = anchor(gb, ob, mb)
                    pa = torch.softmax(sa.masked_fill(~mb, -1e9), dim=1)
                loss = loss + a.kl * (-(pa * logp).sum(1)).mean()  # distill toward frozen BC
            if train:
                opt.zero_grad(); loss.backward(); opt.step()
            else:
                pred = s.masked_fill(~mb, -1e9).argmax(1)
                tgt = tb.argmax(1)
                tot_c += (pred == tgt).sum().item(); tot += len(b)
        return tot_c / max(1, tot)

    for ep in range(a.epochs):
        net.train(); go(tr, True)
        if ep % 2 == 0 or ep == a.epochs - 1:
            net.eval()
            with torch.no_grad():
                acc = go(va, False)
            print(f"ep{ep:3d}  val top1-match={acc:.3f}")
    from features import GLOBAL_DIM
    torch.save({"state": net.state_dict(), "gdim": GLOBAL_DIM, "odim": OPT_DIM}, a.out)
    print(f"saved -> {a.out}")


if __name__ == "__main__":
    main()
