"""Deliberate failure injection for an orchestration evaluation, not production."""
import sys

print("SYNTHETIC_INPUT_MISSING: dataset.csv is unavailable", file=sys.stderr)
sys.exit(7)
