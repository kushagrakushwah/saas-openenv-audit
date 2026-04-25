import json
import os
import uuid
from server.environment import AuditEnvironment
from server.models import AuditAction

OUTPUT_FILE = "data/sft_data.jsonl"
N_EPISODES = 500

SYSTEM_PROMPT = """You are EnvAudit, an autonomous SaaS cost-audit agent.
Tools: get_employee_logins(), get_billing_line_items(), query_software_metadata(software_id), check_contract_terms(software_id), execute_cancellation(software_id), finish_audit()
RULES:
1. NEVER cancel critical service accounts (bots).
2. ALWAYS call check_contract_terms before execute_cancellation.
3. Only cancel if the seat is inactive and has no cancellation fee.
Respond ONLY with JSON: {"tool": "name", "software_id": "id"}"""

class OraclePolicy:
    """Peeks at ground truth to guarantee 1.0 grader scores."""
    def __init__(self, env):
        self.env = env
        self.reset()

    def reset(self):
        self.state = "START"
        self.sw_ids = []
        self.sw_idx = 0
        self.sub_step = 0

    def select_action(self, obs):
        if self.state == "START":
            self.state = "BILLING"
            return AuditAction(tool="get_employee_logins")
        
        if self.state == "BILLING":
            self.state = "AUDIT_LOOP"
            self.sw_ids = [s["id"] for s in self.env._db]
            return AuditAction(tool="get_billing_line_items")

        if self.state == "AUDIT_LOOP":
            if self.sw_idx >= len(self.sw_ids):
                return AuditAction(tool="finish_audit")
            
            sw_id = self.sw_ids[self.sw_idx]
            # Peek at internal DB
            sw_record = next(s for s in self.env._db if s["id"] == sw_id)
            
            if self.sub_step == 0:
                self.sub_step = 1
                return AuditAction(tool="query_software_metadata", software_id=sw_id)
            
            if self.sub_step == 1:
                self.sub_step = 2
                return AuditAction(tool="check_contract_terms", software_id=sw_id)
            
            if self.sub_step == 2:
                self.sw_idx += 1
                self.sub_step = 0
                # Only cancel if the environment considers it 100% safe
                if sw_record.get("is_safe_to_cancel"):
                    return AuditAction(tool="execute_cancellation", software_id=sw_id)
                else:
                    return self.select_action(obs)

def generate():
    os.makedirs("data", exist_ok=True)
    successful = 0
    print("Starting optimized data generation...")

    with open(OUTPUT_FILE, "w") as f:
        for ep in range(N_EPISODES):
            # We use task3_hard to ensure the model learns to handle all traps
            env = AuditEnvironment(task_name="task3_hard")
            obs = env.reset()
            policy = OraclePolicy(env)
            
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            while not obs.done:
                # User role: The Environment State
                obs_dict = {
                    "tool_result": obs.tool_result,
                    "error": obs.last_action_error,
                    "step": obs.step
                }
                messages.append({"role": "user", "content": json.dumps(obs_dict)})
                
                # Assistant role: The Oracle Action
                action = policy.select_action(obs)
                
                # Handle renaming finish -> finish_audit for OpenEnv compliance
                tool_name = action.tool
                if tool_name == "finish": tool_name = "finish_audit"
                
                action_dict = {"tool": tool_name}
                if action.software_id:
                    action_dict["software_id"] = action.software_id
                    
                messages.append({"role": "assistant", "content": json.dumps(action_dict)})
                
                obs = env.step(action)

            # Verification
            final_state = env.get_state()
            if final_state.grader_score >= 0.99:
                traj = {
                    "messages": messages,
                    "total_reward": final_state.total_savings,
                    "grader_score": final_state.grader_score
                }
                f.write(json.dumps(traj) + "\n")
                successful += 1
                
            if (ep + 1) % 50 == 0:
                print(f"Episode {ep + 1}/{N_EPISODES}. Saved: {successful}")

    print(f"\nSUCCESS: Saved {successful} perfect trajectories to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate()