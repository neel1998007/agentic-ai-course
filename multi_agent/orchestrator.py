# multi_agent/orchestrator.py

import logging
from groq import Groq
from config.settings import LLM_MODEL
from .planner import create_plan
from .supervisor import run_supervised_plan, SUPERVISOR_CONFIG

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Synthesizer: combines all executor outputs
# ─────────────────────────────────────────────

SYNTHESIZER_SYSTEM_PROMPT = """You are a synthesis assistant.

You receive:
1. The original user goal
2. Results from multiple specialized executor agents

Your job: combine the executor results into ONE clear, helpful final answer.

Rules:
- Use ONLY information from the executor results. Do not invent facts.
- If some tasks failed, acknowledge this honestly. 
  Example: "I could not retrieve weather data, but here is what I found..."
- Format the answer for a regular user (not a developer).
- For Indian users: use ₹ for prices, mention GST where relevant.
- Be concise but complete. Aim for 150-300 words.
"""


def synthesize_results(
    original_goal: str,
    plan_state,
    client: Groq,
) -> str:
    """
    Call LLM to synthesize executor results into final answer.
    
    Builds a context block from all task results (success and failure)
    and asks the synthesizer LLM to combine them.
    """
    logger.info("[ORCHESTRATOR] Synthesizing results...")

    # Build context from all results
    context_parts = []
    for task_id, result in plan_state.results.items():
        task = plan_state.tasks[task_id]
        status_str = "SUCCESS" if result.success else "FAILED"
        context_parts.append(
            f"[{task_id} - {status_str}]\n"
            f"Task: {task.description}\n"
            f"Result: {result.output}\n"
        )

    context = "\n---\n".join(context_parts)

    success_rate = plan_state.get_success_rate()
    if success_rate < SUPERVISOR_CONFIG["min_success_rate"]:
        logger.warning(
            f"[ORCHESTRATOR] Low success rate ({success_rate:.0%}). "
            f"Synthesis may be incomplete."
        )

    synthesis_prompt = (
        f"ORIGINAL GOAL:\n{original_goal}\n\n"
        f"EXECUTOR RESULTS:\n{context}\n\n"
        f"Please synthesize the above into a final answer for the user."
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": synthesis_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Synthesis failed: {e}")
        # Fallback: just concatenate the successful results
        successful = [
            f"{r.task_id}: {r.output}"
            for r in plan_state.results.values()
            if r.success
        ]
        if successful:
            return "Partial answer (synthesis unavailable):\n\n" + "\n\n".join(successful)
        return "All tasks failed. Unable to provide an answer."


# ─────────────────────────────────────────────
# Main entry point for multi-agent system
# ─────────────────────────────────────────────

def run_multi_agent(
    goal: str,
    client: Groq,
    critical_task_ids: list = None,
) -> str:
    """
    Full multi-agent pipeline:
      1. Planner   → create task plan
      2. Supervisor → execute tasks with failure handling
      3. Synthesizer → combine results into final answer
    
    Args:
        goal             : user's original goal (string)
        client           : shared Groq client
        critical_task_ids: task IDs that must succeed (optional)
    
    Returns:
        Final answer string (always returns something, even on partial failure)
    
    Reliability guarantees:
        - Planner failure → returns error message immediately
        - Executor failures → supervisor retries, then continues
        - Synthesis failure → fallback concatenation
        - Never raises exception to caller
    """
    logger.info("=" * 60)
    logger.info(f"[ORCHESTRATOR] New multi-agent run")
    logger.info(f"[ORCHESTRATOR] Goal: {goal[:100]}...")
    logger.info("=" * 60)

    # ── Step 1: Planning ──
    tasks = create_plan(goal, client)

    if not tasks:
        logger.error("[ORCHESTRATOR] Planning failed. Aborting.")
        return "I was unable to create a plan for this goal. Please try rephrasing."

    logger.info(f"[ORCHESTRATOR] Plan created with {len(tasks)} tasks:")
    for t in tasks:
        deps = f" (needs: {t.depends_on})" if t.depends_on else ""
        logger.info(f"  {t.task_id}: {t.description[:60]}{deps}")

    # ── Step 2: Supervised Execution ──
    plan_state = run_supervised_plan(
        tasks=tasks,
        client=client,
        critical_task_ids=critical_task_ids or [],
    )

    logger.info(f"[ORCHESTRATOR] Execution complete: {plan_state.summary()}")

    # ── Step 3: Synthesis ──
    final_answer = synthesize_results(goal, plan_state, client)

    logger.info("[ORCHESTRATOR] Multi-agent run complete")
    logger.info(f"[ORCHESTRATOR] Total steps across all executors: {plan_state.total_steps}")

    return final_answer