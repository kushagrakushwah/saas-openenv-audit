"""
models.py — Typed Pydantic models for the SaaS Audit environment.

Uses plain Pydantic BaseModel — avoids coupling to any specific version of
openenv-core's internal base classes, which vary across releases and are
the root cause of the 422 Unprocessable Entity errors when the Action model
fields cannot be deserialized from the raw request body.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

class AuditAction(BaseModel):
    """
    The agent's discrete tool call each step.

    tool: one of
        "get_employee_logins"      → returns all employee login records
        "get_billing_line_items"   → returns all active subscription seats
        "query_software_metadata"  → metadata for a specific software_id
        "check_contract_terms"     → contract + penalty info for a software_id
        "execute_cancellation"     → cancel a seat/subscription by software_id
        "finish"                   → agent signals task complete

    software_id: required for query_software_metadata, check_contract_terms,
                 execute_cancellation. Ignored otherwise.
    """
    tool: str
    software_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------

class AuditObservation(BaseModel):
    """
    What the agent receives after each action.

    tool_result         : JSON payload from the called tool.
    last_action_error   : human-readable error string, or None if no error.
    step                : step counter within this episode.
    done                : whether the episode has ended.
    reward              : reward earned THIS step (partial signal).
    metadata            : optional extra key-value pairs.
    """
    tool_result: Dict[str, Any] = Field(default_factory=dict)
    last_action_error: Optional[str] = None
    step: int = 0
    done: bool = False
    reward: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# State  (internal ground-truth — exposed at GET /{task}/state)
# ---------------------------------------------------------------------------

class AuditState(BaseModel):
    """
    Full internal state of the environment.
    """
    episode_id: Optional[str] = None
    step_count: int = 0
    task_name: str = "task1_easy"
    cancelled_ids: List[str] = Field(default_factory=list)
    total_savings: float = 0.0
    penalty_points: float = 0.0
    critical_service_cancelled: bool = False
    early_cancellation_penalty_triggered: bool = False
    grader_score: float = 0.0