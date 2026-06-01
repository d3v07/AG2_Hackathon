"""Same-origin public run submission relay."""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.auth import AuthError, validate_tenant_id
from api.routes.runs import submit_run_for_tenant
from api.schemas import RunCreate

router = APIRouter(prefix="/api/public", tags=["public"])


def _public_tenant_id() -> str:
    try:
        return validate_tenant_id(os.environ.get("CONCORD_PUBLIC_TENANT_ID") or "local")
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/runs", status_code=202)
def submit_public_run_endpoint(
    body: RunCreate,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    if os.environ.get("CONCORD_PUBLIC_RUNS_ENABLED") != "1":
        raise HTTPException(status_code=403, detail="public run submission is disabled")
    if body.raw_trace is not None:
        raise HTTPException(status_code=400, detail="public run submission accepts task_spec only")
    return submit_run_for_tenant(body, background_tasks, _public_tenant_id())
