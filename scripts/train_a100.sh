#!/usr/bin/env bash
# Unattended AlphaZero training for tempo on an A100 box (Colab/cloud). No interactivity.
# Self-play (CPU cores) -> train policy/value net on the GPU -> checkpoint model.npz -> repeat.
# Bootstraps everything: clones the repo, downloads the cg engine, harvests a little BC data.
#
# LAUNCH:
#   export KAGGLE_TOKEN="KGAT_xxx"           # Kaggle API token (Settings -> API)
#   export GIT_TOKEN="ghp_xxx"               # GitHub PAT with read access to teddytennant/tempo
#   export HOURS=6                           # wall-clock budget (default 6)
#   bash train_a100.sh
# RETRIEVE: net/ckpt/model_cN.npz  (copy the latest back; bundle with BUNDLE_NET=1)
set -uo pipefail
HOURS=${HOURS:-6}
WORKERS=${WORKERS:-$(nproc)}
LOG=a100_train.log

[ -d tempo ] || git clone "https://${GIT_TOKEN}@github.com/teddytennant/tempo.git"
cd tempo
exec >>"$LOG" 2>&1
echo "=== START $(date) HOURS=$HOURS WORKERS=$WORKERS ==="

python -m pip -q install kaggle numpy >/dev/null 2>&1 || pip install -q kaggle numpy
python - <<'PY'
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
PY

mkdir -p ~/.kaggle cg data/raw data/episodes data/bc data/selfplay net/ckpt
printf '%s' "$KAGGLE_TOKEN" > ~/.kaggle/access_token; chmod 600 ~/.kaggle/access_token
KG="python -m kaggle"

# 1. cg engine + card data (the repo gitignores these — download from the competition)
echo "--- downloading engine ---"
( cd cg
  for f in __init__.py api.py sim.py game.py utils.py libcg.so; do
    $KG competitions download pokemon-tcg-ai-battle -f "sample_submission/cg/$f" -q
  done
  for z in *.zip; do [ -e "$z" ] && unzip -oq "$z"; done; rm -f *.zip )
$KG competitions download pokemon-tcg-ai-battle -f EN_Card_Data.csv -p data/raw -q
( cd data/raw; for z in *.zip; do [ -e "$z" ] && unzip -oq "$z"; done; rm -f *.zip )

# 2. bootstrap BC data from a few real replays (optional but helps the value head)
echo "--- harvesting replays for BC ---"
( cd data/episodes
  for s in 53915967 53915585 53903200; do
    for id in $($KG competitions episodes "$s" 2>/dev/null | awk '{print $1}' | grep -E '^[0-9]+$' | head -40); do
      [ -f "episode-$id-replay.json" ] || $KG competitions replay "$id" >/dev/null 2>&1
    done
  done )
python -m tools.extract_bc || true

# 3. AlphaZero loop until the time budget runs out (GPU training)
echo "--- AZ loop ---"
END=$(( $(date +%s) + HOURS*3600 ))
c=0
[ -f net/model.pt ] || cp net/bc_model.pt net/model.pt 2>/dev/null || true
while [ "$(date +%s)" -lt "$END" ]; do
  c=$((c+1))
  python -m train.selfplay_gen --games 160 --iters 60 --workers "$WORKERS"
  tail -n 120000 data/selfplay/records.jsonl > data/selfplay/r.tmp 2>/dev/null && mv data/selfplay/r.tmp data/selfplay/records.jsonl
  python -m train.train_net --init net/model.pt --out net/model.pt --epochs 6
  python -m train.export_npz net/model.pt "net/ckpt/model_c${c}.npz"
  cp "net/ckpt/model_c${c}.npz" net/ckpt/latest.npz
  echo "[$(date)] cycle $c done; selfplay=$(wc -l < data/selfplay/records.jsonl)"
done
echo "=== DONE $(date) — latest net: net/ckpt/latest.npz ==="
