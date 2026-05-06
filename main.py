"""
Entry point. Sets up logging. Tests tools. Runs agent.
"""

import logging
import sys
from config.settings import LOG_LEVEL, LOG_FILE


def setup_logging():
    """Configure logging for the whole application."""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt     = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S"
    )
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def test_tools():
    """
    Quick sanity check — test all tools directly
    before running the agent.
    Catches tool bugs early, before LLM is involved.
    """
    from agent.tools import run_tool

    print("\n🧪 Tool Sanity Tests")
    print("─" * 40)

    tests = [
        # (tool_name, input, expected_substring)
        ("calculate",       "79900 * 0.15",          "11985"),
        ("calculate",       "79,900 * 0.15",          "11985"),   # comma handling
        ("calculate",       "₹79900 * 0.15",          "11985"),   # currency symbol
        ("search_product",  "iPhone 15",              "79,900"),
        ("search_product",  "unknown product xyz",    "No product found"),
        ("compare_products","iPhone 15 vs Samsung S24","cheaper"),
        ("blocked_tool",    "anything",               "not permitted"),  # allowlist test
    ]

    passed = 0
    failed = 0

    for tool_name, tool_input, expected in tests:
        result = run_tool(tool_name, tool_input)
        ok     = expected.lower() in result.lower()
        status = "✅" if ok else "❌"
        print(f"  {status} {tool_name}('{tool_input[:30]}')")
        if not ok:
            print(f"     Expected '{expected}' in result")
            print(f"     Got: '{result}'")
            failed += 1
        else:
            passed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    from agent.core import run_agent

    logger.info("=" * 50)
    logger.info("Agent session started")
    logger.info("=" * 50)

    # Run tool tests first
    all_passed = test_tools()
    if not all_passed:
        logger.error("Tool tests failed. Fix tools before running agent.")
        return

    print("\n✅ All tool tests passed. Starting agent...\n")

    # Agent goals
    goals = [
        "What is 18% GST on iPhone 15?",
        "Which is cheaper — Samsung S24 or Pixel 8, and by how much?",
        "What is the battery difference between iPhone 15 and Pixel 8?",
    ]

    for goal in goals:
        print(f"\n{'─'*50}")
        print(f"🎯 Goal: {goal}")
        result = run_agent(goal)
        print(f"✅ Answer: {result}")

    logger.info("Agent session ended")


if __name__ == "__main__":
    main()