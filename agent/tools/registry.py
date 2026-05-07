"""
Central tool registry.
NOW INCLUDES REAL API TOOLS.
"""

import logging
from agent.tools.math_tools import calculate, CALCULATE_SCHEMA
from agent.tools.search_tools import search_product, SEARCH_PRODUCT_SCHEMA
from agent.tools.search_tools import compare_products, COMPARE_PRODUCTS_SCHEMA
from agent.tools.real_api_tools import convert_currency, CURRENCY_CONVERTER_SCHEMA
from agent.tools.real_api_tools import get_weather, WEATHER_SCHEMA

logger = logging.getLogger(__name__)

# ── Tool Registry ─────────────────────────────────────
TOOL_REGISTRY = {
    "calculate": (calculate, CALCULATE_SCHEMA),
    "search_product": (search_product, SEARCH_PRODUCT_SCHEMA),
    "compare_products": (compare_products, COMPARE_PRODUCTS_SCHEMA),
    "convert_currency": (convert_currency, CURRENCY_CONVERTER_SCHEMA),
    "get_weather": (get_weather, WEATHER_SCHEMA),
}

# ── Allowlist ─────────────────────────────────────────
ALLOWED_TOOLS = {
    "calculate",
    "search_product",
    "compare_products",
    "convert_currency",
    "get_weather",
    "final_answer",
}

def get_tool_descriptions() -> str:
    """Generates tool descriptions for system prompt."""
    lines = ["Available tools (respond with JSON to call them):"]
    
    for name, (_, schema) in TOOL_REGISTRY.items():
        desc = schema["description"]
        lines.append(f"\n- {name}: {desc[:120]}...")
    
    lines.append("\n- final_answer: Return your final answer to the user.")
    return "\n".join(lines)

def run_tool(tool_name: str, tool_input: str) -> str:
    """Central tool runner with allowlist enforcement."""
    if tool_name not in ALLOWED_TOOLS:
        msg = f"Tool '{tool_name}' is not permitted."
        logger.warning(f"BLOCKED: {tool_name}")
        return msg
    
    if tool_name == "final_answer":
        return tool_input
    
    if tool_name not in TOOL_REGISTRY:
        return f"Tool '{tool_name}' not found"
    
    executor, _ = TOOL_REGISTRY[tool_name]
    logger.info(f"Executing: {tool_name}('{tool_input[:50]}')")
    
    try:
        result = executor(tool_input)
        logger.info(f"Tool '{tool_name}' result: {str(result)[:100]}")
        return str(result)
    except Exception as e:
        msg = f"Unexpected error in '{tool_name}': {e}"
        logger.error(msg, exc_info=True)
        return msg