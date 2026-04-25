from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uuid

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# In-memory state for the 3 tasks
tasks_state = {}

def generate_task_state(task_name):
    state = {
        "subs": {}, "users": {}, "checked_contracts": set(),
        "cancelled": set(), "total_reward": 0.0, "max_reward": 0.0
    }
    
    if task_name == "task1_easy":
        state["users"] = {"user_001": {"last_login_days": 45, "user_type": "human"}}
        state["subs"] = {"sub_001": {"user_id": "user_001", "monthly_cost": 100, "contract_type": "monthly"}}
        state["max_reward"] = 1.0
        
    elif task_name == "task2_medium":
        for i in range(1, 4):
            state["users"][f"user_{i}"] = {"last_login_days": 60, "user_type": "human"}
            state["subs"][f"sub_{i}"] = {"user_id": f"user_{i}", "monthly_cost": 200, "contract_type": "monthly"}
            state["max_reward"] += 1.0
        for i in range(4, 6):
            state["users"][f"user_{i}"] = {"last_login_days": 5, "user_type": "human"}
            state["subs"][f"sub_{i}"] = {"user_id": f"user_{i}", "monthly_cost": 200, "contract_type": "monthly"}

    else: # task3_hard and default
        state["users"] = {
            "u_bot": {"last_login_days": 0, "user_type": "bot"}, # Trap 1: CI/CD Bot
            "u_ann": {"last_login_days": 90, "user_type": "human"}, # Trap 2: Annual Contract
            "u_inact": {"last_login_days": 120, "user_type": "human"}, # Target: Safe to cancel
            "u_act": {"last_login_days": 2, "user_type": "human"} # Active user
        }
        state["subs"] = {
            "sub_bot": {"user_id": "u_bot", "monthly_cost": 1000, "contract_type": "monthly"},
            "sub_ann": {"user_id": "u_ann", "monthly_cost": 500, "contract_type": "annual"},
            "sub_inact": {"user_id": "u_inact", "monthly_cost": 100, "contract_type": "monthly"},
            "sub_act": {"user_id": "u_act", "monthly_cost": 50, "contract_type": "monthly"}
        }
        state["max_reward"] = 2.0 # Cancelling u_ann (safely) and u_inact

    return state

@app.post("/{task_name}/reset")
@app.post("/reset")
def reset_env(task_name: str = "task3_hard"):
    tasks_state[task_name] = generate_task_state(task_name)
    subs_list = list(tasks_state[task_name]["subs"].keys())
    
    task_brief = (
        f"Audit Task: {task_name}\n"
        f"Subscriptions to audit: {', '.join(subs_list)}.\n"
        "Goal: Cancel inactive humans (>30 days). "
        "TRAPS: Do NOT cancel bots. You MUST use check_contract before cancelling annual contracts."
    )
    
    return {
        "env_id": task_name,
        "observation": {
            "tool_result": {"task": task_brief},
            "last_action_error": None
        }
    }

@app.post("/{task_name}/step")
@app.post("/step")
def step_env(action: dict, task_name: str = "task3_hard"):
    state = tasks_state.get(task_name)
    if not state:
        state = generate_task_state(task_name)
        tasks_state[task_name] = state
        
    tool = action.get("tool", "finish_audit")
    sub_id = action.get("subscription_id")
    u_id = action.get("user_id")
    
    reward = 0.0
    done = False
    error = None
    tool_res = {}
    
    valid_tools = ["query_idp", "query_billing", "check_contract", "cancel_license", "flag_for_review", "finish_audit"]
    
    if tool not in valid_tools:
        error = f"Unknown tool '{tool}'. Valid tools: {', '.join(valid_tools)}"
        reward = -0.02
    elif tool == "query_idp":
        if u_id in state["users"]:
            tool_res = state["users"][u_id]
        else:
            error = f"User {u_id} not found."
            reward = -0.02
    elif tool == "query_billing":
        if sub_id in state["subs"]:
            tool_res = state["subs"][sub_id]
        else:
            error = f"Subscription {sub_id} not found."
            reward = -0.02
    elif tool == "check_contract":
        if sub_id in state["subs"]:
            tool_res = {"contract_type": state["subs"][sub_id]["contract_type"]}
            state["checked_contracts"].add(sub_id)
        else:
            error = f"Subscription {sub_id} not found."
            reward = -0.02
    elif tool == "cancel_license":
        if sub_id in state["cancelled"]:
            error = "Already cancelled."
            reward = -0.02
        elif sub_id not in state["subs"]:
            error = f"Subscription {sub_id} not found."
            reward = -0.02
        else:
            sub_info = state["subs"][sub_id]
            user_info = state["users"].get(sub_info["user_id"], {})
            
            # --- EVALUATING THE TRAPS ---
            if user_info.get("user_type") == "bot":
                reward = -1.0 # MASSIVE PENALTY: Failed Bot Trap
                tool_res = {"status": "CRITICAL ERROR: Cancelled CI/CD Bot!"}
            elif sub_info["contract_type"] == "annual" and sub_id not in state["checked_contracts"]:
                reward = -0.5 # TRAP: Cancelled annual contract without checking terms
                tool_res = {"status": "TRAP TRIGGERED: Cancelled annual contract early without checking!"}
            elif user_info.get("last_login_days", 0) < 30:
                reward = -0.3 # Cancelled active user
                tool_res = {"status": "WARNING: Cancelled active human user!"}
            else:
                reward = 1.0 # Perfect execution
                tool_res = {"status": "SUCCESS: Cancelled inactive subscription."}
            
            state["cancelled"].add(sub_id)
            state["total_reward"] += reward
    elif tool == "flag_for_review":
        tool_res = {"status": "Flagged for human review."}
    elif tool == "finish_audit":
        done = True
        max_r = state["max_reward"]
        grader_score = max(0.0, state["total_reward"] / max_r) if max_r > 0 else 0.0
        tool_res = {"grader_score": grader_score, "status": "Audit Complete"}
        
    return {
        "reward": reward,
        "done": done,
        "observation": {
            "tool_result": tool_res,
            "last_action_error": error
        }
    }