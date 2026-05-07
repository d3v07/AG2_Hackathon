"""Shared API route dependencies."""
from __future__ import annotations

import hmac
import json
import os
from typing import Annotated

from fastapi import Header, HTTPException


def _tenant_keys() -> dict[str, str]:
    raw = os.environ.get("CONCORD_TENANT_KEYS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="tenant key configuration is invalid") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="tenant key configuration is invalid")
    return {str(tenant): str(key) for tenant, key in parsed.items()}


def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    x_concord_api_key: Annotated[str | None, Header(alias="X-Concord-API-Key")] = None,
) -> str:
    tenant_id = (x_tenant_id or "local").strip()
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID cannot be empty")
    if len(tenant_id) > 64 or any(char not in allowed for char in tenant_id):
        raise HTTPException(status_code=400, detail="X-Tenant-ID contains invalid characters")
    if tenant_id == "local":
        return tenant_id

    expected_key = _tenant_keys().get(tenant_id)
    if not expected_key:
        raise HTTPException(status_code=401, detail="tenant credentials are not configured")
    if not x_concord_api_key or not hmac.compare_digest(x_concord_api_key, expected_key):
        raise HTTPException(status_code=401, detail="invalid tenant credentials")
    return tenant_id
