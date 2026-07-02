#!/usr/bin/env bash
# Featurize the multi-day corpus, train the bc_top2 policy, export deploy weights.
set -euo pipefail
cd /home/gradient/projects/ai/tempo
echo "$(date -u +%H:%M:%S) featurize..."
./scripts/run.sh train/bc_top2.py featurize --workers 12
echo "$(date -u +%H:%M:%S) train..."
./scripts/run.sh train/bc_top2.py train --epochs 15 --hidden 256 --out net/bc_top2.pt
echo "$(date -u +%H:%M:%S) export..."
./scripts/run.sh train/export_npz.py net/bc_top2.pt net/bc_top2.npz
echo "$(date -u +%H:%M:%S) PIPELINE DONE"
