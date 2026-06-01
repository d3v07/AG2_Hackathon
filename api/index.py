"""FastAPI app — local dev server + Vercel serverless entry.

Routes:
    GET  /api/runs                  — list run ids
    POST /api/runs                  — submit an async run
    GET  /api/runs/{run_id}         — return CONCORD_DATA for run
    GET  /api/runs/{run_id}/status  — return run status
    GET  /api/workflows             — list workflow registrations
    POST /api/workflows             — register a workflow

Vercel Python runtime auto-detects the `app` ASGI export.
"""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.middleware import ApiAuthMiddleware  # noqa: E402
from api.routes.api_keys import router as api_keys_router  # noqa: E402
from api.routes.public_workflows import router as public_workflows_router  # noqa: E402
from api.routes.public_runs import router as public_runs_router  # noqa: E402
from api.routes.runs import router as runs_router  # noqa: E402
from api.routes.usage import router as usage_router  # noqa: E402
from api.routes.workflows import router as workflows_router  # noqa: E402
from api.store import ensure_store, recover_interrupted_runs  # noqa: E402


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_store()
    recover_interrupted_runs()
    yield


app = FastAPI(title="Concord API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(ApiAuthMiddleware)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(workflows_router)
app.include_router(runs_router)
app.include_router(public_runs_router)
app.include_router(public_workflows_router)
app.include_router(api_keys_router)
app.include_router(usage_router)


_PUBLIC_DIR = _ROOT / "public"
if _PUBLIC_DIR.is_dir() and not os.environ.get("VERCEL"):
    app.mount("/", StaticFiles(directory=str(_PUBLIC_DIR), html=True), name="static")
