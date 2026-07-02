"""Scaled top-player behavior cloning: streaming featurizer + weighted trainer.

Two passes so a ~1M-record multi-day corpus trains within 14G RAM:
  featurize: data/bc_top/records_*.jsonl -> disk memmaps (G f32, O f16 padded to 60, Y i32,
             W f32 teacher-score weight, DAY u16). Multiprocess featurization, single writer.
  train:     stream batches off the memmaps; policy-only (the winners-only corpus makes the
             value head degenerate — deploy uses the policy head alone). Validation = the
             newest day held out entirely (honest generalization to the current meta, no
             same-game leakage). Saves the best-val checkpoint.

Run from repo root:
  python3 train/bc_top2.py featurize
  python3 train/bc_top2.py train --epochs 15 --out net/bc_top2.pt
"""
import argparse
import csv
import glob
import json
import multiprocessing as mp
import os
import re
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "net"))

MAXN = 60
FEAT_DIR = os.path.join(_ROOT, "data", "bc_top", "feat")


# ── teacher weights ──────────────────────────────────────────────────────────
def team_scores():
    paths = sorted(glob.glob(os.path.join(_ROOT, "data", "lb_now", "*publicleaderboard*.csv")))
    scores = {}
    if paths:
        with open(paths[-1], newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    scores[row["TeamName"].strip()] = float(row["Score"])
                except (KeyError, ValueError, TypeError):
                    continue
    return scores


def weight_for(score):
    # 1050 -> 1.0, 1100 -> 1.5, 1213 (current #1) -> 2.6; floor 0.5 for unknown/stale teams
    return float(np.clip(0.5 + max(0.0, score - 1000.0) / 100.0, 0.5, 3.0))


# ── featurize pass ───────────────────────────────────────────────────────────
def _work(line):
    from cg.api import to_observation_class
    from features import featurize
    try:
        r = json.loads(line)
        act = r.get("action")
        if not (isinstance(act, list) and len(act) == 1):
            return None  # policy trains on single-select decisions
        obs = to_observation_class(r["obs"])
        g, opts = featurize(obs)
        n = opts.shape[0]
        if n == 0 or n > MAXN or not (0 <= act[0] < n):
            return None
        return g.astype(np.float32).tobytes(), opts.astype(np.float16).tobytes(), n, act[0], r.get("team", "?")
    except Exception:
        return None


def featurize_cmd(a):
    from features import GLOBAL_DIM, OPT_DIM  # noqa: F401 (dims for allocation)
    files = sorted(glob.glob(os.path.join(_ROOT, "data", "bc_top", "records_*.jsonl")))
    if not files:
        sys.exit("no records_*.jsonl found")
    scores = team_scores()
    total = 0
    for f in files:
        total += sum(1 for _ in open(f))
    print(f"files={len(files)} lines={total}", flush=True)
    os.makedirs(FEAT_DIR, exist_ok=True)
    G = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "G.npy"), "w+", np.float32, (total, GLOBAL_DIM))
    O = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "O.npy"), "w+", np.float16, (total, MAXN, OPT_DIM))
    NOPT = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "N.npy"), "w+", np.int16, (total,))
    Y = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "Y.npy"), "w+", np.int32, (total,))
    W = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "W.npy"), "w+", np.float32, (total,))
    DAY = np.lib.format.open_memmap(os.path.join(FEAT_DIR, "DAY.npy"), "w+", np.uint16, (total,))
    k = 0
    team_w = {}
    with mp.Pool(a.workers) as pool:
        for f in files:
            m = re.search(r"records_(\d+)\.jsonl", f)
            day = int(m.group(1)) if m else 0
            done_before = k
            for res in pool.imap_unordered(_work, open(f), chunksize=64):
                if res is None:
                    continue
                gb, ob, n, y, team = res
                if team not in team_w:
                    team_w[team] = weight_for(scores.get(team, 0.0))
                G[k] = np.frombuffer(gb, np.float32)
                o = np.frombuffer(ob, np.float16).reshape(n, OPT_DIM)
                O[k, :n] = o
                NOPT[k] = n
                Y[k] = y
                W[k] = team_w[team]
                DAY[k] = day
                k += 1
            print(f"{os.path.basename(f)}: +{k - done_before} (total {k})", flush=True)
    json.dump({"count": k, "gdim": int(GLOBAL_DIM), "odim": int(OPT_DIM), "maxn": MAXN},
              open(os.path.join(FEAT_DIR, "meta.json"), "w"))
    print(f"featurized {k}/{total} -> {FEAT_DIR}", flush=True)


# ── train pass ───────────────────────────────────────────────────────────────
def train_cmd(a):
    import torch
    import torch.nn.functional as F
    from model import PolicyValueNet
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)

    meta = json.load(open(os.path.join(FEAT_DIR, "meta.json")))
    n = meta["count"]
    G = np.load(os.path.join(FEAT_DIR, "G.npy"), mmap_mode="r")
    O = np.load(os.path.join(FEAT_DIR, "O.npy"), mmap_mode="r")
    NOPT = np.load(os.path.join(FEAT_DIR, "N.npy"), mmap_mode="r")[:n]
    Y = np.load(os.path.join(FEAT_DIR, "Y.npy"), mmap_mode="r")[:n]
    W = np.load(os.path.join(FEAT_DIR, "W.npy"), mmap_mode="r")[:n]
    DAY = np.load(os.path.join(FEAT_DIR, "DAY.npy"), mmap_mode="r")[:n]

    if a.min_weight > 0:
        keep = W >= a.min_weight
    else:
        keep = np.ones(n, bool)
    days = np.unique(DAY)
    val_day = days.max()
    tr_idx = np.where(keep & (DAY != val_day))[0]
    va_idx = np.where(keep & (DAY == val_day))[0]
    rnd = float(np.mean(1.0 / NOPT[va_idx])) if len(va_idx) else 0.0
    print(f"train={len(tr_idx)} val={len(va_idx)} (val day={val_day})  random-baseline={rnd:.3f}", flush=True)

    net = PolicyValueNet(gdim=meta["gdim"], odim=meta["odim"], h=a.hidden)
    opt = torch.optim.Adam(net.parameters(), lr=a.lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs, eta_min=a.lr * 0.1)

    def fetch(ix):
        ix = np.sort(ix)
        g = torch.from_numpy(np.asarray(G[ix], np.float32))
        o = torch.from_numpy(np.asarray(O[ix], np.float32))
        nn_ = np.asarray(NOPT[ix])
        m = torch.from_numpy(np.arange(MAXN)[None, :] < nn_[:, None])
        y = torch.from_numpy(np.asarray(Y[ix], np.int64))
        w = torch.from_numpy(np.asarray(W[ix], np.float32))
        return g, o, m, y, w

    def evaluate():
        net.eval()
        correct = tot = 0
        with torch.no_grad():
            for i in range(0, len(va_idx), a.bs):
                g, o, m, y, _ = fetch(va_idx[i:i + a.bs])
                s, _v = net(g, o, m)
                correct += (s.argmax(1) == y).sum().item()
                tot += len(y)
        return correct / max(1, tot)

    best = 0.0
    rng = np.random.default_rng(0)
    for ep in range(a.epochs):
        net.train()
        perm = rng.permutation(tr_idx)
        for i in range(0, len(perm), a.bs):
            g, o, m, y, w = fetch(perm[i:i + a.bs])
            s, _v = net(g, o, m)
            ce = F.cross_entropy(s, y, reduction="none")
            loss = (ce * w).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()
        acc = evaluate()
        flag = ""
        if acc > best:
            best = acc
            import torch as _t
            _t.save({"state": net.state_dict(), "gdim": meta["gdim"], "odim": meta["odim"], "h": a.hidden}, a.out)
            flag = "  *saved*"
        print(f"ep{ep:3d}  val top1-acc={acc:.4f}  (best {best:.4f}){flag}", flush=True)
    print(f"done; best val acc={best:.4f} -> {a.out}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("featurize")
    f.add_argument("--workers", type=int, default=12)
    t = sub.add_parser("train")
    t.add_argument("--epochs", type=int, default=15)
    t.add_argument("--bs", type=int, default=1024)
    t.add_argument("--lr", type=float, default=2e-3)
    t.add_argument("--hidden", type=int, default=256)
    t.add_argument("--threads", type=int, default=14)
    t.add_argument("--min-weight", type=float, default=0.0, help="drop teachers below this weight")
    t.add_argument("--out", default=os.path.join(_ROOT, "net", "bc_top2.pt"))
    a = ap.parse_args()
    if a.cmd == "featurize":
        featurize_cmd(a)
    else:
        train_cmd(a)


if __name__ == "__main__":
    main()
