"""Dramatiq actor and API enqueue adapter."""

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from assureai_api.ai_providers import create_ai_provider
from assureai_api.config import get_settings
from assureai_api.database import create_database_engine, create_session_factory
from assureai_api.embedding_providers import create_embedding_provider
from assureai_api.extraction_services import process_extraction_run
from assureai_api.retrieval_services import process_embedding_run
from assureai_api.services import process_document
from assureai_api.storage import LocalDocumentStorage

settings = get_settings()
broker = RedisBroker(url=settings.redis_url or "redis://redis:6379/0")  # type: ignore[no-untyped-call]
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=3, min_backoff=1000)
def process_document_actor(document_id: str) -> None:
    if not settings.database_url:
        raise RuntimeError("ASSUREAI_DATABASE_URL is required by the document worker.")
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    storage = LocalDocumentStorage(settings.storage_path)
    with session_factory() as session:
        process_document(session, storage, document_id)
    engine.dispose()


def enqueue_document(document_id: str) -> object:
    return process_document_actor.send(document_id)


@dramatiq.actor(max_retries=2, min_backoff=2000)
def process_extraction_actor(run_id: str) -> None:
    if not settings.database_url:
        raise RuntimeError("ASSUREAI_DATABASE_URL is required by the extraction worker.")
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    provider = create_ai_provider(settings)
    with session_factory() as session:
        process_extraction_run(session, provider=provider, run_id=run_id)
    engine.dispose()


def enqueue_extraction(run_id: str) -> object:
    return process_extraction_actor.send(run_id)


@dramatiq.actor(max_retries=2, min_backoff=2000)
def process_embedding_actor(run_id: str) -> None:
    if not settings.database_url:
        raise RuntimeError("ASSUREAI_DATABASE_URL is required by the embedding worker.")
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    provider = create_embedding_provider(settings)
    with session_factory() as session:
        process_embedding_run(
            session,
            provider=provider,
            run_id=run_id,
            batch_size=settings.embedding_batch_size,
        )
    engine.dispose()


def enqueue_embedding(run_id: str) -> object:
    return process_embedding_actor.send(run_id)
