# multi_agent/supervisor.py

import logging
from groq import Groq
from .planner import PlannedTask
from .executor import ExecutionResult, execute_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Supervisor configuration
# ─────────────────────────────────────────────

SUPERVISOR_CONFIG = {
    "max_retries_per_task": 1,      # retry a failed task at most once
    "min_success_rate": 0.5,        # if < 50% tasks succeed, abort synthesis
    "critical_task_ids": [],        # task IDs that MUST succeed (set by orchestrator)
}


# ─────────────────────────────────────────────
# Execution plan state (what supervisor tracks)
# ─────────────────────────────────────────────

class PlanExecutionState:
    """
    Tracks the state of all tasks during execution.
    Supervisor reads and writes this.
    """
    def __init__(self, tasks: list):
        self.tasks = {t.task_id: t for t in tasks}
        self.results = {}           # task_id → ExecutionResult
        self.retry_counts = {}      # task_id → int
        self.total_steps = 0        # across all executors

    def get_pending_tasks(self) -> list:
        """Return tasks whose dependencies are all done and are still pending."""
        ready = []
        for task in self.tasks.values():
            if task.status != "pending":
                continue
            # Check all dependencies are done
            deps_done = all(
                self.tasks.get(dep, PlannedTask("", "", [], [], 3)).status == "done"
                for dep in task.depends_on
            )
            if deps_done:
                ready.append(task)
        return sorted(ready, key=lambda t: t.priority)

    def mark_done(self, task_id: str, result: ExecutionResult):
        self.tasks[task_id].status = "done"
        self.tasks[task_id].result = result.output
        self.results[task_id] = result
        self.total_steps += result.steps

    def mark_failed(self, task_id: str, result: ExecutionResult):
        self.tasks[task_id].status = "failed"
        self.results[task_id] = result
        self.total_steps += result.steps

    def get_success_rate(self) -> float:
        if not self.results:
            return 0.0
        successes = sum(1 for r in self.results.values() if r.success)
        return successes / len(self.results)

    def all_tasks_resolved(self) -> bool:
        """True when no task is still pending or running."""
        return all(
            t.status in ("done", "failed")
            for t in self.tasks.values()
        )

    def summary(self) -> str:
        done = sum(1 for t in self.tasks.values() if t.status == "done")
        failed = sum(1 for t in self.tasks.values() if t.status == "failed")
        total = len(self.tasks)
        return f"{done}/{total} tasks done, {failed} failed, {self.total_steps} total steps"


# ─────────────────────────────────────────────
# Supervisor: runs plan, handles failures
# ─────────────────────────────────────────────

def run_supervised_plan(
    tasks: list,
    client: Groq,
    critical_task_ids: list = None,
) -> PlanExecutionState:
    """
    Execute all tasks in the plan with supervision.
    
    Execution strategy:
    1. Find tasks whose dependencies are satisfied (ready tasks).
    2. Run them (sequentially for now — parallel in Lesson 9).
    3. If a task fails: retry once (with a simplified goal).
    4. If a critical task fails after retry: abort entire plan.
    5. If non-critical task fails after retry: continue with rest.
    6. Continue until all tasks are resolved.
    
    Args:
        tasks            : list of PlannedTask from planner
        client           : shared Groq client
        critical_task_ids: task IDs that must succeed (if any fail → abort)
    
    Returns:
        PlanExecutionState with all results.
    """
    if not tasks:
        logger.error("[SUPERVISOR] No tasks to execute")
        return PlanExecutionState([])

    critical_task_ids = critical_task_ids or []
    state = PlanExecutionState(tasks)

    logger.info(f"[SUPERVISOR] Starting plan execution: {len(tasks)} tasks")
    logger.info(f"[SUPERVISOR] Critical tasks: {critical_task_ids or 'none'}")

    iteration = 0
    max_iterations = len(tasks) * 3  # safety: prevent infinite loops

    while not state.all_tasks_resolved() and iteration < max_iterations:
        iteration += 1

        # Get tasks ready to run
        ready_tasks = state.get_pending_tasks()

        if not ready_tasks:
            # Could mean: circular dependency, or all remaining tasks have failed deps
            logger.warning("[SUPERVISOR] No tasks are ready. Checking for stuck tasks...")
            _handle_stuck_tasks(state)
            break

        logger.info(f"[SUPERVISOR] Iteration {iteration}: {len(ready_tasks)} task(s) ready")

        for task in ready_tasks:
            task.status = "running"
            logger.info(f"[SUPERVISOR] Running {task.task_id}...")

            result = execute_task(task, client)

            if result.success:
                state.mark_done(task.task_id, result)
                logger.info(f"[SUPERVISOR] ✓ {task.task_id} succeeded")

            else:
                # First failure: check retry budget
                retry_count = state.retry_counts.get(task.task_id, 0)

                if retry_count < SUPERVISOR_CONFIG["max_retries_per_task"]:
                    logger.warning(
                        f"[SUPERVISOR] {task.task_id} failed. "
                        f"Retrying ({retry_count + 1}/{SUPERVISOR_CONFIG['max_retries_per_task']})..."
                    )
                    state.retry_counts[task.task_id] = retry_count + 1

                    # Simplify the task for retry
                    task.description = _simplify_task_for_retry(task.description)
                    task.status = "pending"  # re-queue it

                else:
                    # Out of retries
                    state.mark_failed(task.task_id, result)
                    logger.error(f"[SUPERVISOR] ✗ {task.task_id} failed after retries")

                    if task.task_id in critical_task_ids:
                        logger.error(
                            f"[SUPERVISOR] Critical task {task.task_id} failed. "
                            f"Aborting plan."
                        )
                        # Mark all remaining pending tasks as failed
                        _abort_remaining_tasks(state)
                        return state

    logger.info(f"[SUPERVISOR] Plan execution complete. {state.summary()}")
    return state


def _simplify_task_for_retry(description: str) -> str:
    """
    When a task fails, simplify the goal for retry.
    Strategy: add explicit instruction to use simpler inputs and be minimal.
    """
    return (
        f"{description}\n"
        f"[RETRY MODE: Use the simplest possible tool inputs. "
        f"If still unsure, return whatever partial information you have.]"
    )


def _handle_stuck_tasks(state: PlanExecutionState):
    """
    If no tasks are ready but some are still pending, 
    it means their dependencies all failed.
    Mark those as failed too.
    """
    from multi_agent.executor import ExecutionResult
    
    for task in state.tasks.values():
        if task.status == "pending":
            logger.warning(
                f"[SUPERVISOR] {task.task_id} stuck (dependencies failed). Marking failed."
            )
            state.mark_failed(
                task.task_id,
                ExecutionResult(
                    task_id=task.task_id,
                    success=False,
                    output="Skipped: dependencies failed",
                    steps=0,
                )
            )


def _abort_remaining_tasks(state: PlanExecutionState):
    """Mark all pending/running tasks as failed due to critical task failure."""
    from multi_agent.executor import ExecutionResult
    
    for task in state.tasks.values():
        if task.status in ("pending", "running"):
            state.mark_failed(
                task.task_id,
                ExecutionResult(
                    task_id=task.task_id,
                    success=False,
                    output="Aborted: critical task failed",
                    steps=0,
                )
            )