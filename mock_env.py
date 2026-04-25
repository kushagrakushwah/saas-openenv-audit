from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/reset")
def reset(seed: int = None):
    return {
        "env_id": "mock-123", 
        "observation": {
            "users": [{"user_id": "u1", "user_type": "human"}, {"user_id": "bot-ci", "user_type": "bot"}], 
            "subscriptions": [{"subscription_id": "sub-aws", "software": "AWS", "monthly_cost": 1500}], 
            "budget_remaining": 50000
        }
    }

@app.post("/step")
def step(action: dict):
    return {
        "reward": random.uniform(-1, 2),
        "done": False,
        "observation": {"budget_remaining": 49000},
        "info": {"trap": None, "savings_usd": 100}
    }