"""Dramatiq actor and API enqueue adapter."""

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from assureai_api.config import get_settings
from assureai_api.database import create_database_engine, create_session_factory
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
