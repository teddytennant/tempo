#!/usr/bin/env bash
SUB="${1:-53947755}"
for i in $(seq 1 60); do
  line=$(~/.local/bin/kaggle competitions submissions pokemon-tcg-ai-battle 2>/dev/null | grep "$SUB")
  echo "$line" | grep -qiE "PENDING|RUNNING" || { echo "DONE: $line"; exit 0; }
  sleep 120
done
echo "still pending after wait: $line"
