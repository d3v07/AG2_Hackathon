"""FastAPI middleware for API key auth."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.auth import AuthError, authenticate_request


def _is_public_api_request(request: Request) -> bool:
    path = request.url.path
    if request.method == "OPTIONS":
        return True
    if path == "/api/health":
        return True
    if request.method == "POST" and path == "/api/public/runs":
        return True
    if request.method == "POST" and path == "/api/public/workflows":
        return True
    if path.startswith("/api/runs/") and path.endswith("/events"):
        return bool(request.query_params.get("stream_token"))
    if path.startswith("/api/runs/") and path.endswith(".js"):
        return bool(request.query_params.get("stream_token"))
    return False


class ApiAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/") or _is_public_api_request(request):
            return await call_next(request)
        try:
            request.state.tenant_id = authenticate_request(request)
        except AuthError as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)
