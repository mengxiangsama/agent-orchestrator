from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
import importlib.util
import unittest

MODULE = Path(__file__).resolve().parents[1] / "src" / "payment.py"
SPEC = importlib.util.spec_from_file_location("quote_under_review", MODULE)
payment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(payment)


class QuoteContract(unittest.TestCase):
    def test_original_payable_is_preserved(self):
        self.assertEqual(120, payment.payable(100, 20))

    def test_no_coupon_disabled_and_threshold(self):
        self.assertEqual(120, payment.quote(100, 20))
        cases = [(100, 20, 30, 100, False, 120), (99, 20, 30, 100, True, 119),
                 (100, 20, 30, 100, True, 90), (90, 20, 30, 100, True, 110)]
        for subtotal, shipping, discount, minimum, enabled, expected in cases:
            with self.subTest(case=(subtotal, shipping, discount, minimum, enabled)):
                self.assertEqual(expected, payment.quote(subtotal, shipping,
                    {"discount": discount, "minimum": minimum, "enabled": enabled}))

    def test_coupon_never_discounts_shipping(self):
        self.assertEqual(20, payment.quote(100, 20,
            {"discount": 1000, "minimum": 0, "enabled": True}))

    def test_zero_and_large_integer(self):
        self.assertEqual(0, payment.quote(0, 0, {"discount": 50, "minimum": 0, "enabled": True}))
        self.assertEqual(10**30 + 4, payment.quote(10**30, 7,
            {"discount": 3, "minimum": 0, "enabled": True}))

    def test_invalid_amounts_even_for_disabled_coupon(self):
        for field in ("subtotal", "shipping", "discount", "minimum"):
            for value in (True, False, 1.0, "1", None, [], Decimal("1"), -1):
                with self.subTest(field=field, value=value):
                    args = {"subtotal": 100, "shipping": 20,
                            "coupon": {"discount": 30, "minimum": 50, "enabled": False}}
                    if field in ("subtotal", "shipping"):
                        args[field] = value
                    else:
                        args["coupon"][field] = value
                    with self.assertRaises((TypeError, ValueError)):
                        payment.quote(**args)

    def test_invalid_coupon_container_and_shape(self):
        cases = [False, 0, [], "coupon", {}, {"discount": 1, "minimum": 0},
                 {"discount": 1, "minimum": 0, "enabled": True, "extra": 1}]
        for coupon in cases:
            with self.subTest(coupon=coupon):
                with self.assertRaises((TypeError, ValueError)):
                    payment.quote(100, 20, coupon)

    def test_enabled_must_be_boolean(self):
        for value in (0, 1, "false", None):
            with self.subTest(enabled=value):
                with self.assertRaises(TypeError):
                    payment.quote(100, 20, {"discount": 1, "minimum": 0, "enabled": value})

    def test_mapping_is_not_mutated_and_result_is_stable(self):
        coupon = {"discount": 30, "minimum": 100, "enabled": True}
        self.assertEqual(90, payment.quote(100, 20, MappingProxyType(coupon)))
        self.assertEqual(90, payment.quote(100, 20, coupon))
        self.assertEqual({"discount": 30, "minimum": 100, "enabled": True}, coupon)

    def test_valid_result_bounds(self):
        for subtotal in (0, 1, 100, 1000):
            for shipping in (0, 1, 20):
                for discount in (0, 1, 2000):
                    result = payment.quote(subtotal, shipping,
                        {"discount": discount, "minimum": 0, "enabled": True})
                    self.assertIs(type(result), int)
                    self.assertLessEqual(shipping, result)
                    self.assertLessEqual(result, subtotal + shipping)


if __name__ == "__main__":
    unittest.main()
