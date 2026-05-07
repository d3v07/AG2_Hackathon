"""Workflow registration routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.schemas import WorkflowCreate
from api.routes.deps import get_tenant_id
from api.store import create_workflow, get_workflow, list_workflows

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _validate_contracts(contracts: list[dict]) -> None:
    required = {"id", "type", "rule"}
    for index, contract in enumerate(contracts):
        if not isinstance(contract, dict):
            raise HTTPException(status_code=400, detail=f"contracts[{index}] must be an object")
        missing = sorted(required - set(contract.keys()))
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"contracts[{index}] missing required field(s): {', '.join(missing)}",
            )


@router.post("")
def create_workflow_endpoint(
    body: WorkflowCreate,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    payload = body.model_dump()
    _validate_contracts(payload["contracts"])
    workflow = create_workflow(payload, tenant_id=tenant_id)
    return {"workflow_id": workflow["workflow_id"], **workflow}


@router.get("")
def list_workflows_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict[str, list[dict]]:
    return {"workflows": list_workflows(tenant_id=tenant_id)}


@router.get("/{workflow_id}")
def get_workflow_endpoint(
    workflow_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    workflow = get_workflow(workflow_id, tenant_id=tenant_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"workflow {workflow_id} not found")
    return workflow
