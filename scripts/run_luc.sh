#!/usr/bin/env bash
# Launcher for the diverse-field Lucario AZ loop (keeps env in one place for reliable detached start).
cd "$(dirname "$0")/.."
export DECK=data/decks/lucario_praxel.csv
export OPPS=data/decks/lucario_praxel.csv,data/decks/abomasnow.csv,data/decks/dunsparce.csv,data/decks/fezandipiti.csv,data/decks/dragapult.csv
export BC=data/bc_lucario/records.jsonl
export MPT=net/lucario.pt
export MNPZ=net/lucario.npz
export SP=data/selfplay_lucario
export CK=net/ckpt_lucario
export TAG=luc
export W=14
exec bash scripts/az_rust_loop.sh 400
