#!/usr/bin/env python3
"""Validate schema_version 1 ledger data without scheduling or artifact access.

validate(record) returns a mapping keyed by task ID. Each value contains status,
attempts, revision (the currently valid acceptance, or None), last_revision (the
last issued acceptance, initially 0), and inputs (the last start's versions).
Only internal consistency is checked; identities, evidence and real tool state
are not authenticated. Paths are compared lexically, not through a filesystem.
"""

import json
import ntpath
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


_MODES = {"analyze", "design", "implement", "review"}
_ACTIVE = {"running", "submitted"}
_STARTABLE = {"pending", "rework", "failed", "blocked", "cancelled", "invalidated"}
_STATES = _ACTIVE | _STARTABLE | {"accepted"}
_EVENTS = {
    "start", "submit", "accept", "reject", "fail", "block", "cancel", "invalidate"
}
_OWNER_EVENTS = {"submit", "fail", "block"}


def _object(value: Any, where: str, required: set, optional: set) -> None:
    if type(value) is not dict:
        raise ValueError(f"{where}: expected an object")
    if any(type(key) is not str for key in value):
        raise ValueError(f"{where}: object keys must be strings")
    missing = required - value.keys()
    if missing:
        raise ValueError(f"{where}: missing field {sorted(missing)[0]!r}")
    unknown = value.keys() - required - optional
    if unknown:
        raise ValueError(f"{where}: unknown field {sorted(unknown)[0]!r}")


def _string(value: Any, where: str) -> None:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{where}: expected a nonempty string")


def _integer(value: Any, where: str) -> None:
    # bool is an int subclass, but is not a JSON integer for this contract.
    if type(value) is not int or value <= 0:
        raise ValueError(f"{where}: expected a positive integer")


def _strings(value: Any, where: str, nonempty: bool = False) -> None:
    if type(value) is not list or (nonempty and not value):
        qualifier = "nonempty " if nonempty else ""
        raise ValueError(f"{where}: expected a {qualifier}list of strings")
    for index, item in enumerate(value):
        _string(item, f"{where}[{index}]")


def _choice(value: Any, where: str, choices: set) -> None:
    _string(value, where)
    if value not in choices:
        raise ValueError(f"{where}: unsupported value {value!r}")


def _path(value: str, where: str) -> Tuple[str, ...]:
    if (
        value.startswith("/")
        or ntpath.splitdrive(value)[0]
        or "\\" in value
        or any(char in value for char in "*?[]")
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or ".." in value.split("/")
    ):
        raise ValueError(f"{where}: expected a portable relative path without '..' or glob")
    # '.' and duplicate separators do not create independent ownership. The
    # empty tuple represents the workspace root, which overlaps every path.
    return tuple(
        part.casefold() for part in value.split("/") if part not in {"", "."}
    )


def _overlap(left: Tuple[str, ...], right: Tuple[str, ...]) -> bool:
    length = min(len(left), len(right))
    return left[:length] == right[:length]


@dataclass
class _State:
    status: str = "pending"
    attempts: int = 0
    last_revision: int = 0
    inputs: Dict[str, int] = field(default_factory=dict)


def validate(record: Any) -> Dict[str, Dict[str, Any]]:
    """Replay a v1 JSON record and return derived task information.

    Raise ValueError for invalid structure or inconsistent events. This function
    does not mutate the input, read files, execute tools, or write files.
    """
    _object(
        record, "record",
        {"schema_version", "mode", "limits", "tasks", "events"}, set(),
    )
    if type(record["schema_version"]) is not int or record["schema_version"] != 1:
        raise ValueError("schema_version: expected integer 1")
    _choice(record["mode"], "mode", _MODES)
    limits = record["limits"]
    _object(limits, "limits", {"max_active", "max_attempts"}, set())
    for key in ("max_active", "max_attempts"):
        _integer(limits[key], f"limits.{key}")
    for key in ("tasks", "events"):
        if type(record[key]) is not list:
            raise ValueError(f"{key}: expected a list")

    tasks = {}
    paths = {}
    for index, task in enumerate(record["tasks"]):
        where = f"tasks[{index}]"
        _object(
            task, where,
            {"id", "owner", "depends_on", "write_paths", "deliverables", "acceptance"},
            {"status"},
        )
        for key in ("id", "owner"):
            _string(task[key], f"{where}.{key}")
        task_id = task["id"]
        if task_id in tasks:
            raise ValueError(f"{where}.id: duplicate task {task_id!r}")
        for key in ("depends_on", "write_paths", "deliverables", "acceptance"):
            _strings(
                task[key], f"{where}.{key}", key in {"deliverables", "acceptance"}
            )
        if len(task["depends_on"]) != len(set(task["depends_on"])):
            raise ValueError(f"{where}.depends_on: duplicate dependency")
        if "status" in task:
            _choice(task["status"], f"{where}.status", _STATES)
        paths[task_id] = [
            _path(path, f"{where}.write_paths[{i}]")
            for i, path in enumerate(task["write_paths"])
        ]
        tasks[task_id] = task

    children: Dict[str, List[str]] = {task_id: [] for task_id in tasks}
    indegree = {}
    for task_id, task in tasks.items():
        indegree[task_id] = len(task["depends_on"])
        for dependency in task["depends_on"]:
            if dependency == task_id:
                raise ValueError(f"task {task_id!r}: self dependency")
            if dependency not in tasks:
                raise ValueError(f"task {task_id!r}: missing dependency {dependency!r}")
            children[dependency].append(task_id)

    ready = deque(task_id for task_id in tasks if indegree[task_id] == 0)
    visited = 0
    while ready:
        task_id = ready.popleft()
        visited += 1
        for child in children[task_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(tasks):
        raise ValueError("tasks: dependency cycle")

    states = {task_id: _State() for task_id in tasks}
    # A dict preserves event order for deterministic conflict diagnostics.
    active: Dict[str, None] = {}
    for index, event in enumerate(record["events"]):
        where = f"events[{index}]"
        _object(
            event, where, {"task", "event", "actor"},
            {"reason", "evidence", "inputs", "revision"},
        )
        for key in ("task", "actor"):
            _string(event[key], f"{where}.{key}")
        _choice(event["event"], f"{where}.event", _EVENTS)
        if "reason" in event:
            _string(event["reason"], f"{where}.reason")
        if "evidence" in event:
            _strings(event["evidence"], f"{where}.evidence", True)
        if "revision" in event:
            _integer(event["revision"], f"{where}.revision")
        if "inputs" in event:
            if type(event["inputs"]) is not dict:
                raise ValueError(f"{where}.inputs: expected an object")
            for dependency, revision in event["inputs"].items():
                _string(dependency, f"{where}.inputs key")
                _integer(revision, f"{where}.inputs[{dependency!r}]")

        task_id = event["task"]
        if task_id not in tasks:
            raise ValueError(f"{where}.task: unknown task {task_id!r}")
        task, state, kind = tasks[task_id], states[task_id], event["event"]
        where += f" ({task_id!r}, {kind})"
        permitted = {"main", task["owner"]} if kind in _OWNER_EVENTS else {"main"}
        if event["actor"] not in permitted:
            raise ValueError(f"{where}: actor is not authorized")

        allowed = {
            "start": _STARTABLE,
            "submit": {"running"},
            "accept": {"submitted"},
            "reject": {"submitted"},
            "fail": _ACTIVE,
            "block": _ACTIVE,
            "cancel": _ACTIVE,
            "invalidate": {"accepted"},
        }[kind]
        if state.status not in allowed:
            raise ValueError(f"{where}: cannot {kind} from {state.status}")
        if kind in {"submit", "accept"} and "evidence" not in event:
            raise ValueError(f"{where}: evidence is required")
        needs_reason = kind in {"reject", "fail", "block", "cancel", "invalidate"}
        needs_reason = needs_reason or (kind == "start" and state.attempts > 0)
        if needs_reason and "reason" not in event:
            raise ValueError(f"{where}: reason is required")

        if kind == "start":
            if state.attempts >= limits["max_attempts"]:
                raise ValueError(f"{where}: max_attempts budget exceeded")
            expected = {}
            for dependency in task["depends_on"]:
                if states[dependency].status != "accepted":
                    raise ValueError(
                        f"{where}: dependency {dependency!r} is not accepted"
                    )
                expected[dependency] = states[dependency].last_revision
            if "inputs" not in event or event["inputs"] != expected:
                raise ValueError(
                    f"{where}: inputs must exactly match current accepted "
                    f"dependency revisions {expected!r}"
                )
            if len(active) >= limits["max_active"]:
                raise ValueError(f"{where}: max_active budget exceeded")
            for other in active:
                if any(
                    _overlap(left, right)
                    for left in paths[task_id] for right in paths[other]
                ):
                    raise ValueError(
                        f"{where}: write ownership conflict with active task {other!r}"
                    )
            state.status = "running"
            state.attempts += 1
            state.inputs = dict(event["inputs"])
            active[task_id] = None
        elif kind == "submit":
            state.status = "submitted"
        elif kind == "accept":
            if "revision" not in event:
                raise ValueError(f"{where}: revision is required")
            revision = event["revision"]
            if (
                (state.last_revision == 0 and revision != 1)
                or revision <= state.last_revision
            ):
                raise ValueError(
                    f"{where}: revision must start at 1 and strictly increase"
                )
            state.last_revision = revision
            state.status = "accepted"
            del active[task_id]
        elif kind == "invalidate":
            descendants = set()
            queue = deque(children[task_id])
            while queue:
                child = queue.popleft()
                if child in descendants:
                    continue
                descendants.add(child)
                if states[child].status in _ACTIVE:
                    raise ValueError(
                        f"{where}: descendant {child!r} is still active; confirm stop first"
                    )
                queue.extend(children[child])
            state.status = "invalidated"
            for child in descendants:
                if states[child].attempts:
                    states[child].status = "invalidated"
        else:
            state.status = {
                "reject": "rework", "fail": "failed",
                "block": "blocked", "cancel": "cancelled",
            }[kind]
            del active[task_id]

    result = {}
    for task_id, task in tasks.items():
        state = states[task_id]
        if "status" in task and task["status"] != state.status:
            raise ValueError(
                f"task {task_id!r}: declared status {task['status']!r} "
                f"does not match derived {state.status!r}"
            )
        result[task_id] = {
            "status": state.status,
            "attempts": state.attempts,
            "revision": state.last_revision if state.status == "accepted" else None,
            "last_revision": state.last_revision,
            "inputs": dict(state.inputs),
        }
    return result


def _json_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("error: usage: python scripts/check_ledger.py path.json", file=sys.stderr)
        return 1
    try:
        with open(args[0], encoding="utf-8") as source:
            record = json.load(
                source, object_pairs_hook=_json_object, parse_constant=_json_constant
            )
        result = validate(record)
    except (ValueError, OSError, RecursionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    # ASCII escaping also makes valid JSON strings safe on limited-encoding
    # terminals, including escaped surrogate code points in task labels.
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
