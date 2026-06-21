"""Export a trained .pt net to a small .npz of weights for numpy-only deploy inference."""
import sys

import numpy as np
import torch

ck = torch.load(sys.argv[1], map_location="cpu")
np.savez(sys.argv[2], **{k: v.numpy() for k, v in ck["state"].items()})
print(f"exported {sys.argv[1]} -> {sys.argv[2]}")
