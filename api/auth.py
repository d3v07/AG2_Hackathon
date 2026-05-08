"""API key authentication and tenant resolution."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from sqlmodel import select

from api.db import session_scope
from api.models import ApiKeyRecord, _utc_now

_TENANT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


@dataclass(frozen=True)
class AuthError(Exception):
    status_code: int
    detail: str


def validate_tenant_id(raw_tenant_id: str | None) -> str:
    tenant_id = (raw_tenant_id or "local").strip()
    if not tenant_id:
        raise AuthError(400, "tenant_id cannot be empty")
    if len(tenant_id) > 64 or any(char not in _TENANT_CHARS for char in tenant_id):
        raise AuthError(400, "tenant_id contains invalid characters")
    return tenant_id


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_count() -> int:
    with session_scope() as session:
        return len(session.exec(select(ApiKeyRecord)).all())


def has_api_keys() -> bool:
    return api_key_count() > 0


def is_local_request(request: Request) -> bool:
    if os.environ.get("CONCORD_ALLOW_DEV_AUTH") == "1":
        return True
    client_host = request.client.host if request.client else ""
    host_header = request.headers.get("host", "").split(":", 1)[0]
    local_hosts = {"127.0.0.1", "::1", "localhost", "testclient"}
    return client_host in local_hosts or host_header in local_hosts


def create_api_key(*, tenant_id: str, name: str = "") -> dict[str, str]:
    tenant_id = validate_tenant_id(tenant_id)
    api_key = f"concord_{secrets.token_urlsafe(32)}"
    record = ApiKeyRecord(
        tenant_id=tenant_id,
        name=name.strip(),
        key_hash=_hash_key(api_key),
        key_prefix=api_key[:16],
    )
    with session_scope() as session:
        session.add(record)
        session.commit()
        session.refresh(record)
        return {
            "api_key_id": record.api_key_id,
            "tenant_id": record.tenant_id,
            "name": record.name,
            "key_prefix": record.key_prefix,
            "api_key": api_key,
        }


def _tenant_keys() -> dict[str, str]:
    raw = os.environ.get("CONCORD_TENANT_KEYS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthError(500, "tenant key configuration is invalid") from exc
    if not isinstance(parsed, dict):
        raise AuthError(500, "tenant key configuration is invalid")
    return {str(tenant): str(key) for tenant, key in parsed.items()}


def _authorization_bearer(request: Request) -> str:
    authorization = request.headers.get("authorization", "").strip()
    if not authorization:
        return ""
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        raise AuthError(401, "invalid authorization header")
    return value.strip()


def _lookup_api_key(api_key: str) -> ApiKeyRecord | None:
    if not api_key:
        return None
    key_hash = _hash_key(api_key)
    with session_scope() as session:
        record = session.exec(
            select(ApiKeyRecord).where(
                ApiKeyRecord.key_hash == key_hash,
                ApiKeyRecord.revoked_at == "",
            )
        ).first()
        if record is None:
            return None
        record.last_used_at = _utc_now()
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def _legacy_header_tenant(tenant_id: str, api_key: str) -> str | None:
    if tenant_id == "local" and not api_key:
        return None
    expected_key = _tenant_keys().get(tenant_id)
    if not expected_key:
        if tenant_id == "local" and not has_api_keys():
            return "local"
        raise AuthError(401, "tenant credentials are not configured")
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise AuthError(401, "invalid tenant credentials")
    return tenant_id


def authenticate_request(request: Request) -> str:
    tenant_header = request.headers.get("x-tenant-id")
    tenant_id = validate_tenant_id(tenant_header)
    bearer_key = _authorization_bearer(request)
    header_key = request.headers.get("x-concord-api-key", "").strip()
    candidate_key = bearer_key or header_key

    if candidate_key:
        record = _lookup_api_key(candidate_key)
        if record is not None:
            if tenant_header and record.tenant_id != tenant_id:
                raise AuthError(403, "API key tenant mismatch")
            return record.tenant_id
        legacy_tenant = _legacy_header_tenant(tenant_id, header_key)
        if legacy_tenant is not None:
            return legacy_tenant
        raise AuthError(401, "invalid API key")

    if tenant_header and tenant_id != "local":
        if not has_api_keys():
            raise AuthError(401, "tenant credentials are not configured")
        raise AuthError(401, "missing API key")
    if has_api_keys():
        raise AuthError(401, "missing API key")
    if not is_local_request(request):
        raise AuthError(401, "missing API key")
    return "local"


def tenant_id_from_request(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return str(tenant_id)
    return authenticate_request(request)


def public_auth_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "api_key_id": payload["api_key_id"],
        "tenant_id": payload["tenant_id"],
        "name": payload["name"],
        "key_prefix": payload["key_prefix"],
        "api_key": payload["api_key"],
    }
