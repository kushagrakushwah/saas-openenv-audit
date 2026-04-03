"""
scenarios.py — Static scenario data for all three tasks.

Each scenario is a list of software subscription dicts.
The grader reads the ground-truth fields at episode end:
    is_safe_to_cancel   : bool  — correct to cancel
    is_critical         : bool  — cancelling = immediate fail
    is_annual_trap      : bool  — annual contract with a cancellation fee
    early_cancel_fee    : float — fee in USD if annual and cancelled early
"""
from typing import Dict, List


# ---------------------------------------------------------------------------
# TASK 1 — EASY  :  The Basic Join
#
# One clearly inactive user (60+ days), rest are active.
# Pure cross-reference task. No traps.
# Grader: 1.0 if the single inactive seat is cancelled, 0.0 otherwise.
# ---------------------------------------------------------------------------
TASK1_EASY: List[Dict] = [
    {
        "id": "sw_001", "name": "Figma — Alice Johnson",
        "monthly_cost": 45.0, "days_since_last_login": 72,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Design",
    },
    {
        "id": "sw_002", "name": "Figma — Bob Chen",
        "monthly_cost": 45.0, "days_since_last_login": 2,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Design",
    },
    {
        "id": "sw_003", "name": "Slack — Carol Smith",
        "monthly_cost": 8.75, "days_since_last_login": 1,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Engineering",
    },
    {
        "id": "sw_004", "name": "Notion — Dave Park",
        "monthly_cost": 16.0, "days_since_last_login": 5,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Product",
    },
]

TASK1_EASY_TARGET_ID  = "sw_001"   # the one correct cancellation
TASK1_EASY_MAX_STEPS  = 12


# ---------------------------------------------------------------------------
# TASK 2 — MEDIUM  :  Batch Processing & Safety
#
# 5 active + 5 inactive users. Cancel ALL inactive, NONE of the active.
# Grader: +0.2 per correct cancellation (max 1.0).
#          immediate 0.0 if any active user is cancelled.
# ---------------------------------------------------------------------------
TASK2_MEDIUM: List[Dict] = [
    # --- INACTIVE (safe to cancel) ---
    {
        "id": "sw_101", "name": "Miro — Ethan Wong",
        "monthly_cost": 30.0, "days_since_last_login": 95,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Design",
    },
    {
        "id": "sw_102", "name": "Loom — Fiona Patel",
        "monthly_cost": 12.5, "days_since_last_login": 80,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Marketing",
    },
    {
        "id": "sw_103", "name": "Invision — George Okafor",
        "monthly_cost": 22.0, "days_since_last_login": 110,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Design",
    },
    {
        "id": "sw_104", "name": "Trello — Hannah Lee",
        "monthly_cost": 5.0, "days_since_last_login": 62,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Operations",
    },
    {
        "id": "sw_105", "name": "Webex — Ivan Russo",
        "monthly_cost": 14.0, "days_since_last_login": 75,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Sales",
    },
    # --- ACTIVE (must NOT cancel) ---
    {
        "id": "sw_106", "name": "Jira — Jane Kim",
        "monthly_cost": 70.0, "days_since_last_login": 1,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Engineering",
    },
    {
        "id": "sw_107", "name": "Slack — Kevin Brown",
        "monthly_cost": 8.75, "days_since_last_login": 0,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Engineering",
    },
    {
        "id": "sw_108", "name": "Zoom — Laura White",
        "monthly_cost": 15.0, "days_since_last_login": 3,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Sales",
    },
    {
        "id": "sw_109", "name": "Notion — Marcus Davis",
        "monthly_cost": 16.0, "days_since_last_login": 7,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Product",
    },
    {
        "id": "sw_110", "name": "Figma — Nina Torres",
        "monthly_cost": 45.0, "days_since_last_login": 14,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Design",
    },
]

TASK2_MEDIUM_SAFE_IDS   = {"sw_101", "sw_102", "sw_103", "sw_104", "sw_105"}
TASK2_MEDIUM_ACTIVE_IDS = {"sw_106", "sw_107", "sw_108", "sw_109", "sw_110"}
TASK2_MEDIUM_MAX_STEPS  = 20


# ---------------------------------------------------------------------------
# TASK 3 — HARD  :  The Traps
#
# Service-account trap: zero human logins → tagged critical, must NOT cancel.
# Annual-contract trap: unused seat but massive early-cancellation fee.
# Plus a mix of genuinely safe-to-cancel seats.
#
# Grader:
#   - Falling into any trap → immediate 0.0
#   - Otherwise: partial credit proportional to correct cancellations
#     out of total safely-cancellable pool. Max 1.0 for perfect run.
# ---------------------------------------------------------------------------
TASK3_HARD: List[Dict] = [
    # --- SAFE to cancel ---
    {
        "id": "sw_201", "name": "Canva Pro — Oliver Scott",
        "monthly_cost": 14.99, "days_since_last_login": 100,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Marketing",
    },
    {
        "id": "sw_202", "name": "Intercom — Priya Mehta",
        "monthly_cost": 65.0, "days_since_last_login": 88,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Support",
    },
    {
        "id": "sw_203", "name": "Webflow — Quinn Adams",
        "monthly_cost": 29.0, "days_since_last_login": 91,
        "service_type": "human", "contract_type": "annual",
        "early_cancel_fee": 0.0,          # annual but NO penalty — safe
        "is_safe_to_cancel": True, "is_critical": False, "is_annual_trap": False,
        "department": "Marketing",
    },
    # --- SERVICE ACCOUNT TRAP (zero logins, but headless critical bot) ---
    {
        "id": "sw_204", "name": "GitHub Actions Runner — CI Bot",
        "monthly_cost": 50.0, "days_since_last_login": 180,
        "service_type": "service_account", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": True, "is_annual_trap": False,
        "department": "Engineering",
        "note": "Headless CI/CD service account. DO NOT CANCEL.",
    },
    {
        "id": "sw_205", "name": "AWS Backup Automation — Ops Bot",
        "monthly_cost": 80.0, "days_since_last_login": 200,
        "service_type": "service_account", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": True, "is_annual_trap": False,
        "department": "Infrastructure",
        "note": "Critical backup orchestration bot. DO NOT CANCEL.",
    },
    # --- ANNUAL CONTRACT TRAP (unused but massive penalty) ---
    {
        "id": "sw_206", "name": "Salesforce CRM — Rachel Kim",
        "monthly_cost": 300.0, "days_since_last_login": 55,
        "service_type": "human", "contract_type": "annual",
        "early_cancel_fee": 1800.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": True,
        "department": "Sales",
    },
    {
        "id": "sw_207", "name": "HubSpot Marketing Hub — Sam Torres",
        "monthly_cost": 90.0, "days_since_last_login": 45,
        "service_type": "human", "contract_type": "annual",
        "early_cancel_fee": 540.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": True,
        "department": "Marketing",
    },
    # --- ACTIVE (must NOT cancel) ---
    {
        "id": "sw_208", "name": "Notion — Tina Foster",
        "monthly_cost": 20.0, "days_since_last_login": 2,
        "service_type": "human", "contract_type": "monthly",
        "early_cancel_fee": 0.0,
        "is_safe_to_cancel": False, "is_critical": False, "is_annual_trap": False,
        "department": "Product",
    },
]

TASK3_HARD_SAFE_IDS    = {"sw_201", "sw_202", "sw_203"}
TASK3_HARD_TRAP_IDS    = {"sw_204", "sw_205", "sw_206", "sw_207"}  # instant-fail
TASK3_HARD_MAX_STEPS   = 25


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SCENARIOS = {
    "task1_easy":   TASK1_EASY,
    "task2_medium": TASK2_MEDIUM,
    "task3_hard":   TASK3_HARD,
}

MAX_STEPS = {
    "task1_easy":   TASK1_EASY_MAX_STEPS,
    "task2_medium": TASK2_MEDIUM_MAX_STEPS,
    "task3_hard":   TASK3_HARD_MAX_STEPS,
}

TASK_PROMPTS = {
    "task1_easy": (
        "You are a SaaS cost auditor. Query the employee login activity and "
        "billing ledger, identify the seat that has not been used in 60+ days, "
        "and cancel it. Call 'finish' when done."
    ),
    "task2_medium": (
        "You are a SaaS cost auditor. The company has 10 software seats. "
        "5 employees are inactive (60+ days no login) and 5 are active. "
        "Cancel ALL inactive seats and NONE of the active ones. "
        "Call 'finish' when done."
    ),
    "task3_hard": (
        "You are a SaaS cost auditor. Reduce SaaS spend — but be careful: "
        "(1) Some tools have zero human logins but are critical headless service "
        "accounts (CI/CD bots, backup systems) — DO NOT cancel them. "
        "(2) Some unused seats are on annual contracts with large early-cancellation "
        "fees — always check contract terms before cancelling. "
        "Maximise monthly savings while avoiding both traps. "
        "Call 'finish' when done."
    ),
}