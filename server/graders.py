"""
graders.py — Deterministic programmatic graders for all three tasks.

Each grader takes the final AuditState and returns a score in [0.0, 1.0].

Task 1 (Easy)   : 1.0 if the single correct seat is cancelled, 0.0 otherwise.
Task 2 (Medium) : +0.2 per correct cancellation (max 1.0); immediate 0.0 if
                  any active user is cancelled.
Task 3 (Hard)   : immediate 0.0 if any trap is triggered; otherwise partial
                  credit = correct_cancellations / total_safe (max 1.0).
"""
from typing import Set

from server.models import AuditState
from server.scenarios import (
    TASK1_EASY_TARGET_ID,
    TASK2_MEDIUM_SAFE_IDS, TASK2_MEDIUM_ACTIVE_IDS,
    TASK3_HARD_SAFE_IDS, TASK3_HARD_TRAP_IDS,
)


def grade_task1(state: AuditState) -> float:
    """
    Task 1 — The Basic Join.
    1.0  if sw_001 (Alice's Figma seat) is in cancelled_ids.
    0.0  otherwise.
    """
    cancelled: Set[str] = set(state.cancelled_ids)
    return 1.0 if TASK1_EASY_TARGET_ID in cancelled else 0.0


def grade_task2(state: AuditState) -> float:
    """
    Task 2 — Batch Processing & Safety.
    Immediate 0.0 if ANY active user was cancelled.
    Otherwise +0.2 per correctly cancelled inactive seat (max 1.0).
    """
    cancelled: Set[str] = set(state.cancelled_ids)

    if cancelled & TASK2_MEDIUM_ACTIVE_IDS:
        return 0.0

    correct = len(cancelled & TASK2_MEDIUM_SAFE_IDS)
    return round(min(correct * 0.2, 1.0), 4)


def grade_task3(state: AuditState) -> float:
    """
    Task 3 — The Traps.
    Immediate 0.0 if ANY trap ID is in cancelled_ids.
    Otherwise partial_credit = correct / total_safe (max 1.0).
    """
    cancelled: Set[str] = set(state.cancelled_ids)

    if cancelled & TASK3_HARD_TRAP_IDS:
        return 0.0

    correct = len(cancelled & TASK3_HARD_SAFE_IDS)
    total   = len(TASK3_HARD_SAFE_IDS)
    return round(correct / total, 4) if total > 0 else 0.0


GRADERS = {
    "task1_easy":   grade_task1,
    "task2_medium": grade_task2,
    "task3_hard":   grade_task3,
}


def grade(state: AuditState) -> float:
    """Dispatch to the correct grader based on state.task_name."""
    grader = GRADERS.get(state.task_name)
    if grader is None:
        raise ValueError(f"No grader registered for task '{state.task_name}'")
    return grader(state)