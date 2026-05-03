"""FastAPI app — local dev server + Vercel serverless entry.

Routes:
    GET  /api/runs                 — list run ids
    GET  /api/runs/{run_id}        — return CONCORD_DATA for run
    GET  /api/runs/{run_id}.js     — same payload as JSONP-style window assignment
    POST /api/runs/{run_id}/approval — set approval status

Vercel Python runtime auto-detects the `app` ASGI export.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.store import get_run, list_runs, put_run  # noqa: E402

app = FastAPI(title="Concord Lite API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ApprovalBody(BaseModel):
    decision: str  # "approved" | "rejected"
    operator: str = "j.kowalski"
    comments: str = ""


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs_endpoint() -> dict[str, list[str]]:
    return {"run_ids": list_runs()}


@app.get("/api/runs/{run_id}.js", response_class=Response)
def get_run_jsonp(run_id: str) -> Response:
    """Return the run as a JS file that assigns window.CONCORD_DATA."""
    data = get_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    payload = json.dumps(data, ensure_ascii=False)
    body = f"window.CONCORD_DATA = {payload};"
    return Response(content=body, media_type="application/javascript")


@app.get("/api/runs/{run_id}")
def get_run_endpoint(run_id: str) -> dict[str, Any]:
    data = get_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return data


@app.post("/api/runs/{run_id}/approval")
def post_approval(run_id: str, body: ApprovalBody) -> dict[str, Any]:
    data = get_run(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    decision_norm = body.decision.lower()
    if decision_norm not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    data["report"]["approval"]["status"] = decision_norm.upper()
    data["report"]["approval"]["operator"] = body.operator
    if body.comments:
        data["report"]["approval"]["comments"] = body.comments
    put_run(run_id, data)
    return {"run_id": run_id, "approval": data["report"]["approval"]}


_PUBLIC_DIR = _ROOT / "public"
if _PUBLIC_DIR.is_dir() and not os.environ.get("VERCEL"):
    app.mount("/", StaticFiles(directory=str(_PUBLIC_DIR), html=True), name="static")
