# multi_agent/executor.py

import logging
from groq import Groq
from .planner import PlannedTask

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Execution result container
# ─────────────────────────────────────────────

class ExecutionResult:
    """
    Result from running one PlannedTask.
    
    Fields:
        task_id  : which task this result belongs to
        success  : did it complete without FAILED status?
        output   : string output (agent's final answer or error message)
        steps    : how many agent steps were used
    """
    def __init__(self, task_id: str, success: bool, output: str, steps: int):
        self.task_id = task_id
        self.success = success
        self.output = output
        self.steps = steps

    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"ExecutionResult({status} {self.task_id}, steps={self.steps})"


# ─────────────────────────────────────────────
# Executor: runs a single PlannedTask
# ─────────────────────────────────────────────

def execute_task(task: PlannedTask, client: Groq, max_steps: int = 6) -> ExecutionResult:
    """
    Run one PlannedTask using the single-agent loop.
    
    Args:
        task       : PlannedTask to execute
        client     : Groq client (shared, avoids creating new connection per task)
        max_steps  : step budget for this executor (default 6, less than main agent)
    
    Returns:
        ExecutionResult with success/failure and output.
    """
    logger.info(f"[EXECUTOR] Starting task {task.task_id}: {task.description[:60]}")

    # Build executor-specific goal
    executor_goal = _build_executor_goal(task)

    try:
        # Use safe wrapper to handle return format inconsistencies
        from agent.core import run_agent
        
        result = run_agent(executor_goal)
        
        # Handle both old (string) and new (tuple) return formats
        if isinstance(result, tuple) and len(result) == 3:
            final_answer, status, steps_used = result
        elif isinstance(result, str):
            final_answer = result
            status = "SUCCESS"
            steps_used = 1
        else:
            final_answer = str(result)
            status = "SUCCESS" 
            steps_used = 1

        success = (status == "SUCCESS")

        if success:
            logger.info(f"[EXECUTOR] Task {task.task_id} completed in {steps_used} steps")
        else:
            logger.warning(f"[EXECUTOR] Task {task.task_id} ended with status={status}")

        return ExecutionResult(
            task_id=task.task_id,
            success=success,
            output=final_answer,
            steps=steps_used,
        )

    except Exception as e:
        logger.error(f"[EXECUTOR] Task {task.task_id} crashed: {e}")
        return ExecutionResult(
            task_id=task.task_id,
            success=False,
            output=f"Executor crashed: {str(e)}",
            steps=0,
        )


def _build_executor_goal(task: PlannedTask) -> str:
    """
    Build the goal string passed to run_agent.
    Enriches task description with instructions for executor behavior.
    """
    tools_str = ", ".join(task.tools_hint) if task.tools_hint else "any available tool"

    goal = (
        f"{task.description}\n\n"
        f"INSTRUCTIONS FOR THIS SUBTASK:\n"
        f"- Preferred tools: {tools_str}\n"
        f"- Be concise. Return only the key facts needed.\n"
        f"- Do NOT ask for more information. Work with what is given.\n"
        f"- If a tool fails once, try a slightly different input. "
        f"If it fails twice, report what you found so far."
    )

    return goal