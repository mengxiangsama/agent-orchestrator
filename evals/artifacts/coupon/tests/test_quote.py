import unittest
from collections import UserDict
from decimal import Decimal
from itertools import product
from types import MappingProxyType

from src.payment import payable, quote


class QuoteTests(unittest.TestCase):
    INVALID_AMOUNTS = (True, False, 1.0, "1", None, [], Decimal("1"))

    def test_payable_is_preserved(self):
        self.assertEqual(payable(1000, 200), 1200)
        self.assertEqual(payable(-1, 2), 1)

    def test_omitted_coupon(self):
        self.assertEqual(quote(1000, 200), 1200)

    def test_coupon_never_discounts_shipping(self):
        coupon = {"discount": 1000, "minimum": 0, "enabled": True}
        self.assertEqual(quote(100, 20, coupon), 20)

    def test_design_boundary_cases(self):
        cases = (
            ("no coupon", 1000, 200, None, 1200),
            ("disabled", 1000, 200, (300, 500, False), 1200),
            ("below minimum", 999, 200, (300, 1000, True), 1199),
            ("at minimum", 1000, 200, (300, 1000, True), 900),
            ("above minimum", 1001, 200, (300, 1000, True), 901),
            ("shipping excluded", 900, 200, (300, 1000, True), 1100),
            ("zero minimum", 1000, 200, (300, 0, True), 900),
            ("zero discount", 1000, 200, (0, 0, True), 1200),
            ("exact discount", 1000, 200, (1000, 0, True), 200),
            ("excess discount", 1000, 200, (5000, 0, True), 200),
            ("zero goods", 0, 200, (500, 0, True), 200),
            ("all zero without coupon", 0, 0, None, 0),
            ("all zero with coupon", 0, 0, (500, 0, True), 0),
            ("zero shipping", 1000, 0, (300, 1000, True), 700),
            ("large integer", 10**30, 7, (3, 0, True), 10**30 + 4),
        )
        for name, subtotal, shipping, values, expected in cases:
            with self.subTest(case=name):
                coupon = (
                    None if values is None else
                    dict(zip(("discount", "minimum", "enabled"), values))
                )
                result = quote(subtotal, shipping, coupon)
                self.assertIs(type(result), int)
                self.assertEqual(result, expected)

    def test_amount_types_are_rejected(self):
        for field, value in product(
            ("subtotal", "shipping", "discount", "minimum"), self.INVALID_AMOUNTS
        ):
            with self.subTest(field=field, value=value):
                args = {"subtotal": 1000, "shipping": 200}
                coupon = {"discount": 300, "minimum": 1000, "enabled": True}
                if field in args:
                    args[field] = value
                    path = field
                else:
                    coupon[field] = value
                    path = "coupon." + field
                with self.assertRaises(TypeError) as error:
                    quote(**args, coupon=coupon)
                self.assertTrue(str(error.exception).startswith(path + " "))

    def test_negative_amounts_are_rejected(self):
        for field in ("subtotal", "shipping", "discount", "minimum"):
            with self.subTest(field=field):
                args = {"subtotal": 1000, "shipping": 200}
                coupon = {"discount": 300, "minimum": 1000, "enabled": True}
                if field in args:
                    args[field] = -1
                    path = field
                else:
                    coupon[field] = -1
                    path = "coupon." + field
                with self.assertRaises(ValueError) as error:
                    quote(**args, coupon=coupon)
                self.assertTrue(str(error.exception).startswith(path + " "))

    def test_coupon_must_be_mapping_or_none(self):
        for value in (False, True, 0, 1, [], [("discount", 1)], "coupon"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "^coupon "):
                    quote(1000, 200, value)

    def test_exact_coupon_keys_even_when_disabled(self):
        for enabled in (True, False):
            valid = {"discount": 300, "minimum": 1000, "enabled": enabled}
            invalid = [
                {},
                {**valid, "code": "extra"},
                {**valid, 1: "non-string key"},
                {"discount": 300, "minimum": 1000, 1: enabled},
            ]
            invalid.extend(
                {key: value for key, value in valid.items() if key != missing}
                for missing in valid
            )
            for coupon in invalid:
                with self.subTest(enabled=enabled, coupon=coupon):
                    with self.assertRaisesRegex(ValueError, "^coupon keys "):
                        quote(1000, 200, coupon)

    def test_enabled_must_be_bool(self):
        for value in (0, 1, "true", "false", None, [], 1.0):
            with self.subTest(value=value):
                coupon = {"discount": 300, "minimum": 1000, "enabled": value}
                with self.assertRaisesRegex(TypeError, r"^coupon\.enabled "):
                    quote(1000, 200, coupon)

    def test_disabled_coupon_amounts_are_still_validated(self):
        for field, value in product(
            ("discount", "minimum"), self.INVALID_AMOUNTS + (-1,)
        ):
            with self.subTest(field=field, value=value):
                coupon = {"discount": 300, "minimum": 1000, "enabled": False}
                coupon[field] = value
                expected_error = ValueError if type(value) is int else TypeError
                with self.assertRaises(expected_error) as error:
                    quote(1000, 200, coupon)
                self.assertTrue(
                    str(error.exception).startswith("coupon." + field + " ")
                )

    def test_unqualified_coupon_is_still_validated(self):
        cases = (
            ({"discount": True, "minimum": 1000, "enabled": True}, TypeError),
            ({"discount": -1, "minimum": 1000, "enabled": True}, ValueError),
            ({"discount": 300, "minimum": "1000", "enabled": True}, TypeError),
            ({"discount": 300, "minimum": 1000, "enabled": 0}, TypeError),
            ({"discount": 300, "minimum": 1000}, ValueError),
            ({"discount": 300, "minimum": 1000, "enabled": True, "x": 1}, ValueError),
        )
        for coupon, expected_error in cases:
            with self.subTest(coupon=coupon):
                with self.assertRaises(expected_error):
                    quote(0, 200, coupon)

    def test_validation_order(self):
        cases = (
            (True, -1, {}, TypeError, "subtotal"),
            (-1, False, [], ValueError, "subtotal"),
            (1000, False, [], TypeError, "shipping"),
            (1000, -1, {}, ValueError, "shipping"),
            (1000, 200, [], TypeError, "coupon"),
            (1000, 200, {"discount": True}, ValueError, "coupon keys"),
            (1000, 200, {"discount": True, "minimum": -1, "enabled": 0},
             TypeError, "coupon.discount"),
            (1000, 200, {"discount": -1, "minimum": True, "enabled": 0},
             ValueError, "coupon.discount"),
            (1000, 200, {"discount": 300, "minimum": True, "enabled": 0},
             TypeError, "coupon.minimum"),
            (1000, 200, {"discount": 300, "minimum": -1, "enabled": 0},
             ValueError, "coupon.minimum"),
            (1000, 200, {"discount": 300, "minimum": 1000, "enabled": 0},
             TypeError, "coupon.enabled"),
        )
        for subtotal, shipping, coupon, expected_error, path in cases:
            with self.subTest(subtotal=subtotal, shipping=shipping, coupon=coupon):
                with self.assertRaises(expected_error) as error:
                    quote(subtotal, shipping, coupon)
                self.assertTrue(str(error.exception).startswith(path + " "))

    def test_mapping_variants_unchanged_after_repeated_quotes(self):
        class FalseyMapping(UserDict):
            def __bool__(self):
                return False

        for subtotal, enabled, expected in (
            (1000, True, 900), (1000, False, 1200), (999, True, 1199)
        ):
            for factory in (dict, MappingProxyType, UserDict, FalseyMapping):
                with self.subTest(subtotal=subtotal, enabled=enabled, factory=factory):
                    original = {"discount": 300, "minimum": 1000, "enabled": enabled}
                    snapshot = original.copy()
                    coupon = factory(original)
                    self.assertEqual(quote(subtotal, 200, coupon), expected)
                    self.assertEqual(quote(subtotal, 200, coupon), expected)
                    self.assertEqual(dict(coupon), snapshot)
                    self.assertEqual(original, snapshot)

    def test_coupon_unchanged_after_validation_failure(self):
        for coupon, expected_error in (
            ({"discount": -1, "minimum": 1000, "enabled": False}, ValueError),
            ({"discount": True, "minimum": 1000, "enabled": False}, TypeError),
            ({"discount": 300, "minimum": 1000}, ValueError),
        ):
            with self.subTest(coupon=coupon):
                snapshot = coupon.copy()
                with self.assertRaises(expected_error):
                    quote(1000, 200, coupon)
                self.assertEqual(coupon, snapshot)

    def test_integer_subclass_is_allowed(self):
        class Amount(int):
            pass

        coupon = {"discount": Amount(300), "minimum": Amount(1000), "enabled": True}
        self.assertEqual(quote(Amount(1000), Amount(200), coupon), 900)

    def test_total_bounds_and_undiscounted_cases(self):
        for subtotal, shipping, discount, minimum, enabled in product(
            (0, 1, 999, 1000, 10**30), (0, 200),
            (0, 1, 1000, 10**30 + 1), (0, 1000), (True, False)
        ):
            with self.subTest(
                subtotal=subtotal, shipping=shipping, discount=discount,
                minimum=minimum, enabled=enabled
            ):
                coupon = {"discount": discount, "minimum": minimum, "enabled": enabled}
                total = quote(subtotal, shipping, coupon)
                self.assertIs(type(total), int)
                self.assertGreaterEqual(total, shipping)
                self.assertLessEqual(total, subtotal + shipping)
                if not enabled or subtotal < minimum:
                    self.assertEqual(total, subtotal + shipping)
                self.assertEqual(quote(subtotal, shipping), subtotal + shipping)

    def test_shipping_only_increases_total(self):
        coupons = (
            None,
            {"discount": 300, "minimum": 1000, "enabled": False},
            {"discount": 300, "minimum": 1000, "enabled": True},
            {"discount": 5000, "minimum": 0, "enabled": True},
        )
        for subtotal, coupon, increase in product((0, 999, 1000), coupons, (0, 1, 10000)):
            with self.subTest(subtotal=subtotal, coupon=coupon, increase=increase):
                base = quote(subtotal, 200, coupon)
                self.assertEqual(quote(subtotal, 200 + increase, coupon), base + increase)


if __name__ == "__main__":
    unittest.main()
