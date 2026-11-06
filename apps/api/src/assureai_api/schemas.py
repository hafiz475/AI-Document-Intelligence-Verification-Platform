"""Typed HTTP request and response contracts."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from assureai_api.models import DocumentStatus


class HealthResponse(BaseModel):
    status: Literal["ok", "ready"]
    service: str
    version: str


class ProjectCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = (
        Field(examples=["Wind Farm Alpha"])
    )
    description: str | None = Field(default=None, max_length=4000)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    filename: str = Field(validation_alias="original_filename")
    mime_type: str
    file_size: int
    sha256_hash: str
    status: DocumentStatus
    page_count: int | None
    character_count: int | None
    processing_error: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    chunk_index: int
    page_number: int | None
    section: str | None
    content: str
    character_count: int
    metadata: dict[str, Any] = Field(validation_alias="chunk_metadata")
    created_at: datetime


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    limit: int
    offset: int
