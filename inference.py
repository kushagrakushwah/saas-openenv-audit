"""
inference.py — Baseline inference script for EnvAudit
=======================================================
Runs an LLM agent against all 3 tasks and emits the mandatory log lines.

MANDATORY ENV VARS:
    HF_TOKEN          Your HuggingFace / API key
    API_BASE_URL      LLM endpoint  (default: https://router.huggingface.co/v1)
    MODEL_NAME        Model to use  (default: Qwen/Qwen2.5-72B-Instruct)
    AUDIT_ENV_URL     Running environment base URL (default: http://localhost:7860)

Mandatory stdout format (strictly followed per spec):
    [START] task=<task> env=<benchmark> model=<model>
    [STEP]  step=<n> action=<str> reward=<0.00> done=<true|false> error=<str|null>
    [END]   success=<true|false> steps=<n> score=<0.00> rewards=<r1,r2,...>

Run:
    python inference.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

import json
import re
import requests
from openai import OpenAI


# ---------------------------------------------------------------------------
# Config — all sourced from environment variables per competition spec
# ---------------------------------------------------------------------------

API_BASE_URL  = os.getenv("API_BASE_URL",  "https://router.huggingface.co/v1")
MODEL_NAME    = os.getenv("MODEL_NAME",    "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN      = os.getenv("HF_TOKEN",      os.getenv("API_KEY", ""))
AUDIT_ENV_URL = os.getenv("AUDIT_ENV_URL", "http://localhost:7860")

BENCHMARK         = "saas_audit_env"
MAX_STEPS         = 20
TEMPERATURE       = 0.0
MAX_TOKENS        = 512
SUCCESS_THRESHOLD = 0.8

TASKS = [
    ("task1_easy",   f"{AUDIT_ENV_URL}/task1_easy"),
    ("task2_medium", f"{AUDIT_ENV_URL}/task2_medium"),
    ("task3_hard",   f"{AUDIT_ENV_URL}/task3_hard"),
]

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)


# ---------------------------------------------------------------------------
# Mandatory structured log helpers — field names & order must match spec
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int,
    action: str,
    reward: float,
    done: bool,
    error,
) -> None:
    done_str  = "true" if done else "false"
    error_str = str(error) if error else "null"
    print(
        f"[STEP] step={step} action={action} "
        f"reward={reward:.2f} done={done_str} error={error_str}",
        flush=True,
    )


def log_end(
    success: bool,
    steps: int,
    score: float,
    rewards: list,
) -> None:
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={success_str} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an AI SaaS cost auditor for a corporation. Reduce monthly SaaS spend \
by cancelling unused software subscriptions — without causing business disruption.

Respond with ONLY a single valid JSON object. No prose. No markdown fences.

Available tools (call exactly one per turn):
  {"tool": "get_employee_logins"}
  {"tool": "get_billing_line_items"}
  {"tool": "query_software_metadata", "software_id": "<id>"}
  {"tool": "check_contract_terms",    "software_id": "<id>"}
  {"tool": "execute_cancellation",    "software_id": "<id>"}
  {"tool": "finish"}

Critical rules:
1. NEVER cancel a service_account — headless automated systems (CI/CD, backups).
2. For ANY annual-contract subscription: call check_contract_terms FIRST.
3. Only cancel seats inactive for 30+ days that are confirmed human licenses.
4. Call finish when you have safely cancelled everything you can.
"""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def env_reset(base_url: str) -> dict:
    r = requests.post(f"{base_url}/reset", timeout=30)
    r.raise_for_status()
    return r.json()


def env_step(base_url: str, tool: str, software_id: str = None) -> dict:
    """
    POST action fields at the TOP LEVEL of the JSON body.
    ActionBody in app.py deserialises tool / software_id / metadata directly.
    """
    payload: dict = {"tool": tool, "metadata": {}}
    if software_id is not None:
        payload["software_id"] = software_id
    r = requests.post(f"{base_url}/step", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# JSON action parser
# ---------------------------------------------------------------------------

def parse_action(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$",           "", text).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------

def run_episode(task_name: str, base_url: str) -> None:
    log_start(task=task_name, env=BENCHMARK, model=MODEL_NAME)

    step_num = 0
    rewards: list = []
    done  = False
    score = 0.0

    # ── Reset ────────────────────────────────────────────────────────────
    try:
        reset_payload = env_reset(base_url)
    except Exception as exc:
        log_end(success=False, steps=0, score=0.0, rewards=[])
        return

    obs        = reset_payload.get("observation", reset_payload)
    task_brief = obs.get("tool_result", {}).get("task", "")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Task brief:\n{task_brief}\n\n"
                "Begin the audit. Call your first tool now."
            ),
        },
    ]

    # ── Agent loop ────────────────────────────────────────────────────────
    while not done and step_num < MAX_STEPS:

        # LLM call
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            raw = response.choices[0].message.content.strip()
        except Exception as exc:
            err = str(exc)[:120]
            step_num += 1
            log_step(step=step_num, action="null", reward=0.0, done=True, error=err)
            rewards.append(0.0)
            done = True
            break

        # Parse action
        try:
            action_dict = parse_action(raw)
            tool        = action_dict.get("tool", "finish")
            software_id = action_dict.get("software_id")
        except (json.JSONDecodeError, KeyError, TypeError):
            tool        = "finish"
            software_id = None

        # Step environment
        try:
            step_resp = env_step(base_url, tool, software_id)
        except Exception as exc:
            err        = str(exc)[:120]
            step_num  += 1
            action_str = f"{tool}({software_id})" if software_id else tool
            log_step(step=step_num, action=action_str, reward=0.0, done=True, error=err)
            rewards.append(0.0)
            done = True
            break

        reward   = float(step_resp.get("reward", 0.0))
        done     = bool(step_resp.get("done", False))
        step_obs = step_resp.get("observation", step_resp)
        last_err = step_obs.get("last_action_error") or None

        step_num += 1
        rewards.append(reward)

        action_str = f"{tool}({software_id})" if software_id else tool
        log_step(step=step_num, action=action_str, reward=reward, done=done, error=last_err)

        if done:
            # Extract the authoritative grader_score from the terminal observation
            grader_score = step_obs.get("tool_result", {}).get("grader_score")
            score = float(grader_score) if grader_score is not None else reward
            break

        # Feed observation back into the conversation
        messages.append({"role": "assistant", "content": raw})
        tool_result_str = json.dumps(step_obs.get("tool_result", {}), indent=2)
        follow_up = f"Tool result:\n{tool_result_str}"
        if last_err:
            follow_up += f"\n\nError: {last_err}"
        follow_up += "\n\nCall your next tool."
        messages.append({"role": "user", "content": follow_up})

    # Clamp and log final score
    score   = min(max(score, 0.0), 1.0)
    success = score >= SUCCESS_THRESHOLD
    log_end(success=success, steps=step_num, score=score, rewards=rewards)


# ---------------------------------------------------------------------------
# Main — runs all 3 tasks sequentially
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    for task_name, base_url in TASKS:
        run_episode(task_name, base_url)
        print("", flush=True)   # blank line separator between tasks