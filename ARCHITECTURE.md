# EnvAudit: System Architecture

*Meta × Scaler OpenEnv Hackathon 2026 · Theme #3.1 — Professional Tasks*
*Kushagra Singh Kushwah · Raj Patil*

---

## The One Design Rule We Didn't Compromise On

The agent never touches the environment code directly. Not during training. Not during evaluation. Not once.

This sounds obvious but it's the kind of thing that quietly breaks under deadline pressure. "Let's just import the scenario generator for debugging" turns into "the agent has access to the trap definitions" turns into "we've built a cheating benchmark."

EnvAudit enforces a strict client/server boundary at the network layer. The agent — whether the SFT baseline or the GRPO-trained model — only ever sees what a real enterprise integration would surface: an observation payload over HTTP, and a reward signal in response to its actions. It cannot inspect `traps.py`. It cannot read `BOT_ACCOUNT_IDS`. It has to figure out that `sw_204` is a bot by calling `query_software_metadata` and reading the response, exactly like a production system would require.

That's not just good engineering. It's the only way the benchmark means anything.

---

## Component Map

```
┌──────────────────────────────────────────────────────────┐
│                   JUDGE / EVALUATOR                      │
│        openenv evaluate --env-url <HF_SPACE_URL>         │
└───────────────────────────┬──────────────────────────────┘
                            │  HTTP  (OpenEnv protocol)
                            ▼
┌──────────────────────────────────────────────────────────┐
│            HUGGINGFACE SPACE  (Docker, port 7860)        │
│                                                          │
│   server/app.py     ──►  FastAPI application             │
│        │                                                 │
│        ▼                                                 │
│   environment.py    ──►  MCPEnvironment subclass         │
│        │                                                 │
│        ├──►  scenarios.py    seeded scenario generator   │
│        ├──►  traps.py        BOT_IDS, ANNUAL_IDS         │
│        └──►  schemas.py      Pydantic request/response   │
└───────────────────────────▲──────────────────────────────┘
                            │  HTTP  (same OpenEnv API)
┌──────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE                         │
│                                                          │
│   inference.py      ──►  interactive agent runner        │
│        └──►  HF Hub model  (kushagrakushwah/envaudit-*)  │
│                                                          │
│   training/grpo_train.py                                 │
│        └──►  HF Space /reset + /step as reward oracle    │
│             (Kaggle: rajpatil01/final-grpo)              │
│                                                          │
│   frontend/         ──►  React/Vite dashboard            │
│        └──►  connects to HF Space for live episode view  │
└──────────────────────────────────────────────────────────┘
```

---

## Layer 1: The FastAPI Server (`server/app.py`)

The server *is* the environment. All episode state lives here and only here. The agent gets observations. It doesn't get state objects.

### Protocol Endpoints

| Method | Path | What It Does |
|---|---|---|
| `POST` | `/reset` | Start a new episode. Returns `env_id` + initial observation. |
| `POST` | `/step` | Submit one tool-call action. Returns `observation`, `reward`, `done`, `info`. |
| `GET` | `/state/{env_id}` | Full debug state — used by the dashboard and evaluation notebook, not the agent. |
| `DELETE` | `/close/{env_id}` | Tear down a finished episode. |
| `GET` | `/health` | Liveness probe. Returns `{"status": "ok", "active_envs": N}`. |
| `POST` | `/set_difficulty` | Curriculum control — scales penalty magnitude during RL training. |
| `GET` | `/render/{env_id}` | Human-readable episode summary for the dashboard. |

### State Isolation

Episodes are keyed by UUID in a module-level dict. When an episode terminates (`done=True`), the entry is deleted immediately. Two concurrent callers — a judge running `openenv evaluate` and Raj's training loop — each get their own `env_id` and never contaminate each other's state.

```python
_envs: Dict[str, EnvAuditEnvironment] = {}

@app.post("/reset")
async def reset(seed: Optional[int] = None):
    env_id = str(uuid.uuid4())
    env = EnvAuditEnvironment(seed=seed)
    obs = env.reset()
    _envs[env_id] = env
    return ResetResponse(env_id=env_id, observation=obs)

@app.post("/step")
async def step(req: StepRequest):
    env = _envs.get(req.env_id)
    if not env:
        raise HTTPException(404, "env_id not found")
    obs, reward, done, info = env.step(req.action)
    if done:
        del _envs[req.env_id]   # clean up immediately
    return StepResponse(observation=obs, reward=reward, done=done, info=info)
```

---

## Layer 2: The State Machine (`environment.py` + `scenarios.py`)

### `scenarios.py` — Deterministic and Seeded

Every episode is reproducible. Same seed = same users, same subscriptions, same login history, same contract types. This is non-negotiable for a benchmark — you can't compare two models if they're not facing the same scenario.

`generate_scenario(rng)` builds:
- 7 human employees + 3 headless CI/CD bots (`BOT_ACCOUNT_IDS`)
- 10 subscriptions, 2 of which are annual contracts (`ANNUAL_CONTRACT_IDS`) with cancellation fees ranging from $1,800–$15,000
- Login activity: bots always show `days_active: 0`; humans are randomly assigned 0, 5, 12, 18, 25, or 30 days

The structural trap: bots and genuinely inactive humans are observationally identical on login data alone. An agent that treats `days_active: 0` as sufficient evidence to cancel will hit Trap A every time. The correct path requires calling `query_software_metadata` and checking the `user_type` field — one extra tool call that the base model never learned to make, and that GRPO eventually taught it to make reliably.

### `environment.py` — The Reward Engine

`EnvAuditEnvironment` inherits from `MCPEnvironment` and implements the full step-level reward logic. The most important function is `_handle_cancel`:

```python
def _handle_cancel(self, sub_id: str, user_id: str):

    # Trap A: bot guard — fires first, no bypass possible
    if user_id in BOT_ACCOUNT_IDS:
        return -3.0, {"trap": "BOT_CANCELLATION"}

    # Trap B: annual contract fee — fires if agent skipped check_contract_terms
    contract = self.scenario["contracts"].get(sub_id, {})
    if contract.get("type") == "annual":
        if sub_id not in self.scenario["checked_contracts"]:
            fee = contract["early_cancellation_fee"]
            return -(fee / 1000.0), {"trap": "ANNUAL_CONTRACT_FEE", "fee_usd": fee}

    # Safe path: reward scales with monthly cost saved
    sub = self.scenario["subscriptions"].get(sub_id, {})
    monthly = sub.get("monthly_cost", 0)
    reward = 0.2 + min(monthly / 100.0, 1.0)
    self.cancelled.add(sub_id)
    return reward, {"savings_usd": monthly}
```

Two guard clauses. Both are invisible to the agent until it uses the right tools. Both represent real enterprise failure modes that cost real money.

---

## Layer 3: The Training Pipeline (`training/`)

### Stage 1 — SFT (`sft_train.py`)

600 oracle trajectories, each recorded from a `RuleBasedPolicy` that always plays optimally. The oracle has direct access to `get_full_state()` during data generation — cheating is fine here, because the oracle isn't being evaluated, it's generating training data.

Fine-tuned via Unsloth SFTTrainer: QLoRA rank 4, max sequence length 512, Paged AdamW 8-bit, loss converging to ~0.0001.

**What SFT taught the model:** which tools exist, what valid JSON looks like, the general shape of a good episode.

**What SFT did not teach the model:** when to stop generating prose. After SFT, average completion length was ~128 tokens. The model would produce markdown headers, bullet points, and multi-sentence explanations before every single action. The environment's parser would eventually find the JSON inside, but the model was burning most of its context window on noise.

SFT gave the model syntax. It didn't give it discipline.

### Stage 2 — GRPO (`grpo_train.py`)

GRPO replaced our original PPO plan. PPO collapsed on the first batch — value head initialisation caused immediate reward hacking toward `finish_audit`, collecting zero reward while avoiding all penalties. We cut it after four hours and switched.

GRPO's direct reward-to-loss mapping was more stable with our setup. More importantly, it let us write custom reward functions that targeted exactly the behaviour we needed to change.

**The two custom reward functions:**

```python
def json_format_reward(completion: str) -> float:
    """
    +1.0 for valid JSON with correct schema.
    -0.5 for anything else — prose, markdown, partial JSON, empty string.
    No partial credit.
    """
    try:
        parsed = json.loads(completion.strip())
        if "tool" in parsed and "parameters" in parsed:
            return 1.0
    except json.JSONDecodeError:
        pass
    return -0.5

def brevity_reward(completion: str) -> float:
    """
    Penalises verbosity. Every token above 40 costs reward.
    The model should output 10 tokens, not 128.
    """
    token_count = len(tokenizer.encode(completion))
    if token_count <= 15:   return  0.3
    elif token_count <= 40: return  0.0
    else: return -0.2 * (token_count / 40)
```

Total reward per step = environment step reward + `json_format_reward` + `brevity_reward`.

**Observed outcome:** within 50 GRPO steps, average completion length dropped from ~128 tokens to ~10 tokens. The model stopped explaining itself and started acting. Task 1 mean reward hit +1.000. Task 3 mean reward went from +0.01 (baseline) to +0.020 — the model learned to avoid the CI/CD bot trap.

**Training ran sequentially:** Task 1 checkpoint → Task 2 → Task 3, each building on the previous one.

Full pipeline: [Raj's Kaggle Notebook](https://www.kaggle.com/code/rajpatil01/final-grpo)

### The Environment as Live Reward Oracle

During GRPO training, the agent calls the deployed HF Space for every step. No local copy of the environment exists inside the training loop. The reward signal during training is identical to the reward signal during evaluation — same server, same trap logic, same seeded scenarios.

```python
# training/grpo_train.py
def collect_rollout(model, tokenizer, env_url: str, seed: int):
    data = requests.post(f"{env_url}/reset", params={"seed": seed}).json()
    env_id = data["env_id"]

    for _ in range(50):
        action = generate_action(model, tokenizer, data["observation"])

        step_data = requests.post(f"{env_url}/step", json={
            "env_id": env_id,
            "action": action,
        }).json()

        env_r    = step_data["reward"]
        format_r = json_format_reward(json.dumps(action), tokenizer)
        brevity_r = brevity_reward(json.dumps(action), tokenizer)
        total_reward = env_r + format_r + brevity_r

        # accumulate for GRPO update
        if step_data["done"]:
            break
```

---

## Layer 4: The Known Limitation (Context Window)

This deserves its own section because it's the difference between "bug" and "architectural constraint."

Task 2 (−0.300) and the partial score on Task 3 (+0.020 rather than higher) share the same root cause: **context window pressure at 10+ subscription steps**.

By step 22 on Task 3, the accumulated conversation history — system prompt, all prior observations, all prior actions — is long enough that the `software_id` the model correctly identified three steps earlier gets dropped during action generation. The model produces `execute_cancellation | software_id: None`. The model *knows* the right target. It identified it correctly via `query_software_metadata`. It just can't carry the specific ID string through 22 steps of accumulated context.

This is not a reasoning failure. The model's world model is correct. The failure is in the retrieval: the relevant fact is in the context window but too far back to be attended to reliably when generating the action.

The fix is a structured scratchpad — a JSON object the model updates each step with `{"processed_subs": [...], "pending_cancellations": [...], "bot_accounts": [...]}` — that keeps the most relevant working memory at the front of the prompt regardless of episode length. We designed this at 6 AM and ran out of time to implement it.

The architecture supports it cleanly. The `/state/{env_id}` endpoint already returns the full server-side state. The scratchpad pattern would use this to inject a compressed working memory into each observation, keeping the useful information at position 0 of the context rather than buried 22 steps back.

---

## Layer 5: The Frontend (`frontend/`)

The React/Vite dashboard has two jobs: make the demo legible to judges, and provide a manual evaluation mode for people who want to try navigating the environment themselves.

### Components

**Step Feed** — every tool call streams in as a colour-coded card. Green for safe information-gathering steps, amber for contract checks, red for cancellations, purple for `finish_audit`. Trap triggers show a `▲ TRAP TRIGGERED` banner inline. Reward is displayed per-step and as a running cumulative total.

**Observation Panel** — live view of the current state: users (bots highlighted in red), active subscriptions with costs, budget remaining, flagged accounts. Updates after every step.

**Reward Sparkline** — a per-step bar chart across the episode. Negative steps render as red bars; high positive steps (expensive safe cancellations) go bright green. You can see at a glance where the agent got tripped up.

**Mode Switch** — Agent Mode (GRPO model runs autonomously) vs Manual Mode (the judge issues tool calls directly). Manual Mode on Task 3 is the fastest way to demonstrate that the trap logic works — call `execute_cancellation` on `sw_204` without calling `query_software_metadata` first, and watch the `−1.00` penalty fire.

---

## Deployment: Docker + HuggingFace Spaces

```dockerfile
FROM python:3.11-slim
RUN pip install uv --no-cache-dir
WORKDIR /app
COPY pyproject.toml openenv.yaml ./
COPY server/ ./server/
RUN uv sync --frozen
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:7860/health || exit 1
CMD ["uv", "run", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

Port 7860 is mandatory for HF Spaces. The `openenv.yaml` `entry_point` field and the Dockerfile CMD both target it. The `openenv evaluate` CLI discovers the environment via the manifest and calls `/reset` and `/step` directly — no additional configuration needed.

---

## A Note on Why the Client/Server Split Matters Beyond Benchmarking

The architecture enforces something that matters in production, not just in hackathon evaluation.

If you build an enterprise audit agent where the LLM has direct database access — where it can read the subscription table directly instead of going through a tool layer — you've removed the audit trail. You can't log what the agent observed before making each decision. You can't reproduce a specific episode to understand why it cancelled the wrong account. You can't rate-limit the agent's access to sensitive billing data.

The OpenEnv client/server split maps directly to the architecture you'd want in a real deployment: the agent interacts with a controlled API surface, all state transitions are logged server-side, and the reward/outcome of every action is verifiable independently of what the agent claims it saw.

EnvAudit is a benchmark. But the design reflects a deployment pattern that a real enterprise SaaS auditor would need to follow anyway.

---

*EnvAudit · Meta × Scaler OpenEnv Hackathon 2026 · Bangalore*

*GRPO Training: [Kaggle — rajpatil01/final-grpo](https://www.kaggle.com/code/rajpatil01/final-grpo)*
*Evaluation: [Google Colab](https://colab.research.google.com/drive/1pMSBR8aASMvULXHbKb-lp1-6BrekDEee?usp=sharing)*
