#!/usr/bin/env bash
# Submit Dunsparce + Lucario at 8pm local (= 00:00 UTC = fresh daily budget). Retries.
cd "$(dirname "$0")/.."
KCMD="$HOME/.local/bin/kaggle"
target=$(date -d 'today 20:00' +%s); now=$(date +%s)
[ "$now" -gt "$target" ] && target=$(date -d 'tomorrow 20:00' +%s)
sleep $(( target - now ))
sub() {
  for i in $(seq 1 6); do
    out=$("$KCMD" competitions submit pokemon-tcg-ai-battle -f "$1" -m "$2" 2>&1)
    echo "$(date '+%H:%M') $1 -> $out" >> submit_8pm_decks.log
    echo "$out" | grep -qi "Successfully submitted" && return 0
    sleep 120
  done
}
sub agent/submission_dunsparce.tar.gz "tempo: Dunsparce/Alakazam draw-combo specialist (20xhand dmg, breaks walls). Rule-based scorer."
sleep 30
sub agent/submission_starmie.tar.gz "tempo: Mega Starmie/Froslass ex specialist + prize-tracking deck-search. Rule-based scorer."
echo "DONE $(date)" >> submit_8pm_decks.log
