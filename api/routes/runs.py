"""Run submission and dashboard data routes."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import EventSourceResponse

from api.events import TERMINAL_STATUSES, replay_status_events, run_event_bus, run_event_tokens
from api.schemas import ApprovalBody, RunCreate
from api.routes.deps import get_tenant_id
from api.store import (
    create_run,
    get_run,
    get_run_status,
    list_runs,
    put_run,
    workflow_exists,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs_endpoint(tenant_id: str = Depends(get_tenant_id)) -> dict[str, list[str]]:
    return {"run_ids": list_runs(tenant_id=tenant_id)}


@router.post("", status_code=202)
def submit_run_endpoint(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, str]:
    if not workflow_exists(body.workflow_id, tenant_id=tenant_id):
        raise HTTPException(status_code=404, detail=f"workflow {body.workflow_id} not found")
    if body.task_spec is not None:
        raise HTTPException(
            status_code=400,
            detail="task_spec submission requires Zone A runtime wiring; submit raw_trace for now",
        )
    run = create_run(
        workflow_id=body.workflow_id,
        raw_trace=body.raw_trace,
        task_spec=body.task_spec,
        tenant_id=tenant_id,
    )
    from api.background import process_run

    background_tasks.add_task(process_run, run["run_id"], tenant_id)
    return run


@router.get("/{run_id}.js", response_class=Response)
def get_run_jsonp(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> Response:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    body = f"window.CONCORD_DATA = {payload};"
    return Response(content=body, media_type="application/javascript")


@router.get("/{run_id}/status")
def get_run_status_endpoint(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict[str, Any]:
    status = get_run_status(run_id, tenant_id=tenant_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return status


STREAM_TOKEN_TTL_SECONDS = 300


@router.post("/{run_id}/events/token")
def create_run_events_token_endpoint(
    run_id: str,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    status = get_run_status(run_id, tenant_id=tenant_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    token = run_event_tokens.create(
        tenant_id,
        run_id,
        ttl_seconds=STREAM_TOKEN_TTL_SECONDS,
    )
    return {"stream_token": token, "expires_in": STREAM_TOKEN_TTL_SECONDS}


def _parse_last_event_id(request: Request) -> int:
    raw = request.headers.get("last-event-id")
    if not raw:
        return 0
    try:
        sequence = int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be an integer") from exc
    if sequence < 0:
        raise HTTPException(status_code=400, detail="Last-Event-ID must be non-negative")
    return sequence


def _event_after(event: dict[str, Any], sequence: int) -> bool:
    return int(event.get("sequence", 0)) > sequence


def _server_event(event: dict[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False)
    return (
        f"id: {event['sequence']}\n"
        f"event: {event['type']}\n"
        "retry: 1500\n"
        f"data: {data}\n\n"
    )


@router.get("/{run_id}/events")
async def get_run_events_endpoint(
    run_id: str,
    request: Request,
    stream_token: str | None = Query(default=None),
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
    x_concord_api_key: Annotated[str | None, Header(alias="X-Concord-API-Key")] = None,
) -> EventSourceResponse:
    if stream_token:
        tenant_id = run_event_tokens.validate(stream_token, run_id)
        if tenant_id is None:
            raise HTTPException(status_code=401, detail="invalid or expired stream token")
    else:
        tenant_id = get_tenant_id(x_tenant_id, x_concord_api_key)

    status = get_run_status(run_id, tenant_id=tenant_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")

    last_sequence = _parse_last_event_id(request)

    async def event_stream() -> AsyncIterator[str]:
        sent_sequence = last_sequence
        replayed = replay_status_events(status)
        for event in replayed:
            if not _event_after(event, sent_sequence):
                continue
            sent_sequence = event["sequence"]
            yield _server_event(event)
        if replayed and replayed[-1]["status"] in TERMINAL_STATUSES:
            return

        subscription = run_event_bus.subscribe(tenant_id, run_id)
        try:
            latest_status = get_run_status(run_id, tenant_id=tenant_id)
            if latest_status is not None and latest_status != status:
                latest_replay = replay_status_events(latest_status)
                for event in latest_replay:
                    if not _event_after(event, sent_sequence):
                        continue
                    sent_sequence = event["sequence"]
                    yield _server_event(event)
                if latest_replay and latest_replay[-1]["status"] in TERMINAL_STATUSES:
                    return

            while not await request.is_disconnected():
                event = await asyncio.to_thread(subscription.get, 0.25)
                if event is None:
                    continue
                if not _event_after(event, sent_sequence):
                    continue
                sent_sequence = event["sequence"]
                yield _server_event(event)
                if event["status"] in TERMINAL_STATUSES:
                    return
        finally:
            subscription.close()

    return EventSourceResponse(event_stream())


@router.get("/{run_id}")
def get_run_endpoint(run_id: str, tenant_id: str = Depends(get_tenant_id)) -> dict[str, Any]:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return data


@router.post("/{run_id}/approval")
def post_approval(
    run_id: str,
    body: ApprovalBody,
    tenant_id: str = Depends(get_tenant_id),
) -> dict[str, Any]:
    data = get_run(run_id, tenant_id=tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    if data.get("status") != "completed":
        raise HTTPException(status_code=409, detail="run must be completed before approval")
    if not isinstance(data.get("report"), dict) or "approval" not in data["report"]:
        raise HTTPException(status_code=409, detail="run report is not approval-ready")
    decision_norm = body.decision.lower()
    if decision_norm not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    data["report"]["approval"]["status"] = decision_norm.upper()
    data["report"]["approval"]["operator"] = body.operator
    if body.comments:
        data["report"]["approval"]["comments"] = body.comments
    put_run(
        run_id,
        data,
        status=data.get("status", "completed"),
        tenant_id=tenant_id,
        status_history=data.get("status_history"),
    )
    return {"run_id": run_id, "approval": data["report"]["approval"]}
