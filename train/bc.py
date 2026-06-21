"""Behavior-clone the field's expert decisions into the policy+value net.

Loads replay-derived records, featurizes once, trains a policy (cross-entropy over legal options,
imitating chosen moves, winners up-weighted) + value head (did this player win). Reports held-out
top-1 accuracy vs the random-pick baseline. Saves the net for MCTS integration.

Run: ./scripts/run.sh -m train.bc --epochs 30
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
from features import featurize, GLOBAL_DIM, OPT_DIM  # noqa: E402
from model import PolicyValueNet  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(records_path, maxn=60, limit=None):
    G, O, M, Y, V, W = [], [], [], [], [], []
    rnd_base = []
    for i, line in enumerate(open(records_path)):
        if limit and i >= limit:
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
        act = r["action"]
        label = act[0] if len(act) == 1 and 0 <= act[0] < n else -1  # policy: single-select only
        pad = np.zeros((maxn, OPT_DIM), np.float32)
        pad[:n] = opts
        mask = np.zeros(maxn, bool)
        mask[:n] = True
        G.append(g); O.append(pad); M.append(mask)
        Y.append(label); V.append(1.0 if r["won"] else -1.0)
        W.append(2.0 if r["won"] else 1.0)
        if label >= 0:
            rnd_base.append(1.0 / n)
    print(f"loaded {len(G)} records; policy examples={sum(1 for y in Y if y>=0)}; "
          f"random-pick baseline acc={np.mean(rnd_base):.3f}")
    return (torch.tensor(np.array(G)), torch.tensor(np.array(O)), torch.tensor(np.array(M)),
            torch.tensor(np.array(Y)), torch.tensor(np.array(V), dtype=torch.float32),
            torch.tensor(np.array(W), dtype=torch.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=os.path.join(_ROOT, "data", "bc", "records.jsonl"))
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--bs", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(_ROOT, "net", "bc_model.pt"))
    a = ap.parse_args()
    torch.manual_seed(0)

    G, O, M, Y, V, W = load(a.records, limit=a.limit)
    n = len(G)
    idx = torch.randperm(n)
    ntr = int(n * 0.9)
    tr, va = idx[:ntr], idx[ntr:]
    net = PolicyValueNet()
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)

    def batches(ix, shuffle=True):
        ix = ix[torch.randperm(len(ix))] if shuffle else ix
        for i in range(0, len(ix), a.bs):
            yield ix[i:i + a.bs]

    for ep in range(a.epochs):
        net.train()
        for b in batches(tr):
            s, v = net(G[b], O[b], M[b])
            ymask = Y[b] >= 0
            ploss = torch.tensor(0.0)
            if ymask.any():
                ce = F.cross_entropy(s[ymask], Y[b][ymask].clamp(min=0), reduction="none")
                ploss = (ce * W[b][ymask]).mean()
            vloss = F.mse_loss(v, V[b])
            loss = ploss + 0.5 * vloss
            opt.zero_grad(); loss.backward(); opt.step()
        if ep % 5 == 0 or ep == a.epochs - 1:
            net.eval()
            with torch.no_grad():
                correct = tot = 0
                vmse = 0.0; vc = 0
                for b in batches(va, shuffle=False):
                    s, v = net(G[b], O[b], M[b])
                    ymask = Y[b] >= 0
                    if ymask.any():
                        pred = s[ymask].argmax(1)
                        correct += (pred == Y[b][ymask]).sum().item()
                        tot += ymask.sum().item()
                    vmse += F.mse_loss(v, V[b], reduction="sum").item(); vc += len(b)
                acc = correct / max(1, tot)
                print(f"ep{ep:3d}  val top1-acc={acc:.3f}  val-value-mse={vmse/max(1,vc):.3f}")

    torch.save({"state": net.state_dict(), "gdim": GLOBAL_DIM, "odim": OPT_DIM}, a.out)
    print(f"saved -> {a.out}")


if __name__ == "__main__":
    main()
