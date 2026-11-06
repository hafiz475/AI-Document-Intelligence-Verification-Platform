"""FastAPI application composition root."""

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from assureai_api import __version__
from assureai_api.config import Settings, get_settings
from assureai_api.database import create_database_engine, create_session_factory
from assureai_api.logging import configure_logging
from assureai_api.routes import router
from assureai_api.schemas import HealthResponse
from assureai_api.storage import LocalDocumentStorage


def create_app(
    settings: Settings | None = None,
    enqueue_document: Callable[[str], object] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)
    database_url = resolved_settings.database_url or "sqlite:///./assureai.db"
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    storage = LocalDocumentStorage(resolved_settings.storage_path)
    redis_client = (
        Redis.from_url(resolved_settings.redis_url) if resolved_settings.redis_url else None
    )

    def dependencies_ready() -> bool:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            if redis_client is not None:
                redis_client.ping()
            return True
        except Exception:
            return False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = dependencies_ready()
        yield
        app.state.ready = False
        if redis_client is not None:
            redis_client.close()
        engine.dispose()

    application = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Project-scoped document ingestion and processing API.",
        lifespan=lifespan,
    )
    application.state.ready = False
    application.state.settings = resolved_settings
    application.state.session_factory = session_factory
    application.state.storage = storage
    if enqueue_document is None:
        from assureai_api.queue import enqueue_document as default_enqueue

        enqueue_document = default_enqueue
    application.state.enqueue_document = enqueue_document
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.get("/health", tags=["operations"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="api", version=__version__)

    @application.get("/ready", tags=["operations"], response_model=HealthResponse)
    async def ready(request: Request) -> HealthResponse:
        request.app.state.ready = dependencies_ready()
        if not request.app.state.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A required dependency is unavailable",
            )
        return HealthResponse(status="ready", service="api", version=__version__)

    application.include_router(router)
    return application


app = create_app()
