from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class ConcordAPIError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Concord API returned HTTP {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class ConcordClient:
    def __init__(
        self,
        api_url: str,
        *,
        api_key: str = "",
        tenant_id: str = "local",
        timeout: float = 30.0,
        transport: Any = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.timeout = timeout
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.tenant_id:
            headers["X-Tenant-ID"] = self.tenant_id
        if self.api_key:
            headers["X-Concord-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> Any:
        headers = self._headers()
        if self.transport is not None:
            response = self.transport(
                method,
                path,
                headers=headers,
                json_body=json_body,
                timeout=self.timeout,
            )
            return self._decode_response(response.status_code, response.text, response.json)

        payload = None
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
        request = Request(
            f"{self.api_url}{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return self._decode_response(response.status, body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            raise ConcordAPIError(exc.code, body) from exc

    def _decode_response(self, status_code: int, text: str, json_loader: Any = None) -> Any:
        if status_code >= 400:
            raise ConcordAPIError(status_code, text)
        if json_loader is not None:
            return json_loader()
        if not text:
            return None
        return json.loads(text)

    def register_workflow(self, definition: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/workflows", definition)

    def list_workflows(self) -> dict[str, Any]:
        return self._request("GET", "/api/workflows")

    def submit_run(self, workflow_id: str, raw_trace: dict[str, Any]) -> dict[str, str]:
        return self._request(
            "POST",
            "/api/runs",
            {"workflow_id": workflow_id, "raw_trace": raw_trace},
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/runs/{run_id}")

    def get_status(self, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/runs/{run_id}/status")
