"""
inference.py — Baseline inference script for EnvAudit
=======================================================
Runs an LLM agent against all 3 tasks and emits the mandatory log lines.

MANDATORY ENV VARS:
    HF_TOKEN          Your HuggingFace / API key
    API_BASE_URL      LLM endpoint  (default: https://router.huggingface.co/v1)
    MODEL_NAME        Model to use  (default: Qwen/Qwen2.5-72B-Instruct)
    LOCAL_IMAGE_NAME  Docker image name if using from_docker_image()
    AUDIT_ENV_URL     Running environment base URL (default: http://localhost:7860)

Mandatory stdout format:
    [START] task=<task> env=saas_audit_env model=<model>
    [STEP]  step=<n> action=<tool> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> rewards=<r1,r2,...>

Run:
    python inference.py
"""
import os
from dotenv import load_dotenv

load_dotenv()
import sys
import json
import re
import requests
from openai import OpenAI


# ---------------------------------------------------------------------------
# Config — all from environment variables
# ---------------------------------------------------------------------------

API_BASE_URL      = os.getenv("API_BASE_URL",   "https://router.huggingface.co/v1")
MODEL_NAME        = os.getenv("MODEL_NAME",      "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN          = os.getenv("HF_TOKEN",        os.getenv("API_KEY", ""))
LOCAL_IMAGE_NAME  = os.getenv("LOCAL_IMAGE_NAME", "")  # for from_docker_image()
AUDIT_ENV_URL     = os.getenv("AUDIT_ENV_URL",   "http://localhost:7860")
BENCHMARK         = "saas_audit_env"

# Tasks and their server sub-paths
TASKS = [
    ("task1_easy",   f"{AUDIT_ENV_URL}/task1_easy"),
    ("task2_medium", f"{AUDIT_ENV_URL}/task2_medium"),
    ("task3_hard",   f"{AUDIT_ENV_URL}/task3_hard"),
]

MAX_STEPS   = 20    # hard ceiling per episode
TEMPERATURE = 0.0   # deterministic for reproducibility
MAX_TOKENS  = 512

client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)


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
    # We now wrap the payload in an "action" dictionary from the start!
    payload = {
        "action": {
            "tool": tool,
            "software_id": software_id,
            "metadata": {}
        }
    }
    
    r = requests.post(f"{base_url}/step", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# JSON action parser
# ---------------------------------------------------------------------------

def parse_action(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------

def run_episode(task_name: str, base_url: str) -> None:
    print(f"[START] task={task_name} env={BENCHMARK} model={MODEL_NAME}", flush=True)

    step_num   = 0
    rewards    = []
    done       = False

    # Reset
    try:
        reset_payload = env_reset(base_url)
    except Exception as exc:
        print(f"[END] success=false steps=0 rewards=", flush=True)
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

    # Agent loop
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
            print(
                f"[STEP] step={step_num} action=null reward=0.00 "
                f"done=true error={err}",
                flush=True,
            )
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
            err = str(exc)[:120]
            step_num += 1
            print(
                f"[STEP] step={step_num} action={tool} reward=0.00 "
                f"done=true error={err}",
                flush=True,
            )
            rewards.append(0.0)
            done = True
            break

        reward     = step_resp.get("reward", 0.0)
        done       = step_resp.get("done", False)
        step_obs   = step_resp.get("observation", step_resp)
        last_error = step_obs.get("last_action_error") or "null"
        step_num  += 1
        rewards.append(reward)

        action_str = f"{tool}({software_id})" if software_id else tool

        print(
            f"[STEP] step={step_num} action={action_str} "
            f"reward={reward:.2f} done={'true' if done else 'false'} "
            f"error={last_error}",
            flush=True,
        )

        if done:
            break

        # Feed observation back into conversation
        messages.append({"role": "assistant", "content": raw})
        tool_result_str = json.dumps(step_obs.get("tool_result", {}), indent=2)
        follow_up = f"Tool result:\n{tool_result_str}"
        if last_error != "null":
            follow_up += f"\n\nError: {last_error}"
        follow_up += "\n\nCall your next tool."
        messages.append({"role": "user", "content": follow_up})

    # [END] line
    final_reward = rewards[-1] if rewards else 0.0
    success      = "true" if final_reward >= 0.8 else "false"
    rewards_str  = ",".join(f"{r:.2f}" for r in rewards)

    print(
        f"[END] success={success} steps={step_num} rewards={rewards_str}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    for task_name, base_url in TASKS:
        run_episode(task_name, base_url)
        print("", flush=True)   # blank line separator between tasks