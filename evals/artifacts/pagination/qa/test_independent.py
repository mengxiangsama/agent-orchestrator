"""Main-agent independent checks derived from R1-R6, not from the implementation."""

import copy
import random
import unittest

from pagination import paginate


class IndependentAcceptance(unittest.TestCase):
    def assert_invalid(self, records, page, page_size):
        before = copy.deepcopy(records)
        with self.assertRaises(ValueError) as caught:
            paginate(records, page, page_size)
        self.assertEqual(str(caught.exception), "INVALID_ARGUMENT")
        self.assertEqual(records, before)

    def test_required_example_r6(self):
        rows = [{"id": i} for i in range(1, 6)]
        self.assertEqual(paginate(rows, 2, 2), [{"id": 3}, {"id": 4}])

    def test_unsorted_input_r2(self):
        rows = [{"id": i} for i in [5, 1, 4, 2, 3]]
        self.assertEqual([x["id"] for x in paginate(rows, 2, 2)], [3, 4])

    def test_no_input_mutation_r1(self):
        rows = [{"id": 3, "extra": {"a": [1]}}, {"id": 1}, {"id": 2}]
        before = copy.deepcopy(rows)
        object_ids = [id(row) for row in rows]
        paginate(rows, 1, 2)
        self.assertEqual(rows, before)
        self.assertEqual([id(row) for row in rows], object_ids)

    def test_empty_input(self):
        self.assertEqual(paginate([], 1, 10), [])

    def test_page_beyond_end_r5(self):
        self.assertEqual(paginate([{"id": 1}], 2, 1), [])

    def test_last_partial_page(self):
        self.assertEqual(paginate([{"id": i} for i in range(1, 6)], 3, 2), [{"id": 5}])

    def test_page_size_boundaries_r3(self):
        rows = [{"id": i} for i in range(101, 0, -1)]
        self.assertEqual(paginate(rows, 1, 1), [{"id": 1}])
        self.assertEqual(len(paginate(rows, 1, 100)), 100)
        self.assertEqual(paginate(rows, 2, 100), [{"id": 101}])

    def test_invalid_page_r4(self):
        for value in [0, -1, 1.0, "1", None, True, False]:
            with self.subTest(page=value):
                self.assert_invalid([{"id": 1}], value, 2)

    def test_invalid_page_size_r4(self):
        for value in [0, -1, 101, 2.0, "2", None, True, False]:
            with self.subTest(page_size=value):
                self.assert_invalid([{"id": 1}], 1, value)

    def test_invalid_record_container(self):
        for rows in [None, {}, (), "text", 4]:
            with self.subTest(records=rows):
                self.assert_invalid(rows, 1, 2)

    def test_invalid_record_shape(self):
        for rows in [[{}], [1], [None], [[1]], [{"id": 1}, {"x": 2}]]:
            with self.subTest(records=rows):
                self.assert_invalid(rows, 1, 2)

    def test_invalid_id_type(self):
        for value in [None, "1", 1.0, True, False, [], {}]:
            with self.subTest(id=value):
                self.assert_invalid([{"id": value}], 1, 2)

    def test_invalid_parameters_on_empty_input(self):
        self.assert_invalid([], 0, 10)
        self.assert_invalid([], 1, 101)

    def test_all_records_validated_even_outside_page(self):
        self.assert_invalid([{"id": 1}, {"id": "bad"}], 100, 1)

    def test_duplicate_negative_ids_and_extra_fields(self):
        rows = [{"id": 2, "tag": "a"}, {"id": -5}, {"id": 2, "tag": "b"}]
        result = paginate(rows, 1, 3)
        self.assertEqual([r["id"] for r in result], [-5, 2, 2])
        self.assertCountEqual([r.get("tag") for r in result], [None, "a", "b"])

    def test_large_page(self):
        self.assertEqual(paginate([{"id": 1}], 10**30, 100), [])

    def test_accepted_design_int_subclass_rejection(self):
        class IntChild(int):
            pass

        self.assert_invalid([{"id": IntChild(1)}], 1, 2)
        self.assert_invalid([], IntChild(1), 2)
        self.assert_invalid([], 1, IntChild(2))

    def test_accepted_design_stable_sort(self):
        rows = [{"id": 2, "tag": "first"}, {"id": 0}, {"id": 2, "tag": "second"}]
        self.assertEqual(paginate(rows, 1, 100), [rows[1], rows[0], rows[2]])

    def test_result_is_new_list(self):
        rows = [{"id": 1}]
        self.assertIsNot(paginate(rows, 1, 100), rows)

    def test_seeded_pagination_properties(self):
        rng = random.Random(290926)
        for trial in range(150):
            rows = [{"id": rng.randint(-100, 100), "n": i} for i in range(rng.randint(0, 120))]
            before = copy.deepcopy(rows)
            size = rng.randint(1, 100)
            page = rng.randint(1, 8)
            expected_ids = sorted(r["id"] for r in rows)[(page - 1) * size:page * size]
            with self.subTest(trial=trial):
                self.assertEqual([r["id"] for r in paginate(rows, page, size)], expected_ids)
                self.assertEqual(rows, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
