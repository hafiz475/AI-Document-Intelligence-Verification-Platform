"""Low-cardinality metrics and OpenTelemetry setup for API and workers."""

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from assureai_api.config import Settings

HTTP_REQUESTS = Counter(
    "assureai_http_requests_total", "HTTP requests", ("method", "route", "status")
)
HTTP_LATENCY = Histogram(
    "assureai_http_request_duration_seconds", "HTTP request latency", ("method", "route")
)
RATE_LIMITS = Counter("assureai_rate_limit_total", "Rejected rate-limited requests")
DOCUMENT_UPLOADS = Counter("assureai_document_uploads_total", "Accepted document uploads")
PROVIDER_CALLS = Counter(
    "assureai_provider_calls_total", "Provider operations", ("provider", "operation", "status")
)
PROVIDER_LATENCY = Histogram(
    "assureai_provider_duration_seconds", "Provider operation latency", ("provider", "operation")
)
WORKER_JOBS = Counter("assureai_worker_jobs_total", "Worker job outcomes", ("job_type", "status"))
WORKER_ACTIVE = Gauge("assureai_worker_active_jobs", "Currently active worker jobs", ("job_type",))


def configure_tracing(settings: Settings) -> None:
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def trace_id() -> str | None:
    value = trace.get_current_span().get_span_context().trace_id
    return f"{value:032x}" if value else None


def trace_carrier() -> dict[str, str]:
    carrier: dict[str, str] = {}
    inject(carrier)
    return carrier


@contextmanager
def operation_span(name: str, **attributes: Any) -> Iterator[None]:
    tracer = trace.get_tracer("assureai")
    with tracer.start_as_current_span(name, attributes=attributes):
        yield


@contextmanager
def provider_metrics(provider: str, operation: str) -> Iterator[None]:
    started = perf_counter()
    status = "success"
    try:
        with operation_span(f"provider.{operation}", provider=provider):
            yield
    except Exception:
        status = "failure"
        raise
    finally:
        PROVIDER_CALLS.labels(provider, operation, status).inc()
        PROVIDER_LATENCY.labels(provider, operation).observe(perf_counter() - started)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST


@contextmanager
def worker_job(job_type: str, job_id: str, carrier: dict[str, str] | None = None) -> Iterator[None]:
    status = "completed"
    WORKER_ACTIVE.labels(job_type).inc()
    try:
        tracer = trace.get_tracer("assureai.worker")
        context = extract(carrier or {})
        with tracer.start_as_current_span(
            f"worker.{job_type}", context=context, attributes={"job_id": job_id}
        ):
            yield
    except Exception:
        status = "failed"
        raise
    finally:
        WORKER_ACTIVE.labels(job_type).dec()
        WORKER_JOBS.labels(job_type, status).inc()
