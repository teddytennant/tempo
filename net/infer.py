"""Policy+value inference for MCTS: featurize an Observation -> (priors over options, value).

Torch version for local development/validation. A numpy-only deploy version (no torch in the
submission) comes once the net is locked.
"""
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import featurize  # noqa: E402
from model import PolicyValueNet  # noqa: E402


class NetPV:
    def __init__(self, path):
        ck = torch.load(path, map_location="cpu")
        self.net = PolicyValueNet()
        self.net.load_state_dict(ck["state"])
        self.net.eval()

    @torch.no_grad()
    def policy_value(self, obs):
        g, opts = featurize(obs)
        n = opts.shape[0]
        if n == 0:
            return [], 0.0
        G = torch.from_numpy(g).unsqueeze(0)
        O = torch.from_numpy(opts).unsqueeze(0)
        M = torch.ones(1, n, dtype=torch.bool)
        s, v = self.net(G, O, M)
        p = torch.softmax(s[0], 0).numpy()
        return p.tolist(), float(v.item())

    __call__ = policy_value
