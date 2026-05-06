"""
Input validation utilities for tools.
Validate BEFORE executing — fail fast, fail clearly.
"""

import re
from typing import Any


class ValidationError(Exception):
    """Raised when tool input fails validation."""
    pass


def validate_string(
    value     : Any,
    field_name: str,
    min_length: int = 1,
    max_length: int = 500,
) -> str:
    """
    Validates that a value is a non-empty string
    within length bounds.
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"'{field_name}' must be a string, "
            f"got {type(value).__name__}"
        )
    value = value.strip()
    if len(value) < min_length:
        raise ValidationError(
            f"'{field_name}' is too short "
            f"(min {min_length} characters)"
        )
    if len(value) > max_length:
        raise ValidationError(
            f"'{field_name}' is too long "
            f"(max {max_length} characters, "
            f"got {len(value)})"
        )
    return value


def validate_math_expression(expression: str) -> str:
    """
    Validates a math expression is safe to evaluate.
    Rejects anything with letters (except 'e' for scientific).
    Rejects anything that looks like code injection.

    Returns cleaned expression or raises ValidationError.
    """
    # Remove commas from numbers (common LLM mistake)
    # e.g. "79,900 * 0.15" → "79900 * 0.15"
    expression = expression.replace(",", "")

    # Remove currency symbols
    # e.g. "₹79900 * 0.15" → "79900 * 0.15"
    expression = re.sub(r'[₹$€£¥]', '', expression)

    # Strip whitespace
    expression = expression.strip()

    # Reject if contains letters (except 'e' for scientific notation)
    # e.g. "import os" → rejected
    # e.g. "1e5 * 2"   → allowed (scientific notation)
    if re.search(r'[a-df-zA-DF-Z_]', expression):
        raise ValidationError(
            f"Expression contains invalid characters: '{expression}'. "
            f"Use only numbers and operators (+, -, *, /, **, %). "
            f"Example: '79900 * 0.15'"
        )

    # Reject empty after cleaning
    if not expression:
        raise ValidationError(
            "Expression is empty after cleaning. "
            "Provide a valid math expression like '100 * 0.18'"
        )

    # Reject suspiciously long expressions
    if len(expression) > 200:
        raise ValidationError(
            f"Expression too long ({len(expression)} chars). "
            f"Max 200 characters."
        )

    return expression


def validate_product_query(query: str) -> str:
    """
    Validates a product search query.
    """
    query = validate_string(query, "query", min_length=2, max_length=100)

    # Reject if looks like code or injection
    suspicious = ["import", "exec", "eval", "__", "os.", "sys."]
    query_lower = query.lower()
    for pattern in suspicious:
        if pattern in query_lower:
            raise ValidationError(
                f"Query contains invalid content: '{pattern}'. "
                f"Please enter a product name like 'iPhone 15'"
            )

    return query