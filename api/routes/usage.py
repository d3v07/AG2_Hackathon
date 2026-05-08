"""Tenant usage and cost routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.routes.deps import get_tenant_id
from api.store import get_tenant_usage

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


@router.get("/usage")
def get_tenant_usage_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    period: str = Query(default="all", pattern="^all$"),
) -> dict:
    return get_tenant_usage(tenant_id=tenant_id, period=period)
