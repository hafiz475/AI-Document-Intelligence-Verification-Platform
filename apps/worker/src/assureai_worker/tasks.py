"""Dramatiq composition root for document ingestion and extraction jobs."""

from assureai_api.queue import (
    process_document_actor,
    process_embedding_actor,
    process_extraction_actor,
)

__all__ = [
    "process_document_actor",
    "process_embedding_actor",
    "process_extraction_actor",
]
