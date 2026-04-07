"""
client.py — Typed HTTP client for the SaaS Audit environment.

No dependency on openenv-core — uses plain `requests` so it works
regardless of openenv-core version.

Usage (server must already be running):
    from client import AuditEnv
    from models import AuditAction

    with AuditEnv(base_url="http://localhost:7860/task1_easy") as env:
        result = env.reset()
        result = env.step(AuditAction(tool="get_employee_logins"))
        print(result.observation, result.reward, result.done)
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

from models import AuditAction, AuditObservation, AuditState


@dataclass
class StepResult:
    """Mirrors the OpenEnv StepResult interface."""
    observation: AuditObservation
    reward: float = 0.0
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)


class AuditEnv:
    """
    Synchronous HTTP client for AuditEnvironment.

    Context-manager usage:
        with AuditEnv(base_url="http://localhost:7860/task1_easy") as env:
            result = env.reset()

    .sync() alias for compatibility with train.py's:
        with AuditEnv(base_url=url).sync() as env:
    """

    def __init__(
        self,
        base_url: str = "http://localhost:7860/task1_easy",
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------ #
    # Context-manager & cleanup                                            #
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "AuditEnv":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def sync(self) -> "AuditEnv":
        """Alias — allows `with AuditEnv(...).sync() as env:` pattern."""
        return self

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._session.close()

    # ------------------------------------------------------------------ #
    # OpenEnv interface                                                    #
    # ------------------------------------------------------------------ #

    def reset(self) -> StepResult:
        resp = self._session.post(f"{self.base_url}/reset", timeout=self.timeout)
        resp.raise_for_status()
        return self._parse(resp.json())

    def step(self, action: AuditAction) -> StepResult:
        payload: Dict[str, Any] = {
            "tool":     action.tool,
            "metadata": action.metadata or {},
        }
        if action.software_id is not None:
            payload["software_id"] = action.software_id

        resp = self._session.post(
            f"{self.base_url}/step",
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._parse(resp.json())

    def get_state(self) -> AuditState:
        resp = self._session.get(f"{self.base_url}/state", timeout=self.timeout)
        resp.raise_for_status()
        return AuditState(**resp.json())

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse(payload: dict) -> StepResult:
        obs_data = payload.get("observation", payload)
        observation = AuditObservation(
            tool_result=obs_data.get("tool_result", {}),
            last_action_error=obs_data.get("last_action_error"),
            step=obs_data.get("step", 0),
            done=obs_data.get("done", False),
            reward=obs_data.get("reward", 0.0),
            metadata=obs_data.get("metadata", {}),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
            info=payload.get("info", {}),
        )