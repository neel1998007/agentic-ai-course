"""
Math-related tools.
Each tool: validates input → executes → returns string.
"""

import logging
from agent.tools.validator import validate_math_expression, ValidationError

logger = logging.getLogger(__name__)


# ── Tool Schema ───────────────────────────────────────
CALCULATE_SCHEMA = {
    "name": "calculate",
    "description": (
        "Evaluates a mathematical expression and returns the numeric result. "
        "Use this for ANY arithmetic calculation: addition, subtraction, "
        "multiplication, division, percentages, powers. "
        "Also use for: calculating discounts, tax amounts (GST), "
        "currency conversion math, splitting bills, loan EMI estimates."
    ),
    "parameters": {
        "expression": {
            "type"       : "string",
            "description": (
                "A valid math expression using numbers and operators only. "
                "Operators: + (add), - (subtract), * (multiply), "
                "/ (divide), ** (power), % (modulo). "
                "Examples: '79900 * 0.18' for 18% GST on 79900. "
                "'(1000 + 500) / 3' for splitting a bill. "
                "Do NOT include: currency symbols, commas in numbers, "
                "variable names, or function names."
            ),
            "required"   : True,
        }
    },
    "examples": [
        {"input": "79900 * 0.15",    "output": "11985.0"},
        {"input": "(500 + 200) / 3", "output": "233.333..."},
        {"input": "2 ** 10",         "output": "1024"},
    ]
}


# ── Tool Executor ─────────────────────────────────────
def calculate(expression: str) -> str:
    """
    Safely evaluates a math expression.

    Input : math expression string
    Output: result as string, or error message string
    """
    logger.debug(f"calculate called with: '{expression}'")

    # Step 1: Validate and clean input
    try:
        clean_expr = validate_math_expression(expression)
    except ValidationError as e:
        logger.warning(f"calculate validation failed: {e}")
        return f"Calculation error: {e}"

    # Step 2: Execute safely
    try:
        result = eval(
            clean_expr,
            {"__builtins__": {}},
            {}
        )
        # Format result cleanly
        if isinstance(result, float) and result.is_integer():
            formatted = str(int(result))
        elif isinstance(result, float):
            formatted = f"{result:.4f}".rstrip('0').rstrip('.')
        else:
            formatted = str(result)

        logger.info(f"calculate: '{clean_expr}' = {formatted}")
        return f"{formatted}"

    except ZeroDivisionError:
        logger.warning(f"calculate: division by zero in '{clean_expr}'")
        return "Calculation error: division by zero"

    except Exception as e:
        logger.error(f"calculate: unexpected error: {e}")
        return (
            f"Calculation error: could not evaluate '{clean_expr}'. "
            f"Please check the expression format."
        )