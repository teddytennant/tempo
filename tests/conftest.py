"""Test setup: make the mock engine importable as `cg.api` and the agent importable as `main`.

Run without any Kaggle assets: the mock under tests/mock_cg/ satisfies `import cg.api`.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# Mock engine first on the path so `import cg.api` resolves to the test double.
sys.path.insert(0, os.path.join(_HERE, "mock_cg"))
# Agent dir so `import main` loads agent/main.py (which resolves agent/deck.csv).
sys.path.insert(0, os.path.join(_ROOT, "agent"))
