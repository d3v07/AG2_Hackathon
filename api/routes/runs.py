"""Run submission and dashboard data routes."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from api.schemas import ApprovalBody, RunCreate
from api.routes.deps import get_tenant_id
from api.store import (
    create_run,
    get_run,
    get_run_status,
    list_runs,
    put_run,
    workflow_exists,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict[str, list[str]]:
    return {"run_ids": list_runs(tenant_id=tenant_id)}


@router.post("", status_code=202)
def submit_run_endpoint(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not workflow_exists(body.workflow_id, tenant_id=tenant_id):
        raise HTTPException(status_code=404, detail=f"workflow {body.workflow_id} not found")
    if body.task_spec is not None:
        raise HTTPException(
            status_code=400,
            detail="task_spec submission requires Zone A runtime wiring; submit raw_trace for now",
        )
    run = create_run(
        workflow_id=body.workflow_id,
        raw_trace=body.raw_trace,
        task_spec=body.task_spec,
        tenant_id=tenant_id,
    )
    from api.background import process_run

    background_tasks.add_task(process_run, run["run_id"], tenant_id)
    return run


@router.get("/{run_id}.js", response_class=Response)
def get_run_jsonp(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> Response:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    body = f"window.CONCORD_DATA = {payload};"
    return Response(content=body, media_type="application/javascript")


@router.get("/{run_id}/status")
def get_run_status_endpoint(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict[str, Any]:
    status = get_run_status(run_id, tenant_id=tenant_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return status


@router.get("/{run_id}")
def get_run_endpoint(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict[str, Any]:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return data


@router.post("/{run_id}/approval")
def post_approval(
    run_id: str,
    body: ApprovalBody,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if data.get("status") != "completed":
        raise HTTPException(status_code=409, detail="run must be completed before approval")
    if not isinstance(data.get("report"), dict) or "approval" not in data["report"]:
        raise HTTPException(status_code=409, detail="run report is not approval-ready")
    decision_norm = body.decision.lower()
    if decision_norm not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    data["report"]["approval"]["status"] = decision_norm.upper()
    data["report"]["approval"]["operator"] = body.operator
    if body.comments:
        data["report"]["approval"]["comments"] = body.comments
    put_run(
        run_id,
        data,
        status=data.get("status", "completed"),
        tenant_id=tenant_id,
        status_history=data.get("status_history"),
    )
    return {"run_id": run_id, "approval": data["report"]["approval"]}
