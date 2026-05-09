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


def test_real_api_tools():
    """Test real API tools before running agent."""
    from agent.tools import run_tool
    
    print("\n🧪 Testing Real API Tools")
    print("─" * 40)
    
    # Test currency conversion (no auth needed)
    print("Testing currency conversion...")
    result = run_tool("convert_currency", "1000 INR to USD")
    print(f"✅ Currency: {result}\n")
    
    # Test weather (needs API key)
    print("Testing weather lookup...")
    result = run_tool("get_weather", "Mumbai")
    print(f"✅ Weather: {result}\n")
    
    print("✅ All real API tools working\n")


def safe_run_agent(goal: str):
    """
    Wrapper for run_agent that ensures consistent return format.
    Handles both old (string return) and new (tuple return) formats.
    """
    from agent.core import run_agent
    
    result = run_agent(goal)
    
    # Check what we got back
    if isinstance(result, tuple) and len(result) == 3:
        # New format: (answer, status, steps)
        return result
    elif isinstance(result, str):
        # Old format: just answer string
        return result, "SUCCESS", 1
    else:
        # Unknown format
        return str(result), "UNKNOWN", 1


def run_single_agent_demo():
    """Run single-agent examples from previous lessons."""
    print("\n" + "=" * 60)
    print("SINGLE-AGENT DEMO (Lessons 5-7)")
    print("=" * 60)
    
    goals = [
        "What is 5000 INR in USD?",
        "What's the weather like in Delhi?",
        "If I have 10000 INR and exchange it to USD, how much will I get?",
    ]
    
    for goal in goals:
        print(f"\n{'─'*50}")
        print(f"🎯 Goal: {goal}")
        
        # Use safe wrapper
        answer, status, steps = safe_run_agent(goal)
        
        print(f"✅ Answer: {answer}")
        print(f"   Status: {status}, Steps: {steps}")


def run_multi_agent_demo():
    """Demo of multi-agent system for India-relevant buying decision."""
    import os
    from groq import Groq
    from multi_agent.orchestrator import run_multi_agent
    
    print("\n" + "=" * 60)
    print("MULTI-AGENT DEMO (Lesson 8)")
    print("=" * 60)

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    # Goal that naturally decomposes into multiple tasks
    goal = (
        "Help me decide on a laptop under ₹60,000. "
        "Search for available options, convert 800 USD to INR "
        "so I understand if US prices are better, "
        "and check the weather in Delhi because I want to know "
        "if I should visit Nehru Place market today."
    )

    final_answer = run_multi_agent(goal=goal, client=client)

    print("\n" + "─" * 60)
    print("FINAL SYNTHESIZED ANSWER:")
    print("─" * 60)
    print(final_answer)
    print("─" * 60)


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("Agent session started")
    logger.info("=" * 50)
    
    # Test tools first
    test_real_api_tools()
    
    # Run single-agent demo
    run_single_agent_demo()
    
    # Run multi-agent demo
    run_multi_agent_demo()
    
    logger.info("Agent session ended")


if __name__ == "__main__":
    main()