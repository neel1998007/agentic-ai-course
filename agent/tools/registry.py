"""
Central tool registry.
This is the ONLY place where tools are registered.
The agent imports from here — never from individual tool files.

Security: Only tools in ALLOWED_TOOLS can be executed.
"""

import logging
from agent.tools.math_tools   import calculate,        CALCULATE_SCHEMA
from agent.tools.search_tools import search_product,   SEARCH_PRODUCT_SCHEMA
from agent.tools.search_tools import compare_products, COMPARE_PRODUCTS_SCHEMA

logger = logging.getLogger(__name__)


# ── Tool Registry ─────────────────────────────────────
# Maps tool name → (executor function, schema)
TOOL_REGISTRY = {
    "calculate"      : (calculate,        CALCULATE_SCHEMA),
    "search_product" : (search_product,   SEARCH_PRODUCT_SCHEMA),
    "compare_products": (compare_products, COMPARE_PRODUCTS_SCHEMA),
}

# ── Allowlist ─────────────────────────────────────────
# ONLY tools in this set can be executed.
# Remove a tool from here to disable it without
# deleting its code.
ALLOWED_TOOLS = {
    "calculate",
    "search_product",
    "compare_products",
    "final_answer",     # always allowed — agent must be able to stop
}


def get_tool_descriptions() -> str:
    """
    Generates tool descriptions for the system prompt.
    Auto-updates when you add tools to registry.
    Never hardcode tool descriptions in prompts.
    """
    lines = ["Available tools (respond with JSON to call them):"]

    for name, (_, schema) in TOOL_REGISTRY.items():
        desc   = schema["description"]
        params = schema["parameters"]

        # Get first parameter description
        param_desc = ""
        for param_name, param_info in params.items():
            examples = schema.get("examples", [])
            example_str = ""
            if examples:
                example_str = f" Example input: '{examples[0]['input']}'"
            param_desc = (
                f"  Input: {param_info['description'][:100]}..."
                f"{example_str}"
            )

        lines.append(f"\n- {name}: {desc[:120]}...")
        lines.append(param_desc)

    lines.append("\n- final_answer: Return your final answer to the user.")
    lines.append("  Input: Your complete answer as a string.")

    return "\n".join(lines)


def run_tool(tool_name: str, tool_input: str) -> str:
    """
    Central tool runner with allowlist enforcement.

    Steps:
    1. Check allowlist → block if not permitted
    2. Look up in registry → error if not found
    3. Execute → catch any unexpected errors
    4. Return string result always
    """
    # ── Allowlist check ───────────────────────────────
    if tool_name not in ALLOWED_TOOLS:
        msg = (
            f"Tool '{tool_name}' is not permitted. "
            f"Allowed tools: {sorted(ALLOWED_TOOLS)}. "
            f"Use only the tools listed in your instructions."
        )
        logger.warning(f"BLOCKED tool call: '{tool_name}' | Input: '{tool_input}'")
        return msg

    # ── final_answer is handled by agent loop ─────────
    if tool_name == "final_answer":
        return tool_input

    # ── Registry lookup ───────────────────────────────
    if tool_name not in TOOL_REGISTRY:
        msg = (
            f"Tool '{tool_name}' not found in registry. "
            f"Available: {list(TOOL_REGISTRY.keys())}"
        )
        logger.error(msg)
        return msg

    # ── Execute ───────────────────────────────────────
    executor, _ = TOOL_REGISTRY[tool_name]
    logger.info(f"Executing tool: {tool_name}('{tool_input[:50]}')")

    try:
        result = executor(tool_input)
        logger.info(f"Tool '{tool_name}' result: {str(result)[:100]}")
        return str(result)      # always return string
    except Exception as e:
        # Belt and suspenders — tools should never raise
        # but we catch here anyway
        msg = f"Unexpected error in '{tool_name}': {type(e).__name__}: {e}"
        logger.error(msg, exc_info=True)
        return msg