"""Shared API route dependencies."""
from __future__ import annotations

from fastapi import Request

from api.auth import AuthError, tenant_id_from_request


def get_tenant_id(request: Request) -> str:
    try:
        return tenant_id_from_request(request)
    except AuthError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
