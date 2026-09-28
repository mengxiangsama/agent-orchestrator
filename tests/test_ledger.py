"""Contract examples and adversarial records; no real agents or artifacts."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts.check_ledger import validate


def task(task_id="A", owner="worker", dependencies=(), paths=()):
    return {
        "id": task_id,
        "owner": owner,
        "depends_on": list(dependencies),
        "write_paths": list(paths),
        "deliverables": ["result in the response"],
        "acceptance": ["requested scope and behavior checked"],
    }


def ledger(tasks=None, events=None, max_active=2, max_attempts=2, mode="implement"):
    return {
        "schema_version": 1,
        "mode": mode,
        "limits": {"max_active": max_active, "max_attempts": max_attempts},
        "tasks": [task()] if tasks is None else tasks,
        "events": [] if events is None else events,
    }


def event(kind, task_id="A", actor="main", **fields):
    return dict(task=task_id, event=kind, actor=actor, **fields)


def start(task_id="A", inputs=None, **fields):
    return event("start", task_id, inputs={} if inputs is None else inputs, **fields)


def submitted(task_id="A", actor="main"):
    return event("submit", task_id, actor, evidence=["candidate result supplied"])


def accepted(task_id="A", revision=1):
    return event("accept", task_id, revision=revision, evidence=["main checked the requested criteria"])


def completed(task_id="A", inputs=None, revision=1, **fields):
    return [start(task_id, inputs, **fields), submitted(task_id), accepted(task_id, revision)]


def invalidated(task_id="A"):
    return event("invalidate", task_id, reason="approved input changed")


class LedgerTests(unittest.TestCase):
    def assertInvalid(self, record, message):
        with self.assertRaisesRegex(ValueError, message):
            validate(record)

    def test_simple_analysis_by_main(self):
        record = ledger([task(owner="main")], completed(), max_active=1, mode="analyze")
        record["tasks"][0]["status"] = "accepted"
        self.assertEqual(validate(record)["A"], {
            "status": "accepted", "attempts": 1, "revision": 1,
            "last_revision": 1, "inputs": {},
        })

    def test_independent_parallel_work(self):
        record = ledger(
            [task("A", paths=["src/api/"]), task("B", paths=["src/ui/"])],
            [start(), start("B"), submitted(), submitted("B"), accepted("B"), accepted()],
        )
        self.assertTrue(all(info["status"] == "accepted" for info in validate(record).values()))

    def test_design_acceptance_gates_implementation(self):
        tasks = [task("D", paths=["docs/design.md"]), task("I", dependencies=["D"], paths=["src/"])]
        events = completed("D") + completed("I", {"D": 1})
        self.assertEqual(validate(ledger(tasks, events))["I"]["inputs"], {"D": 1})
        self.assertInvalid(ledger(tasks, events[:2] + [start("I", {"D": 1})]), "not accepted")

    def test_rejected_result_requires_reasoned_rework(self):
        events = [start(), submitted(), event("reject", reason="missing negative case")]
        events += completed(reason="added negative case")
        result = validate(ledger(events=events))["A"]
        self.assertEqual((result["status"], result["attempts"], result["revision"]), ("accepted", 2, 1))

    def test_failure_block_and_cancel_can_retry_after_confirmed_stop(self):
        for kind in ("fail", "block", "cancel"):
            for was_submitted in (False, True):
                with self.subTest(kind=kind, was_submitted=was_submitted):
                    events = [start()] + ([submitted()] if was_submitted else [])
                    events += [event(kind, reason="attempt stopped")]
                    events += completed(reason="underlying problem resolved")
                    self.assertEqual(validate(ledger(events=events))["A"]["attempts"], 2)

    def test_single_agent_fallback_preserves_dependency_gate(self):
        tasks = [task("D", owner="main"), task("I", owner="main", dependencies=["D"])]
        result = validate(ledger(tasks, completed("D") + completed("I", {"D": 1}), max_active=1))
        self.assertEqual(result["I"]["status"], "accepted")

    def test_design_only_acceptance_does_not_start_planned_implementation(self):
        tasks = [task("D", paths=["docs/design.md"]), task("I", dependencies=["D"])]
        record = ledger(tasks, completed("D"), mode="design")
        result = validate(record)
        self.assertEqual(result["D"]["status"], "accepted")
        self.assertEqual(result["I"]["status"], "pending")
        self.assertEqual(result["I"]["attempts"], 0)
        self.assertIsNone(result["I"]["revision"])

    def test_empty_record_and_unstarted_tasks(self):
        self.assertEqual(validate(ledger(tasks=[])), {})
        self.assertEqual(validate(ledger())["A"], {
            "status": "pending", "attempts": 0, "revision": None,
            "last_revision": 0, "inputs": {},
        })

    def test_all_modes_are_labels_not_filename_authorization(self):
        for mode in ("analyze", "design", "implement", "review"):
            with self.subTest(mode=mode):
                self.assertEqual(validate(ledger([task(paths=["src/result.py"])], completed(), mode=mode))["A"]["status"], "accepted")

    def test_root_shape_version_mode_and_missing_fields(self):
        for value in (None, [], "record", True):
            with self.subTest(value=value):
                self.assertInvalid(value, "expected an object")
        for value in (True, False, 1.0, "1", 2, None):
            record = ledger()
            record["schema_version"] = value
            with self.subTest(version=value):
                self.assertInvalid(record, "schema_version")
        for value in (None, [], {}, "execute", " "):
            record = ledger(mode=value)
            with self.subTest(mode=value):
                self.assertInvalid(record, "mode")
        for key in ledger():
            record = ledger()
            del record[key]
            with self.subTest(missing=key):
                self.assertInvalid(record, "missing field")

    def test_unknown_fields_and_nonstring_object_keys(self):
        for target in ("root", "limits", "task", "event"):
            for key in ("typo", 7):
                record = ledger(events=[start()])
                objects = {"root": record, "limits": record["limits"], "task": record["tasks"][0], "event": record["events"][0]}
                objects[target][key] = 1
                with self.subTest(target=target, key=key):
                    self.assertInvalid(record, "unknown field|keys must be strings")

    def test_limits_are_positive_integers_not_bools(self):
        for key in ("max_active", "max_attempts"):
            for value in (True, False, 0, -1, 1.0, "2", None, [], {}):
                record = ledger()
                record["limits"][key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, "positive integer")
        for value in (None, [], 1):
            record = ledger()
            record["limits"] = value
            self.assertInvalid(record, "limits")

    def test_task_and_event_collections_require_lists_of_objects(self):
        for key in ("tasks", "events"):
            for value in (None, {}, (), "", [None], [[]]):
                record = ledger()
                record[key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, "expected")

    def test_required_task_fields_and_strict_field_types(self):
        for key in task():
            record = ledger()
            del record["tasks"][0][key]
            with self.subTest(missing=key):
                self.assertInvalid(record, "missing field")
        for key in ("id", "owner"):
            for value in (None, "", " \t", 1, [], {}):
                record = ledger()
                record["tasks"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, "nonempty string")
        for key in ("depends_on", "write_paths", "deliverables", "acceptance"):
            for value in (None, "value", {}, (), [1], [False], [" "], [[]]):
                record = ledger()
                record["tasks"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, key)
        for key in ("deliverables", "acceptance"):
            record = ledger()
            record["tasks"][0][key] = []
            self.assertInvalid(record, "nonempty list")

    def test_duplicate_task_ids(self):
        self.assertInvalid(ledger([task(), task()]), "duplicate task")

    def test_missing_self_and_duplicate_dependencies(self):
        cases = [(["missing"], "missing dependency"), (["A"], "self dependency"), (["B", "B"], "duplicate dependency")]
        for dependencies, error in cases:
            with self.subTest(dependencies=dependencies):
                self.assertInvalid(ledger([task(dependencies=dependencies), task("B")]), error)

    def test_indirect_and_disconnected_cycles(self):
        for tasks in (
            [task("A", dependencies=["B"]), task("B", dependencies=["A"])],
            [task("A", dependencies=["B"]), task("B", dependencies=["C"]), task("C", dependencies=["A"])],
            [task("independent"), task("A", dependencies=["B"]), task("B", dependencies=["A"])],
        ):
            self.assertInvalid(ledger(tasks), "dependency cycle")

    def test_forward_references_and_long_acyclic_graph(self):
        tasks = [task(str(index), dependencies=[str(index - 1)] if index else []) for index in range(1200)]
        result = validate(ledger(list(reversed(tasks))))
        self.assertEqual(len(result), 1200)

    def test_event_required_fields_and_actor_types(self):
        for key in ("task", "event", "actor"):
            record = ledger(events=[start()])
            del record["events"][0][key]
            self.assertInvalid(record, "missing field")
            for value in (None, " ", 1, [], {}):
                record = ledger(events=[start()])
                record["events"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, "nonempty string")
        self.assertInvalid(ledger(events=[event("finish")]), "unsupported value")
        self.assertInvalid(ledger(events=[start("missing")]), "unknown task")

    def test_optional_event_fields_are_typed_even_when_not_required(self):
        cases = {"reason": [None, "", " ", [], 3], "evidence": [None, [], "text", [""], [True]], "inputs": [None, [], {"A": True}, {1: 1}], "revision": [None, 0, -1, True, 1.0, "1"]}
        for key, values in cases.items():
            for value in values:
                record = ledger(events=[start()])
                record["events"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertInvalid(record, key)

    def test_owner_can_submit_fail_or_block_but_not_another_owner(self):
        for kind in ("submit", "fail", "block"):
            fields = {"evidence": ["result"]} if kind == "submit" else {"reason": "stopped"}
            good = ledger(events=[start(), event(kind, actor="worker", **fields)])
            validate(good)
            good["events"][-1]["actor"] = "unrelated-worker"
            self.assertInvalid(good, "actor is not authorized")

    def test_only_main_can_control_execution_and_acceptance(self):
        cases = [
            ([], start(actor="worker")),
            ([start(), submitted()], dict(accepted(), actor="worker")),
            ([start(), submitted()], event("reject", actor="worker", reason="bad result")),
            ([start()], event("cancel", actor="worker", reason="stop")),
            (completed(), event("invalidate", actor="worker", reason="changed")),
        ]
        for prefix, action in cases:
            with self.subTest(kind=action["event"]):
                self.assertInvalid(ledger(events=prefix + [action]), "actor is not authorized")

    def test_invalid_transitions_cannot_skip_review_or_restart_active_work(self):
        cases = [
            ([], submitted()), ([], accepted()), ([], event("reject", reason="x")),
            ([], event("fail", reason="x")), ([], event("block", reason="x")),
            ([], event("cancel", reason="x")), ([], invalidated()),
            ([start()], start(reason="retry")), ([start()], accepted()),
            ([start()], event("reject", reason="x")), ([start()], invalidated()),
            ([start(), submitted()], submitted()), ([start(), submitted()], start(reason="retry")),
            (completed(), accepted(revision=2)), (completed(), start(reason="retry")),
            (completed(), event("fail", reason="x")),
            ([start(), event("fail", reason="stopped")], accepted()),
            (completed() + [invalidated()], accepted(revision=2)),
        ]
        for prefix, action in cases:
            with self.subTest(prefix=prefix, action=action):
                self.assertInvalid(ledger(events=prefix + [action]), "cannot")

    def test_submit_and_accept_require_evidence(self):
        self.assertInvalid(ledger(events=[start(), event("submit")]), "evidence is required")
        self.assertInvalid(ledger(events=[start(), submitted(), event("accept", revision=1)]), "evidence is required")

    def test_stop_reject_and_invalidate_require_reasons(self):
        for kind, prefix in (("fail", [start()]), ("block", [start()]), ("cancel", [start()]), ("reject", [start(), submitted()]), ("invalidate", completed())):
            with self.subTest(kind=kind):
                self.assertInvalid(ledger(events=prefix + [event(kind)]), "reason is required")

    def test_every_retry_requires_a_reason(self):
        for kind in ("fail", "block", "cancel", "reject", "invalidate"):
            prefix = completed() if kind == "invalidate" else [start(), submitted()]
            events = prefix + [event(kind, reason="stopped or invalidated"), start()]
            with self.subTest(kind=kind):
                self.assertInvalid(ledger(events=events), "reason is required")

    def test_start_requires_exact_input_mapping_even_with_no_dependencies(self):
        self.assertInvalid(ledger(events=[event("start")]), "inputs must exactly match")
        self.assertInvalid(ledger(events=[start(inputs={"unknown": 1})]), "inputs must exactly match")
        tasks = [task("A"), task("B"), task("C", dependencies=["A", "B"])]
        prefix = completed() + completed("B")
        for inputs in ({}, {"A": 1}, {"A": 1, "B": 2}, {"A": 1, "B": 1, "C": 1}):
            with self.subTest(inputs=inputs):
                self.assertInvalid(ledger(tasks, prefix + [start("C", inputs)]), "inputs must exactly match")
        self.assertEqual(validate(ledger(tasks, prefix + [start("C", {"B": 1, "A": 1})]))["C"]["status"], "running")

    def test_only_accepted_dependencies_can_be_consumed(self):
        tasks = [task(), task("B", dependencies=["A"])]
        prefixes = [[], [start()], [start(), submitted()], [start(), event("fail", reason="stopped")], [start(), event("block", reason="stopped")], [start(), event("cancel", reason="stopped")], [start(), submitted(), event("reject", reason="rejected")], completed() + [invalidated()]]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assertInvalid(ledger(tasks, prefix + [start("B", {"A": 1})]), "not accepted")

    def test_first_acceptance_revision_must_be_one(self):
        self.assertInvalid(ledger(events=[start(), submitted(), accepted(revision=2)]), "start at 1")
        self.assertInvalid(ledger(events=[start(), submitted(), event("accept", evidence=["checked"])]), "revision is required")

    def test_reacceptance_strictly_increases_without_reusing_invalid_revision(self):
        prefix = completed() + [invalidated(), start(reason="new version"), submitted()]
        self.assertInvalid(ledger(events=prefix + [accepted(revision=1)]), "strictly increase")
        # Strict increase does not imply the undocumented restriction '+1 only'.
        self.assertEqual(validate(ledger(events=prefix + [accepted(revision=3)]))["A"]["revision"], 3)

    def test_submitted_retains_a_slot(self):
        record = ledger([task(), task("B")], [start(), submitted(), start("B")], max_active=1)
        self.assertInvalid(record, "max_active")

    def test_max_active_includes_running_and_boundary_is_allowed(self):
        tasks = [task("A"), task("B"), task("C")]
        validate(ledger(tasks, [start(), start("B")]))
        self.assertInvalid(ledger(tasks, [start(), start("B"), start("C")]), "max_active")

    def test_release_events_free_slots_and_ownership(self):
        tasks = [task("A", paths=["src/"]), task("B", paths=["src/file.py"])]
        for kind in ("accept", "reject", "fail", "block", "cancel"):
            action = accepted() if kind == "accept" else event(kind, reason="stopped or returned")
            events = [start(), submitted(), action, start("B")]
            with self.subTest(kind=kind):
                self.assertEqual(validate(ledger(tasks, events, max_active=1))["B"]["status"], "running")

    def test_attempt_budget_is_per_task_and_persists_after_invalidation(self):
        events = [start(), event("fail", reason="stopped"), start(reason="retry"), event("block", reason="stopped"), start(reason="retry again")]
        self.assertInvalid(ledger(events=events), "max_attempts")
        self.assertInvalid(ledger(events=completed() + [invalidated(), start(reason="changed")], max_attempts=1), "max_attempts")
        self.assertEqual(validate(ledger([task(), task("B")], completed() + completed("B"), max_attempts=1))["B"]["attempts"], 1)

    def test_same_parent_child_and_casefolded_paths_conflict(self):
        for left, right in (("src/a.py", "src/a.py"), ("src", "src/a.py"), ("src/a.py", "src/"), ("SRC/A.py", "src/a.PY"), ("Straße/a.py", "STRASSE/a.py"), (".", "anything"), ("anything", "."), ("./src//./a.py", "src/a.py")):
            for was_submitted in (False, True):
                tasks = [task("A", paths=[left]), task("B", paths=[right])]
                events = [start()] + ([submitted()] if was_submitted else []) + [start("B")]
                with self.subTest(left=left, right=right, submitted=was_submitted):
                    self.assertInvalid(ledger(tasks, events), "write ownership conflict")

    def test_ownership_checks_all_declared_paths(self):
        tasks = [task("A", paths=["docs/a.md", "src/common"]), task("B", paths=["tests/b.py", "src/common/util.py"])]
        self.assertInvalid(ledger(tasks, [start(), start("B")]), "ownership conflict")

    def test_readonly_and_component_prefix_neighbors_do_not_conflict(self):
        for left, right in (([], ["."]), (["."], []), ([], []), (["src/api"], ["src/apis"]), (["src/a.py"], ["src/a.py.bak"])):
            with self.subTest(left=left, right=right):
                validate(ledger([task("A", paths=left), task("B", paths=right)], [start(), start("B")]))

    def test_invalid_write_paths_rejected_even_for_pending_tasks(self):
        for path in ("../file", "a/../file", "..", "/tmp/file", "//host/file", "C:/file", "C:relative", "a\\b", "a/*", "a/?", "a/[ab]", "a/\x00b", "a/\nb"):
            with self.subTest(path=path):
                self.assertInvalid(ledger([task(paths=[path])]), "portable relative path")

    def test_invalidation_propagates_transitively_and_preserves_pending(self):
        tasks = [task(), task("B", dependencies=["A"]), task("C", dependencies=["B"]), task("P", dependencies=["C"]), task("U")]
        events = completed() + completed("B", {"A": 1}) + completed("C", {"B": 1}) + completed("U") + [invalidated()]
        result = validate(ledger(tasks, events))
        for task_id in ("A", "B", "C"):
            self.assertEqual(result[task_id]["status"], "invalidated")
            self.assertIsNone(result[task_id]["revision"])
            self.assertEqual(result[task_id]["last_revision"], 1)
        self.assertEqual(result["P"]["status"], "pending")
        self.assertEqual(result["P"]["attempts"], 0)
        self.assertEqual(result["U"]["status"], "accepted")

    def test_invalidation_reaches_diamond_graph_once(self):
        tasks = [task(), task("B", dependencies=["A"]), task("C", dependencies=["A"]), task("D", dependencies=["B", "C"])]
        events = completed() + completed("B", {"A": 1}) + completed("C", {"A": 1}) + completed("D", {"B": 1, "C": 1}) + [invalidated()]
        self.assertTrue(all(info["status"] == "invalidated" for info in validate(ledger(tasks, events)).values()))

    def test_any_running_or_submitted_descendant_prevents_invalidation(self):
        tasks = [task(), task("B", dependencies=["A"]), task("C", dependencies=["B"])]
        for descendant in ("B", "C"):
            for was_submitted in (False, True):
                prefix = completed()
                if descendant == "C":
                    prefix += completed("B", {"A": 1})
                inputs = {"A": 1} if descendant == "B" else {"B": 1}
                prefix += [start(descendant, inputs)]
                if was_submitted:
                    prefix += [submitted(descendant)]
                with self.subTest(descendant=descendant, submitted=was_submitted):
                    self.assertInvalid(ledger(tasks, prefix + [invalidated()]), "still active")

    def test_stopped_or_rejected_executed_descendants_are_invalidated(self):
        tasks = [task(), task("B", dependencies=["A"])]
        for kind in ("fail", "block", "cancel", "reject"):
            prefix = completed() + [start("B", {"A": 1}), submitted("B"), event(kind, "B", reason="stopped")]
            result = validate(ledger(tasks, prefix + [invalidated()]))
            with self.subTest(kind=kind):
                self.assertEqual(result["B"]["status"], "invalidated")
                self.assertEqual(result["B"]["attempts"], 1)
                self.assertIsNone(result["B"]["revision"])

    def test_new_versions_require_new_inputs_and_full_downstream_reacceptance(self):
        tasks = [task(), task("B", dependencies=["A"]), task("C", dependencies=["B"])]
        prefix = completed() + completed("B", {"A": 1}) + completed("C", {"B": 1}) + [invalidated()]
        prefix += completed(revision=2, reason="new design")
        self.assertInvalid(ledger(tasks, prefix + [start("B", {"A": 1}, reason="retry")]), "inputs must exactly match")
        self.assertInvalid(ledger(tasks, prefix + [start("C", {"B": 1}, reason="retry")]), "not accepted")
        events = prefix + completed("B", {"A": 2}, revision=2, reason="new design")
        events += completed("C", {"B": 2}, revision=2, reason="new implementation")
        result = validate(ledger(tasks, events))
        self.assertTrue(all(info["revision"] == 2 and info["attempts"] == 2 for info in result.values()))

    def test_final_declared_status_must_match_replayed_state(self):
        record = ledger(events=[start(), submitted()])
        record["tasks"][0]["status"] = "accepted"
        self.assertInvalid(record, "does not match derived 'submitted'")
        record["tasks"][0]["status"] = "submitted"
        self.assertIsNone(validate(record)["A"]["revision"])
        for value in (None, [], True, "done"):
            record["tasks"][0]["status"] = value
            self.assertInvalid(record, "status")

    def test_validation_is_pure_and_does_not_read_deliverables_or_execute_tools(self):
        record = ledger(events=completed())
        record["tasks"][0]["deliverables"] = ["/not/a/real/artifact", "$(touch should-not-exist)"]
        original = copy.deepcopy(record)
        with mock.patch("builtins.open", side_effect=AssertionError("no file access")), mock.patch("subprocess.Popen", side_effect=AssertionError("no processes")), mock.patch("os.system", side_effect=AssertionError("no tools")):
            result = validate(record)
        self.assertEqual(record, original)
        result["A"]["inputs"]["mutated"] = 9
        self.assertEqual(validate(record)["A"]["inputs"], {})


class LedgerCliTests(unittest.TestCase):
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_ledger.py"

    def run_cli(self, args, cwd):
        return subprocess.run([sys.executable, "-B", str(self.script)] + list(args), cwd=cwd, capture_output=True, text=True, timeout=10)

    def test_cli_success_outputs_derived_states_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            text = json.dumps(ledger(events=completed()))
            path.write_text(text, encoding="utf-8")
            result = self.run_cli([str(path)], directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["A"]["status"], "accepted")
            self.assertEqual(result.stderr, "")
            self.assertEqual(path.read_text(encoding="utf-8"), text)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_cli_invalid_record_or_json_exits_one_without_traceback(self):
        texts = ["{", "[]", json.dumps(ledger(events=[accepted()])), '{"schema_version":1,"schema_version":1}', '{"number":NaN}', '{"number":Infinity}']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            for text in texts:
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text):
                    result = self.run_cli([str(path)], directory)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_cli_json_labels_are_safe_for_output_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            for task_id in ("设计任务", "\ud800"):
                record = ledger([task(task_id)], completed(task_id))
                path.write_text(json.dumps(record), encoding="utf-8")
                with self.subTest(task_id=task_id):
                    result = self.run_cli([str(path)], directory)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)[task_id]["status"], "accepted")

    def test_cli_missing_unreadable_encoding_and_usage_errors_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            path.write_bytes(b"\xff")
            for args in ([], ["one", "two"], [str(Path(directory) / "missing.json")], [directory], [str(path)]):
                with self.subTest(args=args):
                    result = self.run_cli(args, directory)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("error:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
