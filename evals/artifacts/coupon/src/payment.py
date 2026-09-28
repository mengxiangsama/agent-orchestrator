from collections.abc import Mapping


def payable(subtotal, shipping):
    """Existing synthetic code; this evaluation starts with a design-only request."""
    return subtotal + shipping


def _validate_amount(value, field):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"{field} must be a non-negative integer (bool is not allowed)"
        )
    if value < 0:
        raise ValueError(f"{field} must be non-negative")


def quote(subtotal, shipping, coupon=None):
    """Return the total in integer cents, applying a coupon only to goods."""
    _validate_amount(subtotal, "subtotal")
    _validate_amount(shipping, "shipping")

    applied_discount = 0
    if coupon is not None:
        if not isinstance(coupon, Mapping):
            raise TypeError("coupon must be a Mapping or None")
        keys = tuple(coupon)
        if any(not isinstance(key, str) for key in keys) or set(keys) != {
            "discount", "minimum", "enabled"
        }:
            raise ValueError(
                "coupon keys must be exactly discount, minimum, enabled"
            )

        discount = coupon["discount"]
        _validate_amount(discount, "coupon.discount")
        minimum = coupon["minimum"]
        _validate_amount(minimum, "coupon.minimum")
        enabled = coupon["enabled"]
        if type(enabled) is not bool:
            raise TypeError("coupon.enabled must be a bool")

        if enabled and subtotal >= minimum:
            applied_discount = min(discount, subtotal)

    return subtotal - applied_discount + shipping
