"""FastAPI application composition root."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from assureai_api import __version__
from assureai_api.config import Settings, get_settings
from assureai_api.logging import configure_logging
from assureai_api.schemas import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application instance with injectable configuration."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = True
        yield
        app.state.ready = False

    application = FastAPI(
        title=resolved_settings.app_name,
        version=__version__,
        description="Document intelligence and verification API.",
        lifespan=lifespan,
    )
    application.state.ready = False
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["operations"], response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="api", version=__version__)

    @application.get("/ready", tags=["operations"], response_model=HealthResponse)
    async def ready(request: Request) -> HealthResponse:
        # Database/Redis checks will be added when those dependencies are used in Milestone 1.
        if not request.app.state.ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Application startup is incomplete",
            )
        return HealthResponse(status="ready", service="api", version=__version__)

    return application


app = create_app()
