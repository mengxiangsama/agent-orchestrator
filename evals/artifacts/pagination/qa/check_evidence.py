"""Check published evidence consistency; does not authenticate agent tool calls.

Publication adaptation: the failure JSON hash below is for the redacted copy.
The original-run checker used the private, unredacted failure JSON hash.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    run = json.loads((ROOT / "run.json").read_text(encoding="utf-8"))
    events = run["events"]
    d1_accept = next(i for i, e in enumerate(events) if e["task"] == "D1" and e["event"] == "accept")
    i1_starts = [i for i, e in enumerate(events) if e["task"] == "I1" and e["event"] == "start"]
    assert len(i1_starts) == 2
    assert all(i > d1_accept for i in i1_starts)
    assert all(events[i]["inputs"] == {"D1": 1} for i in i1_starts)
    assert len([e for e in events if e["task"] == "D1" and e["event"] == "start"]) == 2
    assert any(e["task"] == "D1" and e["event"] == "reject" for e in events)
    assert any(e["task"] == "I1" and e["event"] == "fail" for e in events)
    assert digest("docs/design-attempt-1.md") == "c564379488f5ce402cb8916c7d98a9863d7569813c4f7e4ae921964bc3be5a6d"
    assert digest("docs/design-v1.md") == "6a0fe8ec5b6edd62507486e73f3cf4941e809659e48e61ac700f9c8681647387"
    assert digest("evidence/i1-attempt-1.json") == "1cb342e6d33351e9a78a4b64e3092613d94cee6957ff5e9cc0781852c47bc162"
    assert digest("fixtures/records.json") == "ed5c433fce91e49fb48643f1d0bb8a86801ffc72c205d0f7106401a6456cec7b"
    failed = json.loads((ROOT / "evidence/i1-attempt-1.json").read_text(encoding="utf-8"))
    repeated = json.loads((ROOT / "evidence/main-missing-input-probe.json").read_text(encoding="utf-8"))
    recovered = json.loads((ROOT / "evidence/main-recovery-probe.json").read_text(encoding="utf-8"))
    assert failed["exit_code"] == repeated["exit_code"] == 1
    assert "FileNotFoundError" in failed["output"] and "FileNotFoundError" in repeated["output"]
    assert not failed["implementation_generated"] and not failed["retried"]
    assert recovered["exit_code"] == 0
    assert failed["command"] == repeated["command"] == recovered["command"]
    print("PASS: dependency ordering, two-attempt limits, rejected design, failure/recovery, immutable evidence hashes")
    print("LIMIT: checks record/file consistency only; tool-call authenticity remains in conversation trace")


if __name__ == "__main__":
    main()
