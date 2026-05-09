# multi_agent/planner.py

import json
import logging
from groq import Groq
from config.settings import LLM_MODEL

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data structure for a single planned task
# ─────────────────────────────────────────────

class PlannedTask:
    """
    Represents one subtask created by the Planner.
    
    Fields:
        task_id     : unique identifier, e.g. "task_1"
        description : what this task should accomplish (plain English)
        tools_hint  : which tools the executor should prefer
        depends_on  : list of task_ids that must complete first
                      (empty = can run immediately)
        priority    : 1 (high) to 3 (low), affects execution order
    """

    def __init__(self, task_id: str, description: str,
                 tools_hint: list, depends_on: list, priority: int):
        self.task_id = task_id
        self.description = description
        self.tools_hint = tools_hint        # e.g. ["search_product", "compare_products"]
        self.depends_on = depends_on        # e.g. [] or ["task_1"]
        self.priority = priority            # 1=high, 2=medium, 3=low
        self.status = "pending"             # pending | running | done | failed
        self.result = None                  # filled after execution

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "description": self.description,
            "tools_hint": self.tools_hint,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "status": self.status,
        }

    def __repr__(self):
        return f"PlannedTask({self.task_id}, priority={self.priority}, status={self.status})"


# ─────────────────────────────────────────────
# Planner: calls LLM, returns list of PlannedTask
# ─────────────────────────────────────────────

PLANNER_SYSTEM_PROMPT = """You are a task planning assistant for an AI agent system.

Your job: decompose a user's goal into a small number of independent subtasks
that specialized executor agents can handle.

AVAILABLE TOOLS (executors can use these):
- calculate         : math calculations
- search_product    : search product database by name
- compare_products  : compare two products from database
- convert_currency  : convert between currencies (needs: from_currency, to_currency, amount)
- get_weather       : get weather for a city (needs: city name)

RULES:
1. Output ONLY valid JSON. No explanation, no markdown, no extra text.
2. Maximum 5 tasks. If goal needs more, merge related tasks.
3. Each task must be achievable with 1-3 tool calls.
4. depends_on: list task_ids that must finish BEFORE this task starts.
   Use [] if task can start immediately.
5. tools_hint: suggest which tools to use (executor may adapt).
6. priority: 1=must do first, 2=normal, 3=nice to have

OUTPUT FORMAT (strict):
{
  "plan_summary": "one sentence describing overall strategy",
  "tasks": [
    {
      "task_id": "task_1",
      "description": "clear description of what to do",
      "tools_hint": ["tool_name_1", "tool_name_2"],
      "depends_on": [],
      "priority": 1
    }
  ]
}
"""


def create_plan(goal: str, client: Groq) -> list:
    """
    Call LLM to decompose goal into PlannedTask list.
    
    Returns:
        List of PlannedTask objects, ordered by priority.
        Empty list if planning fails.
    
    Failure modes handled:
        - LLM returns non-JSON → log + return empty plan
        - LLM returns JSON with wrong structure → log + return empty plan
        - LLM creates > 5 tasks → truncate with warning
        - API error → log + return empty plan
    """
    logger.info(f"[PLANNER] Creating plan for goal: {goal[:80]}...")

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Goal: {goal}"}
            ],
            temperature=0.2,        # Low temperature: we want consistent, structured output
            max_tokens=1000,
        )

        raw_output = response.choices[0].message.content.strip()
        logger.debug(f"[PLANNER] Raw LLM output:\n{raw_output}")

        # ── Parse JSON ──
        plan_data = _parse_plan_json(raw_output)
        if plan_data is None:
            return []

        # ── Validate and convert to PlannedTask objects ──
        tasks = _validate_and_build_tasks(plan_data)

        logger.info(f"[PLANNER] Plan created: {len(tasks)} tasks")
        for t in tasks:
            logger.info(f"  {t.task_id} (priority={t.priority}): {t.description[:60]}")

        return tasks

    except Exception as e:
        logger.error(f"[PLANNER] Failed to create plan: {e}")
        return []


def _parse_plan_json(raw_output: str) -> dict | None:
    """
    Try to extract valid JSON from LLM output.
    Handles cases where LLM adds markdown fences.
    """
    # Remove markdown fences if present
    cleaned = raw_output
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"[PLANNER] JSON parse failed: {e}")
        logger.error(f"[PLANNER] Raw was: {raw_output[:200]}")
        return None


def _validate_and_build_tasks(plan_data: dict) -> list:
    """
    Validate plan structure and build PlannedTask objects.
    Returns empty list if structure is wrong.
    """
    if "tasks" not in plan_data:
        logger.error("[PLANNER] Plan missing 'tasks' key")
        return []

    raw_tasks = plan_data["tasks"]

    if not isinstance(raw_tasks, list):
        logger.error("[PLANNER] 'tasks' is not a list")
        return []

    # Enforce max 5 tasks
    if len(raw_tasks) > 5:
        logger.warning(f"[PLANNER] LLM created {len(raw_tasks)} tasks, truncating to 5")
        raw_tasks = raw_tasks[:5]

    tasks = []
    for i, raw in enumerate(raw_tasks):
        try:
            task = PlannedTask(
                task_id=str(raw.get("task_id", f"task_{i+1}")),
                description=str(raw.get("description", "No description")),
                tools_hint=raw.get("tools_hint", []),
                depends_on=raw.get("depends_on", []),
                priority=int(raw.get("priority", 2)),
            )
            tasks.append(task)
        except Exception as e:
            logger.warning(f"[PLANNER] Skipping malformed task {i}: {e}")

    # Sort by priority (1 first, then 2, then 3)
    tasks.sort(key=lambda t: t.priority)

    return tasks