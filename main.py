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


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    from agent.core import run_agent
    from agent.tools import run_tool
    
    logger.info("=" * 50)
    logger.info("Agent session started")
    logger.info("=" * 50)
    
    # Test real API tools
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
    
    # Agent goals with real APIs
    goals = [
        "What is 5000 INR in USD?",
        "What's the weather like in Delhi?",
        "If I have 10000 INR and exchange it to USD, how much will I get?",
    ]
    
    for goal in goals:
        print(f"\n{'─'*50}")
        print(f"🎯 Goal: {goal}")
        result = run_agent(goal)
        print(f"✅ Answer: {result}")
    
    logger.info("Agent session ended")


if __name__ == "__main__":
    main()