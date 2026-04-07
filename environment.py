"""
environment.py — SaaS Audit Environment core logic.

Implements the OpenEnv server-side interface:
    reset()     → AuditObservation        (clean new episode)
    step()      → AuditObservation        (advance one step)
    get_state() → AuditState              (internal ground-truth)

Not coupled to any web framework — app.py wires HTTP routes manually.
Reward signal is shaped throughout each episode for partial progress;
the authoritative grader score is computed on finish / timeout.
"""
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

from models import AuditAction, AuditObservation, AuditState
from scenarios import SCENARIOS, MAX_STEPS, TASK_PROMPTS
from graders import grade


AVAILABLE_TOOLS = [
    "get_employee_logins",
    "get_billing_line_items",
    "query_software_metadata",
    "check_contract_terms",
    "execute_cancellation",
    "finish",
]


class AuditEnvironment:

    def __init__(self, task_name: str = "task1_easy"):
        assert task_name in SCENARIOS, (
            f"task_name must be one of {list(SCENARIOS)}"
        )
        self.task_name = task_name
        self._reset_internals()

    # ------------------------------------------------------------------
    # Public OpenEnv interface
    # ------------------------------------------------------------------

    def reset(self) -> AuditObservation:
        self._reset_internals()
        return AuditObservation(
            tool_result={
                "message": "Episode started. New SaaS audit session initialised.",
                "task": TASK_PROMPTS[self.task_name],
                "available_tools": AVAILABLE_TOOLS,
                "hint": (
                    "Start with get_employee_logins and get_billing_line_items "
                    "to gather data. Use software_id with the metadata/contract/"
                    "cancellation tools. Call finish when done."
                ),
            },
            step=0,
            done=False,
            reward=0.0,
        )

    def step(self, action: AuditAction) -> AuditObservation:
        self._steps += 1

        if self._done:
            return AuditObservation(
                tool_result={"message": "Episode already ended. Call reset()."},
                step=self._steps,
                done=True,
                reward=0.0,
            )

        if self._steps > MAX_STEPS[self.task_name]:
            return self._end_episode(
                reason="Maximum steps exceeded — episode terminated."
            )

        tool = (action.tool or "").strip().lower()

        dispatch = {
            "get_employee_logins":     self._tool_get_logins,
            "get_billing_line_items":  self._tool_get_billing,
            "query_software_metadata": lambda: self._tool_query_metadata(action.software_id),
            "check_contract_terms":    lambda: self._tool_check_contract(action.software_id),
            "execute_cancellation":    lambda: self._tool_cancel(action.software_id),
            "finish":                  self._tool_finish,
        }

        handler = dispatch.get(tool)
        if handler is None:
            return AuditObservation(
                tool_result={},
                last_action_error=(
                    f"Unknown tool '{action.tool}'. "
                    f"Valid tools: {', '.join(AVAILABLE_TOOLS)}"
                ),
                step=self._steps,
                done=False,
                reward=0.0,
            )

        return handler()

    def get_state(self) -> AuditState:
        return AuditState(
            episode_id=self._episode_id,
            step_count=self._steps,
            task_name=self.task_name,
            cancelled_ids=list(self._cancelled_ids),
            total_savings=round(self._savings, 2),
            penalty_points=round(self._penalty, 4),
            critical_service_cancelled=self._critical_cancelled,
            early_cancellation_penalty_triggered=self._early_cancel_triggered,
            grader_score=self._grader_score,
        )

    # ------------------------------------------------------------------
    # Private — internal state management
    # ------------------------------------------------------------------

    def _reset_internals(self):
        self._episode_id: str = str(uuid.uuid4())
        self._steps: int = 0
        self._done: bool = False
        self._db: List[Dict] = deepcopy(SCENARIOS[self.task_name])
        self._cancelled_ids: Set[str] = set()
        self._checked_contract_ids: Set[str] = set()
        self._savings: float = 0.0
        self._penalty: float = 0.0
        self._critical_cancelled: bool = False
        self._early_cancel_triggered: bool = False
        self._grader_score: float = 0.0
        self._target_savings: float = sum(
            s["monthly_cost"] for s in self._db if s.get("is_safe_to_cancel")
        )

    def _get_sw(self, software_id: Optional[str]) -> Optional[Dict]:
        if not software_id:
            return None
        for s in self._db:
            if s["id"] == software_id and s["id"] not in self._cancelled_ids:
                return s
        return None

    def _end_episode(self, reason: str = "finish") -> AuditObservation:
        self._done = True
        self._grader_score = grade(self.get_state())
        return AuditObservation(
            tool_result={
                "message":                      reason,
                "total_monthly_savings_usd":    round(self._savings, 2),
                "cancelled_ids":                list(self._cancelled_ids),
                "grader_score":                 self._grader_score,
                "critical_service_cancelled":   self._critical_cancelled,
                "early_cancellation_triggered": self._early_cancel_triggered,
            },
            step=self._steps,
            done=True,
            reward=self._grader_score,
        )

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def _tool_get_logins(self) -> AuditObservation:
        records = []
        for s in self._db:
            if s["id"] not in self._cancelled_ids:
                records.append({
                    "software_id":           s["id"],
                    "software_name":         s["name"],
                    "days_since_last_login": s["days_since_last_login"],
                    "active_within_30d":     s["days_since_last_login"] <= 30,
                    "department":            s.get("department", "Unknown"),
                })
        return AuditObservation(
            tool_result={"employee_login_records": records,
                         "total_seats": len(records)},
            step=self._steps,
            done=False,
            reward=0.0,
        )

    def _tool_get_billing(self) -> AuditObservation:
        items = []
        for s in self._db:
            if s["id"] not in self._cancelled_ids:
                items.append({
                    "software_id":      s["id"],
                    "software_name":    s["name"],
                    "monthly_cost_usd": s["monthly_cost"],
                    "contract_type":    s["contract_type"],
                    "department":       s.get("department", "Unknown"),
                })
        total = sum(i["monthly_cost_usd"] for i in items)
        return AuditObservation(
            tool_result={"billing_line_items": items,
                         "total_monthly_spend_usd": round(total, 2),
                         "currency": "USD"},
            step=self._steps,
            done=False,
            reward=0.0,
        )

    def _tool_query_metadata(self, software_id: Optional[str]) -> AuditObservation:
        sw = self._get_sw(software_id)
        if not sw:
            return AuditObservation(
                tool_result={},
                last_action_error=f"software_id '{software_id}' not found or already cancelled.",
                step=self._steps,
                done=False,
                reward=0.0,
            )

        result: Dict[str, Any] = {
            "software_id":           sw["id"],
            "software_name":         sw["name"],
            "service_type":          sw["service_type"],
            "contract_type":         sw["contract_type"],
            "monthly_cost_usd":      sw["monthly_cost"],
            "days_since_last_login": sw["days_since_last_login"],
            "department":            sw.get("department", "Unknown"),
            "owner_email":           (
                f"{sw['department'].lower()}@company.com"
                if sw.get("department") else "unknown@company.com"
            ),
        }
        if sw["service_type"] == "service_account":
            result["warning"] = (
                "WARNING: HEADLESS SERVICE ACCOUNT — automated system dependency "
                "(no human users). DO NOT cancel."
            )
        if sw.get("note"):
            result["note"] = sw["note"]

        return AuditObservation(
            tool_result=result,
            step=self._steps,
            done=False,
            reward=0.0,
        )

    def _tool_check_contract(self, software_id: Optional[str]) -> AuditObservation:
        sw = self._get_sw(software_id)
        if not sw:
            return AuditObservation(
                tool_result={},
                last_action_error=f"software_id '{software_id}' not found or already cancelled.",
                step=self._steps,
                done=False,
                reward=0.0,
            )

        self._checked_contract_ids.add(software_id)
        fee = sw.get("early_cancel_fee", 0.0)
        months_remaining = 6 if sw["contract_type"] == "annual" else 0

        recommendation = (
            f"Annual contract. Early cancellation fee: ${fee:,.2f}. NOT recommended to cancel."
            if fee > 0
            else "No early-cancellation penalty. Safe to cancel if seat is inactive."
        )

        return AuditObservation(
            tool_result={
                "software_id":               sw["id"],
                "software_name":             sw["name"],
                "contract_type":             sw["contract_type"],
                "months_remaining_in_term":  months_remaining,
                "early_cancellation_fee_usd": fee,
                "recommendation":            recommendation,
            },
            step=self._steps,
            done=False,
            reward=0.0,
        )

    def _tool_cancel(self, software_id: Optional[str]) -> AuditObservation:
        sw = self._get_sw(software_id)

        if not sw:
            return AuditObservation(
                tool_result={"message": f"'{software_id}' not found or already cancelled."},
                last_action_error=f"software_id '{software_id}' not found or already cancelled.",
                step=self._steps,
                done=False,
                reward=0.0,
            )

        # Mark cancelled immediately (mirrors real-world irreversible API call)
        self._cancelled_ids.add(software_id)

        # Trap 1: Critical service account
        if sw.get("is_critical"):
            self._critical_cancelled = True
            self._penalty += 1.0
            return self._end_episode(
                reason=(
                    "CRITICAL FAILURE — You cancelled a headless service account. "
                    "Company CI/CD / backup pipeline has been disrupted. Episode terminated."
                )
            )

        # Trap 2: Annual contract with early-cancel penalty
        if sw["contract_type"] == "annual" and sw.get("early_cancel_fee", 0) > 0:
            self._early_cancel_triggered = True
            self._penalty += 0.5
            checked = software_id in self._checked_contract_ids
            note = (
                "You checked contract terms first, but cancelled anyway."
                if checked
                else "You did NOT check contract terms before cancelling."
            )
            return self._end_episode(
                reason=(
                    f"Annual contract trap triggered. "
                    f"Early cancellation fee of ${sw['early_cancel_fee']:,.2f} "
                    f"charged to company account. {note} Episode terminated."
                )
            )

        # Wrong: active user cancelled (penalty but episode continues)
        if not sw.get("is_safe_to_cancel"):
            self._penalty += 0.3
            return AuditObservation(
                tool_result={
                    "cancelled":     True,
                    "software_id":   software_id,
                    "software_name": sw["name"],
                    "consequence":   (
                        "This subscription had active users. "
                        "Cancellation may cause business disruption."
                    ),
                },
                last_action_error="Active subscription cancelled — business disruption risk.",
                step=self._steps,
                done=False,
                reward=-0.3,
            )

        # Correct cancellation — partial reward proportional to seat cost
        self._savings += sw["monthly_cost"]
        partial_reward = round(
            sw["monthly_cost"] / max(self._target_savings, 1.0), 4
        )
        return AuditObservation(
            tool_result={
                "cancelled":            True,
                "software_id":          software_id,
                "software_name":        sw["name"],
                "monthly_savings_usd":  sw["monthly_cost"],
                "total_savings_so_far": round(self._savings, 2),
            },
            step=self._steps,
            done=False,
            reward=partial_reward,
        )

    def _tool_finish(self) -> AuditObservation:
        return self._end_episode(reason="Agent signalled task complete.")