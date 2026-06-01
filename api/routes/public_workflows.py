"""Same-origin public workflow import relay."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from api.auth import AuthError, validate_tenant_id
from api.routes.workflows import create_workflow_for_tenant
from api.schemas import WorkflowCreate

router = APIRouter(prefix="/api/public", tags=["public"])


def _public_tenant_id() -> str:
    try:
        return validate_tenant_id(os.environ.get("CONCORD_PUBLIC_TENANT_ID") or "local")
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/workflows")
def create_public_workflow_endpoint(body: WorkflowCreate) -> dict:
    if os.environ.get("CONCORD_PUBLIC_WORKFLOWS_ENABLED") != "1":
        raise HTTPException(status_code=403, detail="public workflow import is disabled")
    return create_workflow_for_tenant(body, _public_tenant_id())
