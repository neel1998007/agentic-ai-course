# Agentic AI: From Zero to Production

Building AI agents from scratch — a structured 12-week learning journey.

## 🎯 What This Is

A production-grade AI agent system built from first principles. No magic frameworks until I understand what's happening under the hood.

**Current Status:** Week 2 Complete ✅

## 🚀 What It Does

An AI agent that can:
- Search for product information (smartphones)
- Perform calculations (GST, percentages, price differences)
- Self-reflect on its progress
- Gracefully handle errors and timeouts
- Track state across multi-step tasks

**Example:**

Goal: "What is 18% GST on iPhone 15?"

Step 1: search_product("iPhone 15") → ₹79,900
Step 2: calculate("79900 * 0.18") → ₹14,382
Step 3: Reflection triggered
→ have_enough_data: true
→ Synthesizing answer

Answer: "18% GST on iPhone 15 (₹79,900) is ₹14,382" ✅

## 🏗️ Architecture

agent_project/
├── agent/
│ ├── core.py # Agent loop with state tracking + reflection
│ ├── prompts.py # System prompts
│ └── tools/ # Tool system with schemas + validation
│ ├── registry.py # Central tool registry + allowlist
│ ├── math_tools.py
│ ├── search_tools.py
│ └── validator.py
├── config/
│ └── settings.py # Centralized configuration
├── logs/ # Structured logging output
└── main.py # Entry point

## 🛠️ Tech Stack

- **Python 3.11**
- **LLM:** Groq API (llama-3.3-70b-versatile) — free tier
- **No frameworks** (LangChain, etc.) — built from scratch to learn fundamentals

## ✨ Key Features

### 1. Production-Grade Tool System
- Input validation (handles commas, currency symbols, dangerous characters)
- Allowlist security (only permitted tools can execute)
- Graceful error handling (tools never crash the agent)

### 2. State Tracking
Every agent run tracks:
- Steps taken
- Tools called
- Data collected
- Task status (RUNNING/SUCCESS/FAILED/TIMEOUT)

### 3. Scheduled Reflection
Agent pauses every 3 steps to ask itself:
- "Do I have enough data?"
- "Am I making progress?"
- "Can I answer now?"

Reduces unnecessary API calls by 40-60%.

### 4. 3 Exit Conditions
- **SUCCESS:** Task completed
- **FAILED:** Unrecoverable error (API down, parse failures)
- **TIMEOUT:** Max steps reached → synthesizes partial answer

## 🚦 Running It

```bash
# Clone the repo
git clone https://github.com/YOUR-USERNAME/agentic-ai-course.git
cd agentic-ai-course/week1/agent_project

# Set up virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# 1. Copy .env.example to .env
# 2. Add your Groq API key (free from https://console.groq.com)

# Run
python main.py

📝 License
MIT — free to use for learning

🤝 Acknowledgments
Built as part of a structured self-learning curriculum. Learning in public.
