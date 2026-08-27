"""Thresholds and patterns for reading money out of a Spanish answer."""

import re
from decimal import Decimal

# A run of digits with optional thousands/decimal separators, always ending on a digit.
AMOUNT_TOKEN = re.compile(r"\d[\d.,]*\d|\d")

# A separator followed by exactly this many digits at the end of a token is a decimal point.
DECIMAL_TAIL_DIGITS = 2

# Below this, a bare number in an answer is an identifier or a count, not a money figure.
MONETARY_FLOOR = Decimal(100)
