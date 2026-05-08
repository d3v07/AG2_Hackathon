"""API key management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.auth import api_key_count, create_api_key, public_auth_payload
from api.routes.deps import get_tenant_id
from api.schemas import ApiKeyCreate

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.post("", status_code=201)
def create_api_key_endpoint(
    body: ApiKeyCreate,
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    existing_count = api_key_count()
    target_tenant_id = body.tenant_id or tenant_id
    if existing_count and target_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="cannot create an API key for another tenant")
    return public_auth_payload(create_api_key(tenant_id=target_tenant_id, name=body.name))
