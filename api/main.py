"""
FastAPI backend for the ProDet Agent web UI.

Exposes:
  POST /api/chat/stream  — SSE-streamed agent responses
  GET  /api/projects      — available project folders
  GET  /api/agents        — available agent metadata
  GET  /api/health        — health check
"""

import json
import logging
import os
import sys
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

# Ensure the project root is on sys.path so we can import agents
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Startup diagnostic: surface ProDet runtime issues immediately rather than
# at the first tool call. Non-fatal — non-ProDet agents still work.
try:
    from prodet_agent import check_prodet_runtime
    _runtime_status = check_prodet_runtime()
    if _runtime_status["ok"]:
        logger.info(
            f"[ProDet runtime OK] python={_runtime_status['prodet_python']} "
            f"root={_runtime_status['prodet_root']}"
        )
    else:
        logger.warning(
            "[ProDet runtime NOT READY] %s\n"
            "ProDet tools will fail until this is fixed. "
            "Non-ProDet agents (config, scheduling, procurement) still work.",
            _runtime_status["message"],
        )
except Exception as _e:
    logger.warning(f"Could not run ProDet runtime check: {_e}")
    _runtime_status = {"ok": False, "message": str(_e)}

app = FastAPI(title="ProDet Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    project: Optional[str] = None
    chat_history: Optional[list[ChatMessage]] = None
    forced_agent: Optional[str] = None  # bypass router when set


# ---------------------------------------------------------------------------
# Lazy-loaded team instance (one per process)
# ---------------------------------------------------------------------------

_team_lock = threading.Lock()
_team = None
_token_cb = None


def _get_team():
    global _team, _token_cb
    if _team is None:
        with _team_lock:
            if _team is None:
                from utils.token_logger import TokenCounterCallback
                from reinforcement_team import ProDetAgentTeam
                _token_cb = TokenCounterCallback(agent_name="prodet-agent")
                _team = ProDetAgentTeam(token_callback=_token_cb)
    return _team, _token_cb


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "ProDet Agent API running",
        "prodet_runtime": _runtime_status,
    }


@app.get("/api/agents")
def list_agents():
    """Return metadata for all available agents."""
    from reinforcement_team import AGENT_LABELS
    return {"agents": AGENT_LABELS}


@app.get("/api/projects")
def list_projects():
    """Return available project folder names."""
    from paths import RC_AGENT_PROJECTS
    if not os.path.isdir(RC_AGENT_PROJECTS):
        return {"projects": []}
    projects = sorted(
        d for d in os.listdir(RC_AGENT_PROJECTS)
        if os.path.isdir(os.path.join(RC_AGENT_PROJECTS, d))
    )
    return {"projects": projects}


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """Stream agent response as Server-Sent Events."""

    def event_generator():
        try:
            team, token_cb = _get_team()

            # Build LangChain message history
            from langchain_core.messages import HumanMessage, AIMessage
            chat_history = []
            if req.chat_history:
                for msg in req.chat_history:
                    if msg.role == "user":
                        chat_history.append(HumanMessage(content=msg.content))
                    elif msg.role == "assistant":
                        chat_history.append(AIMessage(content=msg.content))

            # Build message with project context
            query = req.query
            if req.project:
                query = f"[Active project: {req.project} — use projects/{req.project}/ for all file paths]\n{query}"

            # Route to the right agent and run
            response, target = team.run(
                query,
                chat_history=chat_history,
                forced_agent=req.forced_agent,
            )

            # Emit in chunks to give the UI a streaming feel
            chunk_size = 12
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i + chunk_size]
                yield "data: " + json.dumps({"token": chunk}, ensure_ascii=False) + "\n\n"

            # Emit cost info
            cost = sum(s.cost for s in token_cb.agent_stats.values()) if token_cb else 0
            yield "data: " + json.dumps({
                "done": True,
                "routed_to": target,
                "session_cost": round(cost, 6),
            }, ensure_ascii=False) + "\n\n"

        except Exception as e:
            logger.exception("Chat stream error")
            yield "data: " + json.dumps({"error": str(e)}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
