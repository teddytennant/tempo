"""Match a mined deck composition (sorted 60-id csv) against all known deck csvs,
and print the deck's card names via cg card data.

Usage: ./scripts/run.sh tools/match_deck_composition.py <deck.csv> [<deck2.csv> ...]
"""
import glob
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def load_ids(path):
    with open(path) as f:
        return sorted(int(x.strip()) for x in f if x.strip())


def main():
    known = {}
    for p in glob.glob(os.path.join(_ROOT, "data", "decks", "*.csv")) + \
             glob.glob(os.path.join(_ROOT, "data", "decks", "mined", "*.csv")):
        try:
            known[p] = load_ids(p)
        except Exception:
            pass

    try:
        from cg.api import all_card_data
        cards = {c.cardId: c for c in all_card_data()}
    except Exception as e:
        print(f"(card names unavailable: {e})")
        cards = {}

    for target in sys.argv[1:]:
        ids = load_ids(target)
        print(f"\n=== {target} ({len(ids)} cards) ===")
        cnt = Counter(ids)
        for cid, n in sorted(cnt.items()):
            c = cards.get(cid)
            if c is None:
                print(f"  {n}x {cid:5d} ?")
                continue
            tags = [str(getattr(c, "cardType", ""))]
            if getattr(c, "megaEx", False):
                tags.append("MEGA-ex")
            elif getattr(c, "ex", False):
                tags.append("ex")
            if getattr(c, "tera", False):
                tags.append("tera")
            if getattr(c, "aceSpec", False):
                tags.append("ACE")
            print(f"  {n}x {cid:5d} {c.name} [{' '.join(t for t in tags if t)}]")
        # match
        scored = []
        for p, kids in known.items():
            overlap = sum((Counter(ids) & Counter(kids)).values())
            scored.append((overlap, p))
        scored.sort(reverse=True)
        print("top matches (card-overlap of 60):")
        for ov, p in scored[:5]:
            exact = " EXACT" if ov == 60 and len(known[p]) == 60 else ""
            print(f"  {ov}/60 {os.path.relpath(p, _ROOT)}{exact}")


if __name__ == "__main__":
    main()
