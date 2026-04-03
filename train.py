"""
train.py — Demo policy runners for the SaaS Audit environment.

Runs two baseline policies against all three tasks using the typed client:
  - RandomPolicy     : picks a random valid tool each step
  - RuleBasedPolicy  : deterministic rule-based auditor (near-optimal)

Usage (server must be running):
    uvicorn app:app --host 0.0.0.0 --port 7860 &
    python train.py
"""
import random
from client import AuditEnv
from models import AuditAction

TASK_URLS = {
    "task1_easy":   "http://localhost:7860/task1_easy",
    "task2_medium": "http://localhost:7860/task2_medium",
    "task3_hard":   "http://localhost:7860/task3_hard",
}


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class RandomPolicy:
    """Randomly selects a tool each step — mostly noisy, used as lower bound."""
    name = "🎲 Random"
    TOOLS = [
        "get_employee_logins", "get_billing_line_items",
        "query_software_metadata", "check_contract_terms",
        "execute_cancellation", "finish",
    ]
    FAKE_IDS = [f"sw_{str(i).zfill(3)}" for i in range(1, 12)]

    def reset(self):
        pass

    def select_action(self, obs) -> AuditAction:
        tool = random.choice(self.TOOLS)
        sid  = random.choice(self.FAKE_IDS) if tool in (
            "query_software_metadata", "check_contract_terms", "execute_cancellation"
        ) else None
        return AuditAction(tool=tool, software_id=sid)


class RuleBasedPolicy:
    """
    Deterministic rule-based policy — near-optimal baseline.

    Phase 1: gather logins + billing
    Phase 2: for each seat, query metadata
    Phase 3: for annual contracts, check terms
    Phase 4: cancel seats that pass all safety checks
    Phase 5: finish
    """
    name = "🧠 Rule-Based"

    def reset(self):
        self._phase       = "get_logins"
        self._logins      = {}     # software_id -> days_since_last_login
        self._billing     = {}     # software_id -> {cost, contract_type}
        self._metadata    = {}     # software_id -> service_type
        self._contracts   = {}     # software_id -> early_cancel_fee
        self._to_inspect  = []
        self._to_check    = []
        self._to_cancel   = []
        self._inspected   = set()
        self._contract_checked = set()

    def select_action(self, obs) -> AuditAction:
        tr = obs.tool_result if hasattr(obs, "tool_result") else {}

        # Absorb tool results
        if "employee_login_records" in tr:
            for rec in tr["employee_login_records"]:
                self._logins[rec["software_id"]] = rec["days_since_last_login"]
        if "billing_line_items" in tr:
            for item in tr["billing_line_items"]:
                self._billing[item["software_id"]] = {
                    "cost":          item["monthly_cost_usd"],
                    "contract_type": item["contract_type"],
                }
        if "service_type" in tr:
            sid = tr.get("software_id")
            if sid:
                self._metadata[sid] = tr["service_type"]
                self._inspected.add(sid)
        if "contract_type" in tr and "early_cancellation_fee_usd" in tr:
            sid = tr.get("software_id")
            if sid:
                self._contracts[sid] = tr["early_cancellation_fee_usd"]
                self._contract_checked.add(sid)

        # Phase machine
        if self._phase == "get_logins":
            self._phase = "get_billing"
            return AuditAction(tool="get_employee_logins")

        if self._phase == "get_billing":
            self._phase = "inspect"
            self._to_inspect = list(self._billing.keys())
            return AuditAction(tool="get_billing_line_items")

        if self._phase == "inspect":
            if self._to_inspect:
                sid = self._to_inspect.pop(0)
                return AuditAction(tool="query_software_metadata", software_id=sid)
            # Done inspecting — figure out candidates
            candidates = []
            for sid, days in self._logins.items():
                if days > 30 and self._metadata.get(sid) != "service_account":
                    candidates.append(sid)
            # Split: annual needs contract check, monthly can cancel directly
            self._to_check  = [s for s in candidates
                                if self._billing.get(s, {}).get("contract_type") == "annual"]
            self._to_cancel = [s for s in candidates
                                if self._billing.get(s, {}).get("contract_type") != "annual"]
            self._phase = "check_contracts"

        if self._phase == "check_contracts":
            if self._to_check:
                sid = self._to_check.pop(0)
                return AuditAction(tool="check_contract_terms", software_id=sid)
            # Move annual candidates with zero fee to cancel list
            for sid in self._contract_checked:
                if self._contracts.get(sid, 1) == 0.0:
                    self._to_cancel.append(sid)
            self._phase = "cancel"

        if self._phase == "cancel":
            if self._to_cancel:
                return AuditAction(tool="execute_cancellation",
                                   software_id=self._to_cancel.pop(0))
            self._phase = "finish"

        return AuditAction(tool="finish")


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------

def run_episode(env, policy) -> float:
    policy.reset()
    result = env.reset()
    final_reward = 0.0

    while not result.observation.done:
        action = policy.select_action(result.observation)
        result = env.step(action)
        error  = result.observation.last_action_error or ""
        print(
            f"  step {result.observation.step:2d} | "
            f"{action.tool:<28} "
            f"{'(' + action.software_id + ')' if action.software_id else '':<12} "
            f"reward={result.reward:+.3f}"
            + (f"  ⚠ {error[:60]}" if error else "")
        )
        if result.observation.done:
            final_reward = result.observation.tool_result.get("grader_score", result.reward)
            break

    print(f"  → Grader score: {final_reward:.4f}\n")
    return final_reward


def evaluate(task_name: str, url: str, policy, episodes: int = 3):
    print(f"\n{'='*64}")
    print(f"  Task: {task_name}  |  Policy: {policy.name}")
    print(f"{'='*64}\n")
    scores = []
    with AuditEnv(base_url=url).sync() as env:
        for ep in range(1, episodes + 1):
            print(f"  Episode {ep}/{episodes}")
            scores.append(run_episode(env, policy))
    avg = sum(scores) / len(scores)
    print(f"  Average grader score over {episodes} episodes: {avg:.4f}\n")


if __name__ == "__main__":
    for task, url in TASK_URLS.items():
        evaluate(task, url, RuleBasedPolicy(), episodes=3)
        evaluate(task, url, RandomPolicy(),    episodes=3)