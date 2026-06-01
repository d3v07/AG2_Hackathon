"""API key management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import (
    AuthError,
    api_key_count,
    authenticate_request,
    create_api_key,
    has_api_keys,
    is_local_request,
    public_auth_payload,
)
from api.routes.deps import get_tenant_id
from api.schemas import ApiKeyCreate

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


@router.get("/status")
def api_key_status_endpoint(request: Request) -> dict:
    keys_exist = has_api_keys()
    authenticated_tenant = ""
    has_candidate_key = bool(
        request.headers.get("authorization", "").strip()
        or request.headers.get("x-concord-api-key", "").strip()
    )
    if has_candidate_key:
        try:
            authenticated_tenant = authenticate_request(request)
        except AuthError:
            authenticated_tenant = ""
    return {
        "requires_api_key": keys_exist,
        "can_create_first_key": not keys_exist and is_local_request(request),
        "authenticated": bool(authenticated_tenant),
        "tenant_id": authenticated_tenant,
    }


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
