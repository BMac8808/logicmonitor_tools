"""FastAPI application factory."""

from __future__ import annotations

import hmac
import logging
import secrets
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .adapters.lm_mcp import build_registry
from .config import Settings
from .db import init_db, make_engine, session_factory
from .knowledge import KnowledgeBase
from .llm import LLMProvider, build_provider

log = logging.getLogger("se_pov_builder")


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None,
               mcp_transport: httpx.BaseTransport | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # httpx logs full request URLs at INFO; keep outbound (LLM) call details out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    engine = make_engine(settings.database_url)
    init_db(engine)

    app = FastAPI(
        title="SE Demo & POV Builder",
        version=__version__,
        description="Community tool for planning technical sales engagements. "
                    "Not an official LogicMonitor product. Synthetic data only.",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.kb = KnowledgeBase.load(settings.content_dir)
    app.state.adapters = build_registry(settings, settings.content_dir / "adapters" / "mock_responses", mcp_transport)
    app.state.llm = llm or build_provider(settings)
    # Signs transcript proposals so accept only takes quotes this server found. Held in memory only:
    # receipts lapse on restart, and the transcript itself is never stored.
    app.state.receipt_key = secrets.token_bytes(32)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def auth_and_log(request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        if settings.api_token and path.startswith("/api/") and path != "/api/health" and request.method != "OPTIONS":
            supplied = request.headers.get("authorization", "")
            expected = f"Bearer {settings.api_token}"
            if not hmac.compare_digest(supplied.encode(), expected.encode()):
                return JSONResponse({"detail": "Missing or invalid API token"}, status_code=401)
        response = await call_next(request)
        # Log method, path, status and timing only. Bodies and headers are never logged.
        log.info("%s %s %s %.1fms", request.method, path, response.status_code,
                 (time.perf_counter() - start) * 1000)
        return response

    from .api import deals, discovery, integrations, meta, plans, workflows

    for module in (meta, deals, discovery, plans, workflows, integrations):
        app.include_router(module.router, prefix="/api")

    dist = settings.frontend_dist
    if dist and (dist / "index.html").exists():
        index = dist / "index.html"
        root = dist.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = (dist / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
            return FileResponse(index)

    return app
