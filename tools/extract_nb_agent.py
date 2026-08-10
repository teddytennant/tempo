"""Pull a submittable (main.py, deck.csv) pair out of a competition notebook.

Public agents in this competition are published in three shapes, and hand-extracting each one is
where the time goes:

  1. `%%writefile main.py` cell + a DECK list written to deck.csv by a separate cell,
  2. a `MAIN_SOURCE = r'''...'''` / `DECK_SOURCE = r'''...'''` pair inside one generator cell,
  3. a base64 PAYLOAD_B64 dict mapping filenames to bytes.

This handles all three, plus a `.py`-script kernel (no ipynb). It writes <out>/main.py and
<out>/deck.csv and refuses to write a deck that is not exactly 60 cards, so a bad extraction is a
hard error here rather than a failed Kaggle validation later.

  ./scripts/run.sh -m tools.extract_nb_agent notebooks/foo/foo.ipynb experiments/fork_foo
"""
from __future__ import annotations

import ast
import base64
import json
import os
import re
import sys


def _cells(path):
    if path.endswith(".ipynb"):
        nb = json.load(open(path))
        return ["".join(c["source"]) if isinstance(c["source"], list) else c["source"]
                for c in nb["cells"] if c["cell_type"] == "code"]
    return [open(path).read()]


def _balanced(src, start):
    """Return the {...} literal beginning at src[start]."""
    depth, i = 0, start
    while True:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def _triple(src, marker):
    i = src.find(marker)
    if i < 0:
        return None
    i += len(marker)
    j = src.index("'''", i)
    return src[i:j]


def extract(path):
    main = deck = group = None
    for src in _cells(path):
        if main is None and src.lstrip().startswith("%%writefile main.py"):
            main = src.split("\n", 1)[1]
        if main is None:
            main = _triple(src, "MAIN_SOURCE = r'''")
        if deck is None:
            deck = _triple(src, "DECK_SOURCE = r'''")
        if group is None:
            group = _triple(src, "GROUP_SOURCE = r'''")
        if "PAYLOAD_B64 = " in src and main is None:
            k = src.index("PAYLOAD_B64 = ") + len("PAYLOAD_B64 = ")
            payload = ast.literal_eval(_balanced(src, k))
            for name, b64 in payload.items():
                blob = base64.b64decode(b64).decode("utf-8", "replace")
                if name == "main.py":
                    main = blob
                elif name == "deck.csv":
                    deck = blob
                elif name == "group.txt":
                    group = blob
        if deck is None and re.search(r"^\s*DECK\s*=\s*\[", src, re.M):
            ns = {}
            body = re.sub(r"^\s*Path\(.*$", "", src, flags=re.M)
            body = re.sub(r"^\s*print\(.*$", "", body, flags=re.M)
            try:
                exec(body, ns)
            except Exception:
                pass
            if isinstance(ns.get("DECK"), (list, tuple)):
                deck = "\n".join(str(x) for x in ns["DECK"]) + "\n"
    return main, deck, group


def main_cli():
    path, out = sys.argv[1], sys.argv[2]
    main, deck, group = extract(path)
    if main is None:
        raise SystemExit(f"no main.py payload found in {path}")
    if deck is None:
        raise SystemExit(f"no deck found in {path}")
    cards = [int(x) for x in deck.split() if x.strip()]
    if len(cards) != 60:
        raise SystemExit(f"deck has {len(cards)} cards, expected 60")
    try:
        compile(main, "main.py", "exec")
    except SyntaxError as e:
        raise SystemExit(f"extracted main.py does not compile: {e}")
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "main.py"), "w").write(main)
    open(os.path.join(out, "deck.csv"), "w").write("\n".join(map(str, cards)) + "\n")
    if group:
        open(os.path.join(out, "group.txt"), "w").write(group)
    print(f"{out}: main.py {len(main)}B, deck 60 cards ({len(set(cards))} unique)"
          f"{', group.txt' if group else ''}")


if __name__ == "__main__":
    main_cli()
