#!/usr/bin/env bash
# STAGE 2 — anchored self-play to SURPASS the frontier WITHOUT drifting from it.
# Fixes the drift that sank the old loop: (1) strong net-vs-net mirror opponents (not vanilla),
# (2) KL-anchor every train step toward the frozen BC/frontier net, (3) BC mixed in every cycle,
# (4) frontier-agreement logged each cycle as the gate. If agreement falls, raise KL.
#   cd ~/tempo && setsid bash scripts/az_anchored.sh 200 >/dev/null 2>&1 </dev/null & disown
cd "$(dirname "$0")/.."
N="${1:-200}"; W="${W:-14}"; KL="${KL:-0.5}"
DECK=data/decks/lucario_praxel.csv
BC=data/bc_lucario/records.jsonl
ANCHOR=net/lucario_best.pt
MPT=net/lucario_s2.pt; MNPZ=net/lucario_s2.npz
SP=data/selfplay_s2; CK=net/ckpt_s2
mkdir -p "$CK" "$SP"
[ -f "$MPT" ] || cp net/lucario_best.pt "$MPT"
[ -f "$MNPZ" ] || cp net/lucario_best.npz "$MNPZ"
for c in $(seq 1 "$N"); do
  ts=$(date +%H:%M:%S)
  timeout 600 ./scripts/run.sh -m train.selfplay_rust --pv "$MNPZ" --deck_a "$DECK" --deck_b "$DECK" \
    --games 200 --budget 0.4 --workers "$W" --out "$SP/records.jsonl" >> az_s2.log 2>&1
  tail -n 40000 "$SP/records.jsonl" > "$SP/r.tmp" 2>/dev/null && mv "$SP/r.tmp" "$SP/records.jsonl"
  timeout 400 ./scripts/run.sh -m train.train_net --bc "$BC" --selfplay "$SP/records.jsonl" \
    --init "$MPT" --anchor "$ANCHOR" --kl "$KL" --out "$MPT" --epochs 5 >> az_s2.log 2>&1
  ./scripts/run.sh -m train.export_npz "$MPT" "$MNPZ" >> az_s2.log 2>&1
  cp "$MNPZ" "$CK/model_s2_${c}.npz"
  fa=$(./scripts/run.sh -m tools.frontier_agreement --pv "$MNPZ" --bc "$BC" --n 1200 2>&1 | grep -oE '[0-9]+\.[0-9]+%' | head -1)
  echo "[$ts] s2-cycle $c done (KL=$KL); frontier-agreement$fa; selfplay=$(wc -l < "$SP/records.jsonl" 2>/dev/null)" >> az_s2_progress.log
done
echo "AZ-S2 DONE" >> az_s2_progress.log
