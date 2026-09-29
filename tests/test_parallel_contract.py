"""Synthetic contract-first module ledgers, not agent or business integration runs."""

import unittest

from scripts.check_ledger import validate
from tests.test_ledger import (
    accepted,
    completed,
    event,
    invalidated,
    ledger,
    start,
    submitted,
    task,
)


MODULES = ("COUPON", "ORDER")


class ParallelContractTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            task("C", owner="contract-worker", paths=["contracts/checkout.json"]),
            task(
                "COUPON", owner="coupon-worker", dependencies=["C"],
                paths=["src/backend/coupon/", "tests/unit/coupon/"],
            ),
            task(
                "ORDER", owner="order-worker", dependencies=["C"],
                paths=["src/backend/order/", "tests/unit/order/"],
            ),
            task(
                "INTEGRATION", owner="integration-worker", dependencies=MODULES,
                paths=["tests/integration/checkout/"],
            ),
        ]
        self.parallel = completed("C") + [
            start(module, {"C": 1}) for module in MODULES
        ]

    def replay(self, events, max_active=2):
        return validate(ledger(
            self.tasks, events, max_active=max_active, max_attempts=2,
        ))

    def assertRejected(self, events, message, max_active=2):
        with self.assertRaisesRegex(ValueError, message):
            self.replay(events, max_active=max_active)

    def test_unaccepted_contract_blocks_both_modules(self):
        prefixes = {
            "pending": [],
            "running": [start("C")],
            "submitted": [start("C"), submitted("C")],
        }
        for status, prefix in prefixes.items():
            for module in MODULES:
                with self.subTest(contract=status, module=module):
                    before = self.replay(prefix)
                    self.assertEqual(before["C"]["status"], status)
                    self.assertEqual(before[module]["attempts"], 0)
                    self.assertRejected(
                        prefix + [start(module, {"C": 1})],
                        "dependency 'C' is not accepted",
                    )

    def test_accepted_contract_allows_both_backend_modules_to_run(self):
        for order in (MODULES, tuple(reversed(MODULES))):
            with self.subTest(start_order=order):
                events = completed("C") + [
                    start(module, {"C": 1}) for module in order
                ]
                result = self.replay(events)
                self.assertEqual(result["C"]["revision"], 1)
                for module in MODULES:
                    self.assertEqual(result[module]["status"], "running")
                    self.assertEqual(result[module]["inputs"], {"C": 1})
                    self.assertEqual(result[module]["attempts"], 1)
                self.assertEqual(result["INTEGRATION"]["status"], "pending")

    def test_first_finished_module_can_be_accepted_while_sibling_runs(self):
        for first, sibling in (MODULES, tuple(reversed(MODULES))):
            with self.subTest(first=first):
                before = self.replay(self.parallel)
                events = self.parallel + [submitted(first)]
                result = self.replay(events)
                self.assertEqual(result[first]["status"], "submitted")
                self.assertEqual(result[sibling], before[sibling])

                events += [accepted(first)]
                result = self.replay(events)
                self.assertEqual(result[first]["status"], "accepted")
                self.assertEqual(result[first]["revision"], 1)
                self.assertEqual(result[sibling], before[sibling])

                events += [submitted(sibling), accepted(sibling)]
                events += completed("INTEGRATION", {module: 1 for module in MODULES})
                result = self.replay(events)
                self.assertTrue(all(state["status"] == "accepted" for state in result.values()))
                self.assertEqual(result["INTEGRATION"]["inputs"], {"COUPON": 1, "ORDER": 1})

    def test_local_rework_does_not_interrupt_sibling(self):
        for returned, sibling in (MODULES, tuple(reversed(MODULES))):
            with self.subTest(returned=returned):
                before = self.replay(self.parallel)
                events = self.parallel + [
                    submitted(returned),
                    event("reject", returned, reason="synthetic boundary case missing"),
                ]
                result = self.replay(events)
                self.assertEqual(result[returned]["status"], "rework")
                self.assertIsNone(result[returned]["revision"])
                self.assertEqual(result[sibling], before[sibling])
                self.assertEqual(result["C"], before["C"])

                events += [start(returned, {"C": 1}, reason="boundary case added")]
                result = self.replay(events)
                self.assertEqual(result[returned]["status"], "running")
                self.assertEqual(result[returned]["attempts"], 2)
                self.assertEqual(result[sibling], before[sibling])

                events += [submitted(sibling), accepted(sibling)]
                result = self.replay(events)
                self.assertEqual(result[sibling]["status"], "accepted")
                self.assertEqual(result[returned]["status"], "running")
                events += [submitted(returned), accepted(returned)]
                events += completed("INTEGRATION", {module: 1 for module in MODULES})
                result = self.replay(events)
                self.assertEqual(result[returned]["attempts"], 2)
                self.assertEqual(result[sibling]["attempts"], 1)
                self.assertEqual(result["INTEGRATION"]["status"], "accepted")

    def test_integration_requires_both_module_acceptances(self):
        for unfinished, ready in (MODULES, tuple(reversed(MODULES))):
            for status in ("pending", "running", "submitted", "rework"):
                with self.subTest(unfinished=unfinished, status=status):
                    events = completed("C") + completed(ready, {"C": 1})
                    if status != "pending":
                        events += [start(unfinished, {"C": 1})]
                    if status in {"submitted", "rework"}:
                        events += [submitted(unfinished)]
                    if status == "rework":
                        events += [event("reject", unfinished, reason="boundary case missing")]
                    result = self.replay(events)
                    self.assertEqual(result[ready]["status"], "accepted")
                    self.assertEqual(result[unfinished]["status"], status)
                    self.assertIsNone(result[unfinished]["revision"])
                    self.assertRejected(
                        events + [start("INTEGRATION", {module: 1 for module in MODULES})],
                        "dependency '{}' is not accepted".format(unfinished),
                    )

    def test_shared_contract_does_not_bypass_concurrency_or_ownership_limits(self):
        # Detailed path variants and submitted-slot retention remain covered by
        # LedgerTests.test_same_parent_child_and_casefolded_paths_conflict and
        # LedgerTests.test_submitted_retains_a_slot; only scenario boundaries here.
        self.assertRejected(self.parallel, "max_active budget exceeded", max_active=1)
        serial = completed("C")
        for module in MODULES:
            serial += completed(module, {"C": 1})
        serial += completed("INTEGRATION", {module: 1 for module in MODULES})
        self.assertEqual(self.replay(serial, max_active=1)["INTEGRATION"]["status"], "accepted")

        # Widening one backend module's ownership overlaps its sibling's subtree.
        self.tasks[1]["write_paths"] = ["src/backend/"]
        self.assertRejected(self.parallel, "write ownership conflict")
        self.assertEqual(self.replay(serial)["INTEGRATION"]["status"], "accepted")

    def test_contract_change_requires_stops_and_new_inputs_before_resuming(self):
        for stopped_first, remaining in (MODULES, tuple(reversed(MODULES))):
            with self.subTest(stopped_first=stopped_first):
                self.assertRejected(self.parallel + [invalidated("C")], "still active")
                events = self.parallel + [
                    event("cancel", stopped_first, reason="stop confirmed for contract change"),
                ]
                self.assertEqual(self.replay(events)[remaining]["status"], "running")
                self.assertRejected(
                    events + [invalidated("C")],
                    "descendant '{}' is still active".format(remaining),
                )
                events += [
                    event("cancel", remaining, reason="stop confirmed for contract change"),
                    invalidated("C"),
                ]
                result = self.replay(events)
                for task_id in ("C",) + MODULES:
                    self.assertEqual(result[task_id]["status"], "invalidated")
                    self.assertIsNone(result[task_id]["revision"])
                    self.assertEqual(result[task_id]["attempts"], 1)
                self.assertEqual(result["INTEGRATION"]["status"], "pending")
                for module in MODULES:
                    self.assertRejected(
                        events + [start(module, {"C": 1}, reason="resume with old contract")],
                        "dependency 'C' is not accepted",
                    )

                events += [start("C", reason="contract updated"), submitted("C")]
                for module in MODULES:
                    self.assertRejected(
                        events + [start(module, {"C": 2}, reason="resume with proposed contract")],
                        "dependency 'C' is not accepted",
                    )
                events += [accepted("C", revision=2)]
                for module in MODULES:
                    self.assertRejected(
                        events + [start(module, {"C": 1}, reason="resume with stale contract")],
                        "inputs must exactly match current accepted dependency revisions",
                    )
                events += [
                    start(module, {"C": 2}, reason="resume with accepted contract")
                    for module in MODULES
                ]
                result = self.replay(events)
                for module in MODULES:
                    self.assertEqual(result[module]["status"], "running")
                    self.assertEqual(result[module]["inputs"], {"C": 2})
                    self.assertEqual(result[module]["attempts"], 2)
                events += [submitted(stopped_first), accepted(stopped_first)]
                self.assertRejected(
                    events + [start("INTEGRATION", {module: 1 for module in MODULES})],
                    "dependency '{}' is not accepted".format(remaining),
                )
                events += [submitted(remaining), accepted(remaining)]
                events += completed("INTEGRATION", {module: 1 for module in MODULES})
                result = self.replay(events)
                self.assertTrue(all(state["status"] == "accepted" for state in result.values()))
                self.assertEqual(result["C"]["revision"], 2)
                # These modules were stopped before their first acceptance:
                # their first valid revision is 1, consuming contract revision 2.
                for module in MODULES:
                    self.assertEqual(result[module]["revision"], 1)

    def test_contract_change_invalidates_prior_module_and_integration_acceptance(self):
        events = list(self.parallel)
        for module in MODULES:
            events += [submitted(module), accepted(module)]
        events += completed("INTEGRATION", {module: 1 for module in MODULES})
        events += [invalidated("C")]
        result = self.replay(events)
        for state in result.values():
            self.assertEqual(state["status"], "invalidated")
            self.assertIsNone(state["revision"])
            self.assertEqual(state["last_revision"], 1)
            self.assertEqual(state["attempts"], 1)

        events += completed("C", revision=2, reason="contract updated")
        self.assertRejected(
            events + [start("INTEGRATION", {module: 1 for module in MODULES}, reason="stale results")],
            "dependency 'COUPON' is not accepted",
        )
        events += [
            start(module, {"C": 2}, reason="revalidate against new contract")
            for module in MODULES
        ]
        events += [submitted("COUPON"), accepted("COUPON", revision=2)]
        self.assertRejected(
            events + [start("INTEGRATION", {"COUPON": 2, "ORDER": 1}, reason="partial revalidation")],
            "dependency 'ORDER' is not accepted",
        )
        events += [submitted("ORDER"), accepted("ORDER", revision=2)]
        self.assertRejected(
            events + [start("INTEGRATION", {module: 1 for module in MODULES}, reason="stale versions")],
            "inputs must exactly match current accepted dependency revisions",
        )
        events += completed(
            "INTEGRATION", {module: 2 for module in MODULES},
            revision=2, reason="both modules reaccepted",
        )
        result = self.replay(events)
        for state in result.values():
            self.assertEqual(state["status"], "accepted")
            self.assertEqual(state["revision"], 2)
            self.assertEqual(state["attempts"], 2)
        for module in MODULES:
            self.assertEqual(result[module]["inputs"], {"C": 2})
        self.assertEqual(result["INTEGRATION"]["inputs"], {"COUPON": 2, "ORDER": 2})


if __name__ == "__main__":
    unittest.main()
