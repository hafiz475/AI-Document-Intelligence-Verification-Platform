"""FastAPI application composition root."""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from assureai_api import __version__
from assureai_api.config import Settings, get_settings
from assureai_api.database import create_database_engine, create_session_factory
from assureai_api.evaluation_routes import router as evaluation_router
from assureai_api.logging import configure_logging
from assureai_api.observability import (
    HTTP_LATENCY,
    HTTP_REQUESTS,
    RATE_LIMITS,
    configure_tracing,
    metrics_payload,
    operation_span,
    trace_id,
)
from assureai_api.product_routes import router as product_router
from assureai_api.routes import router
from assureai_api.scanning import create_document_scanner
from assureai_api.schemas import HealthResponse
from assureai_api.secrets import create_secret_store, resolve_provider_secrets
from assureai_api.security import (
    AuthenticationError,
    AuthorizationError,
    Identity,
    RateLimiter,
    RateLimitExceededError,
    authenticate_request,
    authorize_project,
    project_id_from_path,
    record_audit,
    required_role,
    upsert_user,
)
from assureai_api.security_routes import router as security_router
from assureai_api.storage import create_document_storage

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    enqueue_document: Callable[[str], object] | None = None,
    enqueue_extraction: Callable[[str], object] | None = None,
    enqueue_embedding: Callable[[str], object] | None = None,
    enqueue_rag_question: Callable[[str], object] | None = None,
    enqueue_evaluation: Callable[[str], object] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate_production_security()
    if "*" in resolved_settings.cors_origins:
        raise ValueError("Credentialed CORS cannot use a wildcard origin.")
    configure_logging(resolved_settings.log_level)
    configure_tracing(resolved_settings)
    database_url = resolved_settings.database_url or "sqlite:///./assureai.db"
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)
    storage = create_document_storage(resolved_settings)
    secret_store = create_secret_store(resolved_settings)
    resolve_provider_secrets(resolved_settings, secret_store)
    scanner = create_document_scanner(resolved_settings)
    redis_client = (
        Redis.from_url(resolved_settings.redis_url) if resolved_settings.redis_url else None
    )

    def dependencies_ready() -> bool:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                if (
                    connection.dialect.name == "postgresql"
                    and resolved_settings.embedding_provider != "disabled"
                ):
                    vector_available = connection.scalar(
                        text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
                    )
                    if vector_available != 1:
                        return False
            if redis_client is not None:
                redis_client.ping()
            return storage.ready()
        except Exception:
            return False

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = dependencies_ready()
        yield
        app.state.ready = False
        if redis_client is not None:
            redis_client.close()
        storage.close()
        secret_store.close()
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
    application.state.secret_store = secret_store
    application.state.scanner = scanner
    application.state.redis = redis_client
    application.state.rate_limiter = RateLimiter(resolved_settings, redis_client)
    if enqueue_document is None:
        from assureai_api.queue import enqueue_document as default_enqueue

        enqueue_document = default_enqueue
    application.state.enqueue_document = enqueue_document
    if enqueue_extraction is None:
        from assureai_api.queue import enqueue_extraction as default_extraction_enqueue

        enqueue_extraction = default_extraction_enqueue
    application.state.enqueue_extraction = enqueue_extraction
    if enqueue_embedding is None:
        from assureai_api.queue import enqueue_embedding as default_embedding_enqueue

        enqueue_embedding = default_embedding_enqueue
    application.state.enqueue_embedding = enqueue_embedding
    if enqueue_rag_question is None:
        from assureai_api.queue import enqueue_rag_question as default_rag_enqueue

        enqueue_rag_question = default_rag_enqueue
    application.state.enqueue_rag_question = enqueue_rag_question
    if enqueue_evaluation is None:
        from assureai_api.queue import enqueue_evaluation as default_evaluation_enqueue

        enqueue_evaluation = default_evaluation_enqueue
    application.state.enqueue_evaluation = enqueue_evaluation
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Metrics-Token"],
        expose_headers=["X-Request-ID"],
    )

    def error_response(
        code: str,
        message: str,
        request_id: str,
        status_code: int,
        detail: object | None = None,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {"code": code, "message": message, "request_id": request_id},
                "detail": detail if detail is not None else message,
            },
            headers={"X-Request-ID": request_id},
        )

    @application.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        supplied_request_id = request.headers.get("X-Request-ID")
        request_id = (
            supplied_request_id
            if supplied_request_id and len(supplied_request_id) <= 100
            else str(uuid.uuid4())
        )
        request.state.request_id = request_id
        started = time.perf_counter()
        response: Response
        try:
            if (
                sum(len(key) + len(value) for key, value in request.headers.items())
                > resolved_settings.max_header_bytes
            ):
                return error_response(
                    "HEADERS_TOO_LARGE", "Request headers are too large.", request_id, 431
                )
            content_length = request.headers.get("content-length")
            if (
                content_length
                and request.headers.get("content-type", "").startswith("application/json")
                and int(content_length) > resolved_settings.max_json_bytes
            ):
                return error_response(
                    "BODY_TOO_LARGE", "Request body is too large.", request_id, 413
                )

            path = request.url.path
            is_api = path.startswith("/api/v1/")
            is_public_auth = path in {
                "/api/v1/auth/development/login",
                "/api/v1/auth/logout",
            }
            user = None
            if is_api and request.method != "OPTIONS" and not is_public_auth:
                if resolved_settings.auth_mode == "disabled":
                    identity = Identity("development-disabled-auth", None, "Development User")
                else:
                    identity = authenticate_request(request, resolved_settings)
                with session_factory() as security_session:
                    user = upsert_user(security_session, identity)
                    project_id = project_id_from_path(path)
                    if project_id is not None:
                        authorize_project(
                            security_session, user, project_id, required_role(request)
                        )
                    security_session.commit()
                    security_session.expunge(user)
                request.state.user = user
                request.state.project_id = project_id_from_path(path)

            limited = request.method not in {"GET", "HEAD", "OPTIONS"} or path.endswith("/search")
            if limited:
                actor = (
                    user.id
                    if user is not None
                    else request.client.host
                    if request.client
                    else "unknown"
                )
                project_scope = project_id_from_path(path) or "global"
                application.state.rate_limiter.check(f"{actor}:{project_scope}:{path}")

            with operation_span("http.request", method=request.method, path=request.url.path):
                request.state.trace_id = trace_id()
                response = await call_next(request)
            project_id = project_id_from_path(request.url.path)
            audit_type = None
            if request.method == "POST" and request.url.path.endswith("/extractions"):
                audit_type = "extraction.started"
            elif request.method == "POST" and request.url.path.endswith("/search"):
                audit_type = "semantic_search.executed"
            elif request.method == "POST" and request.url.path.endswith("/questions"):
                audit_type = "rag.question_created"
            elif request.method == "POST" and request.url.path.endswith("/evaluation-runs"):
                audit_type = "evaluation.run_created"
            if audit_type and project_id and user is not None and response.status_code < 300:
                with session_factory() as audit_session:
                    record_audit(
                        audit_session,
                        project_id=project_id,
                        event_type=audit_type,
                        actor_user_id=user.id,
                        request_id=request_id,
                        trace_id=request.state.trace_id,
                        target_type="request",
                        target_id=request.url.path,
                    )
                    audit_session.commit()
        except AuthenticationError as exc:
            response = error_response("AUTHENTICATION_REQUIRED", str(exc), request_id, 401)
        except AuthorizationError as exc:
            response = error_response("FORBIDDEN", str(exc), request_id, 403)
        except RateLimitExceededError as exc:
            RATE_LIMITS.inc()
            response = error_response("RATE_LIMITED", str(exc), request_id, 429)
            response.headers["Retry-After"] = str(resolved_settings.rate_limit_window_seconds)
        except ValueError:
            logger.warning("request.rejected", extra={"request_id": request_id})
            response = error_response("INVALID_REQUEST", "The request is invalid.", request_id, 400)
        except Exception:
            logger.exception("request.unhandled", extra={"request_id": request_id})
            response = error_response(
                "INTERNAL_ERROR", "An internal error occurred.", request_id, 500
            )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if resolved_settings.https_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        route = request.scope.get("route")
        route_name = getattr(route, "path", "unmatched")
        HTTP_REQUESTS.labels(request.method, route_name, str(response.status_code)).inc()
        HTTP_LATENCY.labels(request.method, route_name).observe(time.perf_counter() - started)
        return response

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        message = (
            exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
        )
        return error_response(
            f"HTTP_{exc.status_code}",
            message,
            request.state.request_id,
            exc.status_code,
            exc.detail,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        del exc
        return error_response(
            "VALIDATION_ERROR", "The request data is invalid.", request.state.request_id, 422
        )

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

    @application.get("/internal/metrics", include_in_schema=False)
    async def metrics(request: Request) -> Response:
        expected = resolved_settings.metrics_token
        supplied = request.headers.get("X-Metrics-Token")
        if expected is None or supplied != expected.get_secret_value():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
        payload, content_type = metrics_payload()
        return Response(payload, media_type=content_type)

    application.include_router(router)
    application.include_router(evaluation_router)
    application.include_router(security_router)
    application.include_router(product_router)
    return application


app = create_app()
