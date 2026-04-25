from pydantic import BaseModel
from typing import Any, Dict, Optional

class StepRequest(BaseModel):
    env_id: str
    action: Dict[str, Any]

class ResetResponse(BaseModel):
    env_id: str
    observation: Dict[str, Any]

class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]

class StateResponse(BaseModel):
    state: Dict[str, Any]