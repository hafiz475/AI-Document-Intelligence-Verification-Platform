"""Shared transport schemas for operational endpoints."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Stable response for liveness and readiness probes."""

    status: Literal["ok", "ready"]
    service: str
    version: str
