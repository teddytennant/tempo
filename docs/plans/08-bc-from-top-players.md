# BC-from-Top-Players — the only path with a #1 ceiling

Cloning the whole field teaches the ~600-Elo average. To contend with keidroid (1367) we must
imitate ONLY the best. This is the underexplored lever (the team's RL self-play trained on a weak
deck; the existing BC net was never deployed). Status as of 2026-06-24:

## Pipeline (tooling validated, data step pending)
1. **Data source — official daily episode datasets.** Kaggle publishes every ladder game daily as
   `kaggle/pokemon-tcg-ai-battle-episodes-2026-06-DD` (~750 MB/day, thousands of games) + an
   `...-episodes-index`. Download N recent days (`kaggle datasets download`).
2. **Filter to teachers.** `tools/extract_bc_top.py` — keeps only winning decisions by teams with
   public score ≥ --min-score (default 1150 = 32 teams incl. keidroid/tomatomato/Kadoraba). Pass
   `--leaderboard <csv>` to refresh the teacher set; falls back to a baked-in 2026-06-24 list.
   VALIDATED: 440 clean records (0 dropped) from 6 top-team wins in `data/top_episodes/`.
3. **Train.** `train/bc.py --records data/bc_top/records.jsonl --out net/bc_top.pt` (Transformer
   value+policy per `net/model.py`). Run on the idle remote box (nixos@100.106.20.11, 16 cores,
   368 G free) — but the box currently lacks the kaggle CLI + creds, so either download locally and
   rsync the records, or install kaggle there first.
4. **Deploy + validate.** Export to numpy (`net/infer_np.py`), bundle with `BUNDLE_NET=1
   build_submission.sh`, pilot our best deck (crustle 869 or starmie). LADDER-validate as an A/B
   vs the crustle floor — offline win-rate mispredicts rank (per 05-eval-methodology).

## Why it can beat the rule pilots
The rule pilots plateau at ~700–870 because they encode one team's heuristics. A policy distilled
from 32 top teams' *actual winning moves* across all matchups has a far higher ceiling and earns the
Strategy Track's "AI approach" score. Gate promotion on the ladder, never on offline sim.
