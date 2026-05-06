"""
Controlled agent loop with:
- Full state tracking
- Scheduled reflection
- 3 explicit exit conditions
- Progress detection
"""

import json
import time
import logging
from enum import Enum
from dataclasses import dataclass, field

from groq import Groq
from groq import RateLimitError, APITimeoutError, APIError

from config.settings import (LLM_MODEL, LLM_TEMPERATURE,
                              LLM_MAX_TOKENS, AGENT_MAX_STEPS,
                              AGENT_MAX_RETRIES, GROQ_API_KEY)
from agent.prompts   import get_agent_system_prompt
from agent.tools     import run_tool

logger = logging.getLogger(__name__)
client = Groq(api_key=GROQ_API_KEY)


# ─────────────────────────────────────────────────────
# STATE DEFINITIONS
# ─────────────────────────────────────────────────────

class TaskStatus(Enum):
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILED   = "failed"
    TIMEOUT  = "timeout"


@dataclass
class AgentState:
    """
    Complete state of a running agent.
    Everything the agent knows about the current task.
    """
    goal           : str
    status         : TaskStatus        = TaskStatus.RUNNING
    step           : int               = 0
    seen_actions   : set               = field(default_factory=set)
    collected_data : list              = field(default_factory=list)
    reflection_notes: list             = field(default_factory=list)
    parse_failures : int               = 0
    final_answer   : str               = ""
    error_message  : str               = ""

    def summary(self) -> str:
        """Returns a readable summary of current state."""
        return (
            f"Step {self.step}/{AGENT_MAX_STEPS} | "
            f"Status: {self.status.value} | "
            f"Data collected: {len(self.collected_data)} items | "
            f"Actions taken: {len(self.seen_actions)}"
        )


# ─────────────────────────────────────────────────────
# LLM CALLER
# ─────────────────────────────────────────────────────

def call_llm_with_retry(messages: list) -> str | None:
    """LLM call with exponential backoff retry."""
    for attempt in range(AGENT_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model       = LLM_MODEL,
                messages    = messages,
                temperature = LLM_TEMPERATURE,
                max_tokens  = LLM_MAX_TOKENS,
            )
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                logger.warning("LLM output cut off (finish_reason=length)")

            return response.choices[0].message.content.strip()

        except RateLimitError:
            wait = 2 ** attempt
            logger.warning(f"Rate limit. Waiting {wait}s...")
            time.sleep(wait)

        except APITimeoutError:
            wait = 2 ** attempt
            logger.warning(f"Timeout. Waiting {wait}s...")
            time.sleep(wait)

        except APIError as e:
            logger.error(f"API error: {e}")
            if attempt == AGENT_MAX_RETRIES - 1:
                return None
            time.sleep(2 ** attempt)

    logger.error("All LLM retries failed")
    return None


# ─────────────────────────────────────────────────────
# OUTPUT PARSER
# ─────────────────────────────────────────────────────

def parse_llm_output(raw_output: str) -> dict | None:
    """Parse LLM JSON output with fallback extraction."""
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', raw_output, re.DOTALL)
        if match:
            try:
                extracted = json.loads(match.group())
                logger.warning("JSON extracted from non-pure output")
                return extracted
            except json.JSONDecodeError:
                pass
        logger.error(f"Failed to parse: {raw_output[:200]}")
        return None


# ─────────────────────────────────────────────────────
# REFLECTION
# ─────────────────────────────────────────────────────

REFLECTION_PROMPT = """You are reviewing your own progress on a task.

Original goal: {goal}

Data collected so far:
{collected_data}

Actions taken so far:
{actions_taken}

Answer these questions in JSON only:
{{
  "have_enough_data": true or false,
  "making_progress": true or false,
  "next_focus": "what should I focus on next",
  "can_answer_now": true or false
}}
"""


def run_reflection(state: AgentState) -> dict:
    """
    Agent reflects on its own progress.
    Returns reflection assessment.
    """
    logger.info(f"Running reflection at step {state.step}")

    # Build reflection context
    collected_str = "\n".join([
        f"  - {item['tool']}: {item['result'][:100]}"
        for item in state.collected_data
    ]) or "  None yet"

    actions_str = "\n".join([
        f"  - {action}"
        for action in state.seen_actions
    ]) or "  None yet"

    reflection_messages = [
        {
            "role": "system",
            "content": "You are a self-assessment agent. Respond only in valid JSON."
        },
        {
            "role": "user",
            "content": REFLECTION_PROMPT.format(
                goal          = state.goal,
                collected_data= collected_str,
                actions_taken = actions_str,
            )
        }
    ]

    output = call_llm_with_retry(reflection_messages)
    if not output:
        return {"have_enough_data": False, "making_progress": True,
                "next_focus": "continue", "can_answer_now": False}

    reflection = parse_llm_output(output)
    if not reflection:
        return {"have_enough_data": False, "making_progress": True,
                "next_focus": "continue", "can_answer_now": False}

    logger.info(f"Reflection result: {reflection}")
    state.reflection_notes.append(reflection)
    return reflection


# ─────────────────────────────────────────────────────
# SYNTHESIS — Build final answer from collected data
# ─────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """You are finalizing an answer for a user.

Original goal: {goal}

Data collected:
{collected_data}

Write a clear, concise final answer for the user.
Use specific numbers and facts from the data collected.
Do not make up information not in the data.
Respond with plain text — no JSON needed here.
"""


def synthesize_answer(state: AgentState) -> str:
    """
    Builds a final answer from collected data
    when reflection says we have enough information.
    """
    logger.info("Synthesizing answer from collected data")

    collected_str = "\n".join([
        f"- {item['tool']}: {item['result']}"
        for item in state.collected_data
    ])

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Be concise and specific."
        },
        {
            "role": "user",
            "content": SYNTHESIS_PROMPT.format(
                goal          = state.goal,
                collected_data= collected_str,
            )
        }
    ]

    answer = call_llm_with_retry(messages)
    return answer or "Could not synthesize answer from collected data."


# ─────────────────────────────────────────────────────
# MAIN AGENT LOOP
# ─────────────────────────────────────────────────────

# How often to run reflection (every N steps)
REFLECT_EVERY = 3


def run_agent(user_goal: str) -> str:
    """
    Controlled agent loop with state tracking and reflection.

    EXIT CONDITIONS:
    1. SUCCESS : LLM calls final_answer OR reflection says can_answer_now
    2. FAILED  : API down, repeated parse failures, critical tool error
    3. TIMEOUT : Max steps reached
    """
    # ── Initialize State ──────────────────────────────
    state = AgentState(goal=user_goal)
    logger.info(f"Agent started. Goal: {user_goal}")

    # ── Initialize Messages ───────────────────────────
    messages = [
        {"role": "system", "content": get_agent_system_prompt()},
        {"role": "user",   "content": user_goal},
    ]

    # ── Main Loop ─────────────────────────────────────
    while state.step < AGENT_MAX_STEPS:
        state.step += 1
        logger.info(f"── Step {state.step}/{AGENT_MAX_STEPS} ── {state.summary()}")

        # ── SCHEDULED REFLECTION ──────────────────────
        # Every REFLECT_EVERY steps, pause and reflect
        if state.step > 1 and state.step % REFLECT_EVERY == 0:
            reflection = run_reflection(state)

            if reflection.get("can_answer_now"):
                logger.info("Reflection: have enough data → synthesizing answer")
                answer = synthesize_answer(state)
                state.status       = TaskStatus.SUCCESS
                state.final_answer = answer
                return answer

            if not reflection.get("making_progress"):
                logger.warning("Reflection: not making progress → nudging agent")
                messages.append({
                    "role": "user",
                    "content": (
                        f"You have taken {state.step} steps. "
                        f"Reflection shows limited progress. "
                        f"Focus on: {reflection.get('next_focus', 'completing the task')}. "
                        f"If you have enough information, use final_answer now."
                    )
                })

        # ── LLM CALL ──────────────────────────────────
        llm_output = call_llm_with_retry(messages)

        # EXIT 2: API completely down
        if llm_output is None:
            state.status        = TaskStatus.FAILED
            state.error_message = "LLM API unavailable after all retries"
            logger.error(state.error_message)
            return "Agent error: could not reach LLM. Please try again."

        # ── PARSE OUTPUT ──────────────────────────────
        decision = parse_llm_output(llm_output)

        if decision is None:
            state.parse_failures += 1
            logger.warning(f"Parse failure #{state.parse_failures}")

            # EXIT 2: Too many parse failures
            if state.parse_failures >= 2:
                state.status        = TaskStatus.FAILED
                state.error_message = "LLM not following output format"
                logger.error(state.error_message)
                return "Agent error: LLM not following output format."

            messages.append({"role": "assistant", "content": llm_output})
            messages.append({
                "role": "user",
                "content": (
                    'Respond with ONLY valid JSON. '
                    'Example: {"tool": "search_product", "input": "iPhone 15"}'
                )
            })
            continue

        state.parse_failures = 0
        tool_name  = decision.get("tool", "")
        tool_input = decision.get("input", "")

        # EXIT 1: Final answer from LLM
        if tool_name == "final_answer":
            state.status       = TaskStatus.SUCCESS
            state.final_answer = tool_input
            logger.info(f"SUCCESS in {state.step} steps: {tool_input}")
            return tool_input

        # ── REASONING LOOP DETECTION ──────────────────
        action_key = f"{tool_name}:{tool_input}"
        if action_key in state.seen_actions:
            logger.warning(f"Loop detected: {action_key}")
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({
                "role": "user",
                "content": (
                    f"You already called {tool_name}('{tool_input}'). "
                    f"Do not repeat. Use collected data to answer now."
                )
            })
            continue

        state.seen_actions.add(action_key)

        # ── RUN TOOL ──────────────────────────────────
        tool_result = run_tool(tool_name, tool_input)
        logger.info(f"Tool result: {tool_result[:100]}")

        # ── COLLECT DATA ──────────────────────────────
        state.collected_data.append({
            "step"  : state.step,
            "tool"  : tool_name,
            "input" : tool_input,
            "result": tool_result,
        })

        # ── UPDATE MESSAGES ───────────────────────────
        messages.append({"role": "assistant", "content": llm_output})
        messages.append({
            "role": "user",
            "content": (
                f"Tool result: {tool_result}\n"
                f"What is your next step?"
            )
        })

        # ── APPROACHING LIMIT ─────────────────────────
        if state.step == AGENT_MAX_STEPS - 2:
            logger.warning("Approaching max steps")
            messages.append({
                "role": "user",
                "content": (
                    "You have 2 steps remaining. "
                    "You MUST call final_answer on your next step."
                )
            })

    # EXIT 3: Timeout — return best partial answer
    state.status = TaskStatus.TIMEOUT
    logger.error(f"Timeout after {AGENT_MAX_STEPS} steps")

    if state.collected_data:
        logger.info("Attempting synthesis from partial data")
        return synthesize_answer(state)

    return "Agent timed out without collecting enough information."