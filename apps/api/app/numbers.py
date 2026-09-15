"""Display form of decimals shared by every surface: no float, no exponent, no spurious trailing zeros."""

from __future__ import annotations

from decimal import Decimal


def decimal_text(value: Decimal | None, *, min_decimals: int = 2) -> str | None:
    """`Decimal('1000.000000')` -> `'1000.00'`, `Decimal('1.123456')` -> `'1.123456'`, `Decimal('0.010000')` -> `'0.01'`."""
    if value is None:
        return None
    text = format(value.normalize(), "f")
    if text in ("-0", ""):
        text = "0"
    whole, _, fraction = text.partition(".")
    if len(fraction) < min_decimals:
        fraction = fraction.ljust(min_decimals, "0")
    return f"{whole}.{fraction}" if fraction else whole
