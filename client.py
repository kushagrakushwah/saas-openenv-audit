"""
Typed Pydantic models for the SaaS Audit environment.
Follows the OpenEnv spec: Action, Observation, State base classes.
"""
from typing import Any, Dict, List, Optional
from openenv.core.env_server import Action, Observation, State


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

class AuditAction(Action):
    """
    The agent's discrete tool call each step.

    tool: one of
        "get_employee_logins"     → returns all employee login records
        "get_billing_line_items"  → returns all active subscription seats
        "query_software_metadata" → metadata for a specific software_id
        "check_contract_terms"    → contract + penalty info for a software_id
        "execute_cancellation"    → cancel a seat/subscription by software_id
        "finish"                  → agent signals task complete

    software_id: required for query_software_metadata, check_contract_terms,
                 execute_cancellation. Ignored otherwise.
    """
    tool: str
    software_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class AuditObservation(Observation):
    """
    What the agent receives after each action.

    tool_result         : JSON payload from the called tool.
    last_action_error   : human-readable error string, or None if no error.
    step                : step counter within this episode.
    done                : whether the episode has ended.
    reward              : reward earned THIS step (partial signal).
    """
    tool_result: Dict[str, Any] = {}
    last_action_error: Optional[str] = None
    step: int = 0
    done: bool = False
    reward: float = 0.0
    metadata: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# State  (internal ground-truth — exposed at /state endpoint)
# ---------------------------------------------------------------------------

class AuditState(State):
    episode_id: Optional[str] = None
    step_count: int = 0
    task_name: str = "task1_easy"
    cancelled_ids: List[str] = []
    total_savings: float = 0.0
    penalty_points: float = 0.0
    # trap flags
    critical_service_cancelled: bool = False
    early_cancellation_penalty_triggered: bool = False
    # grader score (0.0–1.0) — set when done=True
    grader_score: float = 0.0