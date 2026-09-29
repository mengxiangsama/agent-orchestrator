import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pagination import paginate


class IntChild(int):
    pass


class ListChild(list):
    pass


class DictChild(dict):
    pass


class PaginationTests(unittest.TestCase):
    def assert_invalid(self, records, page, page_size):
        before = copy.deepcopy(records)
        references = list(records) if isinstance(records, list) else None
        with self.assertRaises(ValueError) as caught:
            paginate(records, page, page_size)
        self.assertEqual(type(caught.exception), ValueError)
        self.assertEqual(str(caught.exception), "INVALID_ARGUMENT")
        self.assertEqual(caught.exception.args, ("INVALID_ARGUMENT",))
        self.assertEqual(records, before)
        if references is not None:
            self.assertEqual(len(records), len(references))
            for actual, original in zip(records, references):
                self.assertIs(actual, original)

    def test_a1_to_a9_pagination_boundaries(self):
        five = [{"id": i} for i in (5, 1, 4, 2, 3)]
        three = [{"id": i} for i in (3, 1, 2)]
        many = [{"id": i} for i in range(101, 0, -1)]
        cases = [
            ("A1", five, 2, 2, [3, 4]),
            ("A2", three, 1, 2, [1, 2]),
            ("A3", five, 3, 2, [5]),
            ("A4", [{"id": 1}, {"id": 2}], 2, 2, []),
            ("A5", [{"id": 1}], 10**30, 1, []),
            ("A6", [], 1, 2, []),
            ("A7", three, 2, 1, [2]),
            ("A8", many, 1, 100, list(range(1, 101))),
            ("A9", many, 2, 100, [101]),
        ]
        for case, records, page, size, expected in cases:
            with self.subTest(case=case):
                before = copy.deepcopy(records)
                references = list(records)
                result = paginate(records, page, size)
                self.assertEqual([record["id"] for record in result], expected)
                self.assertEqual(type(result), list)
                self.assertIsNot(result, records)
                self.assertEqual(records, before)
                for actual, original in zip(records, references):
                    self.assertIs(actual, original)

    def test_a10_negative_zero_duplicate_ids_and_stability(self):
        records = [{"id": 2, "tag": "a"}, {"id": -1},
                   {"id": 0}, {"id": 2, "tag": "b"}]
        self.assertEqual(paginate(records, 1, 100), [
            {"id": -1}, {"id": 0},
            {"id": 2, "tag": "a"}, {"id": 2, "tag": "b"},
        ])

    def test_a11_preserves_input_and_extra_fields(self):
        records = [{"id": 2, "extra": {"v": [1]}},
                   {"id": 1, "name": "one"}]
        before = copy.deepcopy(records)
        references = list(records)
        result = paginate(records, 1, 1)
        self.assertEqual(result, [{"id": 1, "name": "one"}])
        self.assertIsNot(result, records)
        self.assertEqual(paginate(records, 2, 1),
                         [{"id": 2, "extra": {"v": [1]}}])
        self.assertEqual(records, before)
        for actual, original in zip(records, references):
            self.assertIs(actual, original)

    def test_e1_invalid_record_containers(self):
        for bad in (None, (), {}, "records", 1):
            with self.subTest(value=bad):
                self.assert_invalid(bad, 1, 2)

    def test_e2_invalid_record_elements(self):
        for bad in (None, 1, [], "record"):
            with self.subTest(value=bad):
                self.assert_invalid([bad], 1, 2)

    def test_e3_missing_id(self):
        self.assert_invalid([{"name": "missing"}], 1, 2)

    def test_e4_invalid_id_types(self):
        for bad in (None, "1", 1.0, True, False):
            with self.subTest(value=bad):
                self.assert_invalid([{"id": bad}], 1, 2)

    def test_e5_invalid_pages(self):
        for bad in (0, -1, None, "1", 1.0, True, False):
            with self.subTest(value=bad):
                self.assert_invalid([{"id": 1}], bad, 2)

    def test_e6_invalid_page_sizes(self):
        for bad in (0, -1, 101, None, "2", 2.0, True, False):
            with self.subTest(value=bad):
                self.assert_invalid([{"id": 1}], 1, bad)

    def test_e7_integer_subclasses_rejected(self):
        self.assert_invalid([{"id": IntChild(1)}], 1, 2)
        self.assert_invalid([], IntChild(1), 2)
        self.assert_invalid([], 1, IntChild(2))

    def test_e8_empty_input_still_validates_parameters(self):
        for page, size in ((0, 2), (1, 101), (True, 2), (1, False)):
            with self.subTest(page=page, size=size):
                self.assert_invalid([], page, size)

    def test_e9_out_of_range_still_validates_records(self):
        self.assert_invalid([{"id": 1}, {}], 999, 1)

    def test_e10_records_outside_page_still_validated(self):
        self.assert_invalid([{"id": 1}, {"id": "2"}], 1, 1)

    def test_e11_invalid_input_is_unchanged(self):
        self.assert_invalid([{"id": 2}, {"id": 1}, {}], 1, 1)

    def test_validation_finishes_before_sorting(self):
        with patch("builtins.sorted", side_effect=AssertionError("early sort")):
            self.assert_invalid([{"id": 1}, {"id": "2"}], 1, 1)

    def test_container_subclasses_are_allowed(self):
        records = ListChild([DictChild(id=2), DictChild(id=1)])
        self.assertEqual(paginate(records, 1, 100), [{"id": 1}, {"id": 2}])

    def test_fixture_second_page_preserves_labels(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "records.json"
        records = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(paginate(records, 2, 2), [
            {"id": 3, "label": "three"}, {"id": 4, "label": "four"},
        ])


if __name__ == "__main__":
    unittest.main()
