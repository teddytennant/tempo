"""Numpy-only policy+value inference for deployment (no torch in the Kaggle submission).

Mirrors model.PolicyValueNet's forward. Loads weights from the .npz exported by train/export_npz.py.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import featurize  # noqa: E402


def _relu(x):
    return np.maximum(x, 0.0)


def _softmax(x):
    x = x - x.max()
    e = np.exp(x)
    return e / e.sum()


class NetPVNumpy:
    def __init__(self, npz_path):
        d = np.load(npz_path)
        self.w = {k: d[k].astype(np.float32) for k in d.files}

    def _lin(self, x, p):
        return x @ self.w[p + ".weight"].T + self.w[p + ".bias"]

    def policy_value(self, obs):
        g, opts = featurize(obs)
        n = opts.shape[0]
        if n == 0:
            return [], 0.0
        G = _relu(self._lin(g, "g.0"))
        G = _relu(self._lin(G, "g.2"))                      # (128,)
        O = _relu(self._lin(opts, "o.0"))                   # (n,128)
        Gx = np.broadcast_to(G, (n, G.shape[0]))
        s = _relu(self._lin(np.concatenate([Gx, O], 1), "score.0"))
        s = self._lin(s, "score.2").squeeze(-1)             # (n,)
        v = _relu(self._lin(G, "val.0"))
        v = np.tanh(self._lin(v, "val.2"))                  # (1,)
        return _softmax(s).tolist(), float(v.reshape(-1)[0])

    __call__ = policy_value
