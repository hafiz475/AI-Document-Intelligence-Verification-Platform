"""Dramatiq composition root for document ingestion jobs."""

from assureai_api.queue import process_document_actor

__all__ = ["process_document_actor"]
