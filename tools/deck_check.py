"""Validate deck legality against EN_Card_Data.csv (no engine needed).

Checks per deck file: exactly 60 IDs, every ID exists, <=4 copies of any card (Basic Energy exempt),
<=1 ACE SPEC total, >=1 Basic Pokémon. A bad deck would waste a scarce daily submission, so this
runs before any submit.

Run: python3 tools/deck_check.py data/decks/*.csv
"""
import csv
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(_ROOT, "data", "raw", "EN_Card_Data.csv")


def load_cards():
    info = {}
    with open(CSV, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            cid = row["Card ID"].strip()
            if not cid.isdigit():
                continue
            cid = int(cid)
            if cid in info:
                continue
            stage = (row["Stage (Pokémon)/Type (Energy and Trainer)"] or "").strip()
            rule = (row["Rule"] or "").strip()
            info[cid] = {"name": row["Card Name"].strip(), "stage": stage, "rule": rule}
    return info


def check(path, info):
    with open(path) as f:
        ids = [int(x) for x in f.read().splitlines() if x.strip()]
    name = os.path.basename(path)
    errs = []
    if len(ids) != 60:
        errs.append(f"{len(ids)} cards (need 60)")
    missing = [i for i in ids if i not in info]
    if missing:
        errs.append(f"unknown IDs: {sorted(set(missing))}")
    counts = Counter(ids)
    for cid, n in counts.items():
        if cid in info and n > 4:
            if "Basic Energy" not in info[cid]["stage"]:
                errs.append(f"{n}x {info[cid]['name']} ({cid}) — >4 copies")
    ace = [cid for cid in counts if cid in info and "ACE SPEC" in info[cid]["rule"]]
    if len(ace) > 1:
        errs.append("multiple ACE SPEC: " + ", ".join(f"{info[c]['name']}({c})" for c in ace))
    basics = sum(n for cid, n in counts.items()
                 if cid in info and info[cid]["stage"] == "Basic Pokémon")
    if basics < 1:
        errs.append("no Basic Pokémon")
    status = "OK " if not errs else "FAIL"
    extra = f"basics={basics} aceSpec={[info[c]['name'] for c in ace]}"
    print(f"[{status}] {name:22s} {extra}")
    for e in errs:
        print(f"        - {e}")
    return not errs


def main():
    info = load_cards()
    paths = sys.argv[1:] or [os.path.join(_ROOT, "data", "decks", f)
                             for f in os.listdir(os.path.join(_ROOT, "data", "decks"))]
    ok = all(check(p, info) for p in sorted(paths))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
