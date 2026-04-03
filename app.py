"""
app.py — FastAPI entrypoint for EnvAudit.

Architecture:
  The openenv validator pings POST /reset — so the DEFAULT task (task1_easy)
  is mounted at ROOT via create_fastapi_app(), giving us /reset /step /state
  for free.

  For task2_medium and task3_hard we create separate FastAPI sub-apps and
  mount them under named prefixes, so all three tasks are accessible:

    POST /reset               → task1_easy  (default, for validator ping)
    POST /step
    GET  /state

    POST /task1_easy/reset    → task1_easy  (explicit)
    POST /task1_easy/step
    GET  /task1_easy/state

    POST /task2_medium/reset  → task2_medium
    POST /task2_medium/step
    GET  /task2_medium/state

    POST /task3_hard/reset    → task3_hard
    POST /task3_hard/step
    GET  /task3_hard/state

    GET  /info                → health check + task listing
"""
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openenv.core.env_server import create_fastapi_app

from models import AuditAction, AuditObservation
from environment import AuditEnvironment


def _factory(task: str):
    """Return a zero-arg callable — required by create_fastapi_app."""
    def make():
        return AuditEnvironment(task_name=task)
    return make


# ── Root app: task1_easy at / (gives /reset /step /state for the validator) ─
app = create_fastapi_app(
    _factory("task1_easy"),
    AuditAction,
    AuditObservation,
)

# ── Sub-apps for each named task ─────────────────────────────────────────────
for _task in ("task1_easy", "task2_medium", "task3_hard"):
    _sub = create_fastapi_app(
        _factory(_task),
        AuditAction,
        AuditObservation,
    )
    app.mount(f"/{_task}", _sub)


# ── Info endpoint ─────────────────────────────────────────────────────────────
@app.get("/info")
async def info():
    return JSONResponse({
        "status":       "ok",
        "name":         "EnvAudit",
        "version":      "1.0.0",
        "default_task": "task1_easy",
        "note": (
            "POST /reset and POST /step use task1_easy by default. "
            "Use /<task_name>/reset and /<task_name>/step for specific tasks."
        ),
        "tasks": {
            "task1_easy": {
                "paths":      ["/reset", "/step", "/state", "/task1_easy/reset"],
                "difficulty": "easy",
                "description": (
                    "The Basic Join. Cancel the single inactive seat "
                    "(60+ days no login). Grader: binary 1.0 / 0.0."
                ),
            },
            "task2_medium": {
                "paths":      ["/task2_medium/reset", "/task2_medium/step",
                               "/task2_medium/state"],
                "difficulty": "medium",
                "description": (
                    "Batch Processing & Safety. 5 inactive + 5 active seats. "
                    "+0.2 per correct cancel; immediate 0.0 if any active user cancelled."
                ),
            },
            "task3_hard": {
                "paths":      ["/task3_hard/reset", "/task3_hard/step",
                               "/task3_hard/state"],
                "difficulty": "hard",
                "description": (
                    "The Traps. Service-account trap + annual-contract trap. "
                    "Immediate 0.0 on any trap; partial credit otherwise."
                ),
            },
        },
    })