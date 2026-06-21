"""Policy+value net: scores each legal option (policy prior) and estimates the game value.
Used as the MCTS PUCT prior + leaf value. Small enough for fast CPU inference."""
import torch
import torch.nn as nn

from features import GLOBAL_DIM, OPT_DIM


class PolicyValueNet(nn.Module):
    def __init__(self, gdim=GLOBAL_DIM, odim=OPT_DIM, h=128):
        super().__init__()
        self.g = nn.Sequential(nn.Linear(gdim, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU())
        self.o = nn.Sequential(nn.Linear(odim, h), nn.ReLU())
        self.score = nn.Sequential(nn.Linear(2 * h, h), nn.ReLU(), nn.Linear(h, 1))
        self.val = nn.Sequential(nn.Linear(h, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, g, opts, mask):
        # g:(B,gd)  opts:(B,N,od)  mask:(B,N) bool
        G = self.g(g)                                   # B,h
        O = self.o(opts)                                # B,N,h
        Gx = G.unsqueeze(1).expand(-1, O.size(1), -1)
        s = self.score(torch.cat([Gx, O], -1)).squeeze(-1)   # B,N
        s = s.masked_fill(~mask, -1e9)
        v = torch.tanh(self.val(G)).squeeze(-1)          # B
        return s, v
